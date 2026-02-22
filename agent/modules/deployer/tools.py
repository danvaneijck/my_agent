"""Deployer tool implementations."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
import structlog
import yaml

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------
DEPLOY_PORT_START = int(os.environ.get("DEPLOY_PORT_START", "4000"))
DEPLOY_PORT_END = int(os.environ.get("DEPLOY_PORT_END", "4100"))
DEPLOY_BASE_DOMAIN = os.environ.get("DEPLOY_BASE_DOMAIN", "projects.localhost")
DEPLOY_NETWORK = os.environ.get("DEPLOY_NETWORK", "agent-net")
TASK_BASE_DIR = "/tmp/claude_tasks"

BUILD_TIMEOUT = 300  # seconds for docker build
COMPOSE_BUILD_TIMEOUT = 600  # seconds for docker compose build
HEALTH_CHECK_RETRIES = 5
HEALTH_CHECK_DELAY = 2.0

_COMPOSE_FILENAMES = [
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
]


async def _resolve_network_name(hint: str = DEPLOY_NETWORK) -> str:
    """Find the real Docker network name matching *hint*.

    Docker Compose prefixes network names with the project name, so a
    compose-defined ``agent-net`` becomes e.g. ``agent_agent-net`` on the
    host.  We ask ``docker network ls`` and pick the first network whose
    name ends with the hint.  Falls back to the hint unchanged.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "network", "ls", "--format", "{{.Name}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        for name in stdout.decode().splitlines():
            if name == hint or name.endswith(f"_{hint}"):
                return name
    except Exception:
        pass
    return hint


# ---------------------------------------------------------------------------
# Deployment data model
# ---------------------------------------------------------------------------
@dataclass
class ServiceInfo:
    """A single service within a compose deployment."""
    name: str
    container_id: str | None = None
    container_name: str = ""
    status: str = "pending"  # pending | running | exited | failed
    ports: list[dict] = field(default_factory=list)  # [{"host": 4000, "container": 8000, "protocol": "tcp"}]
    image: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "status": self.status,
            "ports": self.ports,
            "image": self.image,
        }


@dataclass
class Deployment:
    id: str
    project_name: str
    project_type: str
    port: int
    user_id: str | None = None
    container_id: str | None = None
    url: str = ""
    status: str = "building"  # building | running | failed | stopped
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Compose-specific fields
    services: list[ServiceInfo] = field(default_factory=list)
    compose_project_dir: str = ""
    deploy_compose_file: str = ""  # path to generated remapped compose file
    env_vars: dict[str, str] = field(default_factory=dict)
    all_ports: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "deploy_id": self.id,
            "project_name": self.project_name,
            "project_type": self.project_type,
            "port": self.port,
            "user_id": self.user_id,
            "container_id": self.container_id,
            "url": self.url,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "services": [s.to_dict() for s in self.services],
            "all_ports": self.all_ports,
            "env_var_count": len(self.env_vars),
        }


# ---------------------------------------------------------------------------
# Dockerfile templates for each project type
# ---------------------------------------------------------------------------
DOCKERFILE_REACT = """\
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci 2>/dev/null || npm install
COPY . .
RUN npm run build
# Collect output from whichever directory the framework produces
RUN mkdir -p /output && \\
    (cp -r build/* /output/ 2>/dev/null || true) && \\
    (cp -r dist/* /output/ 2>/dev/null || true) && \\
    (cp -r out/* /output/ 2>/dev/null || true)

FROM nginx:alpine
COPY --from=build /output/ /usr/share/nginx/html/
RUN echo 'server { listen 3000; root /usr/share/nginx/html; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf
EXPOSE 3000
"""

DOCKERFILE_NEXTJS = """\
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci 2>/dev/null || npm install
COPY . .
RUN npm run build
ENV PORT=3000
EXPOSE 3000
CMD ["npm", "start"]
"""

# Next.js with output: "export" produces static HTML — serve with nginx
DOCKERFILE_NEXTJS_EXPORT = """\
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci 2>/dev/null || npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/out/ /usr/share/nginx/html/
RUN echo 'server { listen 3000; root /usr/share/nginx/html; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf
EXPOSE 3000
"""

DOCKERFILE_STATIC = """\
FROM nginx:alpine
COPY . /usr/share/nginx/html/
RUN echo 'server { listen 3000; root /usr/share/nginx/html; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf
EXPOSE 3000
"""

DOCKERFILE_NODE = """\
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci 2>/dev/null || npm install
COPY . .
ENV PORT=3000
EXPOSE 3000
CMD ["npm", "start"]
"""

# Internal port all deployed containers listen on (standardized for nginx routing)
DEPLOY_INTERNAL_PORT = 3000

_TEMPLATES: dict[str, str] = {
    "react": DOCKERFILE_REACT,
    "nextjs": DOCKERFILE_NEXTJS,
    "static": DOCKERFILE_STATIC,
    "node": DOCKERFILE_NODE,
}

_DEFAULT_PORTS: dict[str, int] = {
    "react": DEPLOY_INTERNAL_PORT,
    "static": DEPLOY_INTERNAL_PORT,
    "nextjs": DEPLOY_INTERNAL_PORT,
    "node": DEPLOY_INTERNAL_PORT,
    "docker": 8000,
}

# Container ports that are known TCP-only (non-HTTP) protocols.
# Services on these ports won't get subdomain proxy routing — only direct host:port access.
_TCP_ONLY_PORTS: set[int] = {
    5432,   # PostgreSQL
    3306,   # MySQL
    6379,   # Redis
    27017,  # MongoDB
    5672,   # RabbitMQ AMQP
    9092,   # Kafka
    2181,   # ZooKeeper
    1433,   # MSSQL
    1521,   # Oracle
    11211,  # Memcached
    9042,   # Cassandra
    26379,  # Redis Sentinel
}


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------
class DeployerTools:
    """Tool implementations for project deployment."""

    def __init__(self) -> None:
        self.deployments: dict[str, Deployment] = {}
        self._used_ports: set[int] = set()
        self._network: str = DEPLOY_NETWORK

    async def init(self) -> None:
        """Resolve the real Docker network name and rediscover existing deployments."""
        self._network = await _resolve_network_name(DEPLOY_NETWORK)
        logger.info("resolved_docker_network", network=self._network)
        await self._rediscover_deployments()

    # ------------------------------------------------------------------
    # Rediscovery on startup
    # ------------------------------------------------------------------

    async def _rediscover_deployments(self) -> None:
        """Find existing deploy-* containers and restore them into memory.

        This lets the deployer survive restarts — Docker containers keep
        running even when the deployer module is restarted, so we query
        ``docker ps -a`` for containers whose names start with ``deploy-``
        and reconstruct ``Deployment`` objects from the inspect output.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-a",
                "--filter", "name=^deploy-",
                "--format", "{{.Names}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            container_names = [
                n.strip() for n in stdout.decode().splitlines() if n.strip()
            ]
        except Exception as exc:
            logger.warning("rediscover_docker_ps_failed", error=str(exc))
            return

        if not container_names:
            return

        recovered = 0
        for name in container_names:
            # Container name is "deploy-{deploy_id}"
            if not name.startswith("deploy-"):
                continue
            deploy_id = name[len("deploy-"):]
            if deploy_id in self.deployments:
                continue  # already tracked

            try:
                info = await self._inspect_container(name)
                if info is None:
                    continue

                state = info.get("State", {})
                config = info.get("Config", {})
                host_config = info.get("HostConfig", {})

                # Determine container status
                running = state.get("Running", False)
                status = "running" if running else "stopped"

                # Extract host port from PortBindings
                port = self._extract_host_port(host_config)
                if port is None:
                    logger.warning(
                        "rediscover_no_port", container=name, deploy_id=deploy_id
                    )
                    continue

                # Extract image name to guess project_type
                image = config.get("Image", "")
                # Labels may carry Traefik metadata with internal port
                labels = config.get("Labels", {})

                created_str = info.get("Created", "")
                try:
                    created_at = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    created_at = datetime.now(timezone.utc)

                container_id = info.get("Id", "")[:12]

                deployment = Deployment(
                    id=deploy_id,
                    project_name=labels.get("com.docker.compose.service", deploy_id),
                    project_type=self._guess_project_type(labels, image),
                    port=port,
                    container_id=container_id,
                    url=f"https://{deploy_id}.{DEPLOY_BASE_DOMAIN}",
                    status=status,
                    created_at=created_at,
                )
                self.deployments[deploy_id] = deployment
                self._used_ports.add(port)
                recovered += 1

            except Exception as exc:
                logger.warning(
                    "rediscover_container_failed",
                    container=name,
                    error=str(exc),
                )

        if recovered:
            logger.info("rediscovered_deployments", count=recovered)

        # Also rediscover compose deployments
        await self._rediscover_compose_deployments()

    async def _rediscover_compose_deployments(self) -> None:
        """Find existing deploy-* compose projects and restore them."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "ls", "--format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return

            projects = json.loads(stdout.decode()) if stdout.decode().strip() else []
        except Exception as exc:
            logger.warning("rediscover_compose_ls_failed", error=str(exc))
            return

        recovered = 0
        for project in projects:
            name = project.get("Name", "")
            if not name.startswith("deploy-"):
                continue
            deploy_id = name[len("deploy-"):]
            if deploy_id in self.deployments:
                continue

            try:
                config_files = project.get("ConfigFiles", "")
                compose_dir = ""
                deploy_file = ""
                if config_files:
                    # ConfigFiles is a comma-separated string of paths
                    first_file = config_files.split(",")[0].strip()
                    compose_dir = os.path.dirname(first_file)
                    # Check if this is our generated deploy file
                    if f"deploy-{deploy_id}" in os.path.basename(first_file):
                        deploy_file = first_file

                status_str = project.get("Status", "").lower()
                status = "running" if "running" in status_str else "stopped"

                services = await self._build_compose_services(
                    deploy_id, compose_dir, deploy_file or None
                ) if compose_dir else []

                all_ports: list[dict] = []
                for svc in services:
                    for port in svc.ports:
                        all_ports.append({**port, "service": svc.name})
                        self._used_ports.add(port["host"])

                # Read env vars if compose dir is accessible
                env_vars = {}
                if compose_dir:
                    env_path = os.path.join(compose_dir, ".env")
                    env_vars = self._read_env_file(env_path)

                primary_port = 0
                primary_url = ""
                if all_ports:
                    primary_port = all_ports[0]["host"]
                    primary_url = f"https://{deploy_id}.{DEPLOY_BASE_DOMAIN}"

                deployment = Deployment(
                    id=deploy_id,
                    project_name=deploy_id,  # Best guess without metadata
                    project_type="compose",
                    port=primary_port,
                    url=primary_url,
                    status=status,
                    services=services,
                    compose_project_dir=compose_dir,
                    deploy_compose_file=deploy_file,
                    env_vars=env_vars,
                    all_ports=all_ports,
                )
                self.deployments[deploy_id] = deployment
                recovered += 1

            except Exception as exc:
                logger.warning(
                    "rediscover_compose_project_failed",
                    project=name,
                    error=str(exc),
                )

        if recovered:
            logger.info("rediscovered_compose_deployments", count=recovered)

    async def _inspect_container(self, name: str) -> dict | None:
        """Run ``docker inspect`` and return the parsed JSON for a container."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        data = json.loads(stdout.decode())
        if isinstance(data, list) and data:
            return data[0]
        return None

    @staticmethod
    def _extract_host_port(host_config: dict) -> int | None:
        """Extract the first mapped host port from HostConfig.PortBindings."""
        bindings = host_config.get("PortBindings") or {}
        for _container_port, mappings in bindings.items():
            if mappings:
                try:
                    return int(mappings[0].get("HostPort", 0))
                except (ValueError, IndexError):
                    continue
        return None

    @staticmethod
    def _guess_project_type(labels: dict, image: str) -> str:
        """Best-effort guess of project_type from container metadata."""
        # Traefik labels carry the internal port which hints at the type
        for key, val in labels.items():
            if "loadbalancer.server.port" in key:
                try:
                    internal = int(val)
                except ValueError:
                    continue
                if internal == 80:
                    return "static"
                if internal == 3000:
                    return "node"
        if "nginx" in image:
            return "static"
        if "node" in image:
            return "node"
        return "docker"

    # ------------------------------------------------------------------
    # Next.js static export detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_nextjs_export(project_path: str) -> bool:
        """Check if a Next.js project uses output: 'export' (static HTML)."""
        for config_name in ("next.config.js", "next.config.mjs", "next.config.ts"):
            config_path = os.path.join(project_path, config_name)
            if os.path.isfile(config_path):
                try:
                    with open(config_path) as f:
                        content = f.read()
                    # Match output: "export" or output: 'export'
                    if re.search(r"""output\s*:\s*['"]export['"]""", content):
                        return True
                except OSError:
                    pass
        return False

    # ------------------------------------------------------------------
    # Deploy ID generation
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a project name to a DNS-safe slug for use as subdomain."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9-]", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return slug[:63] or "app"  # DNS label max 63 chars

    def _generate_deploy_id(self, project_name: str) -> str:
        """Generate a deploy ID from the project name, handling collisions."""
        slug = self._slugify(project_name)
        if slug not in self.deployments:
            return slug
        # Collision — append short random suffix
        for _ in range(10):
            candidate = f"{slug[:55]}-{uuid.uuid4().hex[:6]}"
            if candidate not in self.deployments:
                return candidate
        # Fallback to pure random
        return uuid.uuid4().hex[:8]

    # ------------------------------------------------------------------
    # Port management
    # ------------------------------------------------------------------

    def _allocate_port(self) -> int:
        for port in range(DEPLOY_PORT_START, DEPLOY_PORT_END + 1):
            if port not in self._used_ports:
                self._used_ports.add(port)
                return port
        raise RuntimeError(
            f"No available ports in range {DEPLOY_PORT_START}-{DEPLOY_PORT_END}"
        )

    def _free_port(self, port: int) -> None:
        self._used_ports.discard(port)

    # ------------------------------------------------------------------
    # Smart project directory detection
    # ------------------------------------------------------------------

    # Marker files whose presence indicates a project root, keyed by type.
    _PROJECT_MARKERS: dict[str, list[str]] = {
        "compose": _COMPOSE_FILENAMES,
        "react": ["package.json"],
        "nextjs": ["package.json", "next.config.js", "next.config.mjs", "next.config.ts"],
        "node": ["package.json"],
        "static": ["index.html"],
        "docker": ["Dockerfile"],
    }

    _SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next"}

    def _resolve_project_dir(self, project_path: str, project_type: str) -> str:
        """Resolve the actual project directory within a workspace.

        If *project_path* already contains the expected project markers for
        *project_type*, return it as-is.  Otherwise scan immediate
        subdirectories (1 level deep) for a subdirectory that contains the
        markers and return the best match.
        """
        markers = self._PROJECT_MARKERS.get(project_type, [])
        if not markers:
            return project_path

        # Already has a marker → use as-is
        if any(os.path.exists(os.path.join(project_path, m)) for m in markers):
            return project_path

        # Scan immediate children
        try:
            entries = os.listdir(project_path)
        except OSError:
            return project_path

        candidates: list[tuple[str, int]] = []
        for entry in entries:
            if entry in self._SKIP_DIRS or entry.startswith("."):
                continue
            subdir = os.path.join(project_path, entry)
            if not os.path.isdir(subdir):
                continue
            hits = sum(
                1 for m in markers
                if os.path.exists(os.path.join(subdir, m))
            )
            if hits > 0:
                candidates.append((subdir, hits))

        if not candidates:
            return project_path

        # Pick the candidate with the most marker matches
        candidates.sort(key=lambda c: c[1], reverse=True)
        resolved = candidates[0][0]
        logger.info(
            "resolved_project_dir",
            original=project_path,
            resolved=resolved,
            project_type=project_type,
            candidates=len(candidates),
        )
        return resolved

    # ------------------------------------------------------------------
    # Security validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_project_path(project_path: str) -> None:
        """Ensure project_path is within the allowed workspace directory.

        Prevents deploying arbitrary host paths via path traversal.
        """
        real_path = os.path.realpath(project_path)
        if not real_path.startswith(TASK_BASE_DIR + "/"):
            raise ValueError(
                f"Project path must be under {TASK_BASE_DIR}/, "
                f"got: {project_path}"
            )

    @staticmethod
    def _validate_compose_file(compose_path: str) -> None:
        """Reject compose files with dangerous Docker options.

        Checks for privileged mode, host network, capability additions,
        host PID/IPC, and volume mounts outside the allowed workspace.
        """
        with open(compose_path, "r") as f:
            compose_data = yaml.safe_load(f)

        if not isinstance(compose_data, dict):
            return

        services = compose_data.get("services", {})
        if not isinstance(services, dict):
            return

        for svc_name, svc_config in services.items():
            if not isinstance(svc_config, dict):
                continue

            if svc_config.get("privileged"):
                raise ValueError(
                    f"Service '{svc_name}' uses 'privileged: true' — not allowed"
                )

            if svc_config.get("cap_add"):
                raise ValueError(
                    f"Service '{svc_name}' uses 'cap_add' — not allowed"
                )

            net_mode = svc_config.get("network_mode", "")
            if net_mode == "host":
                raise ValueError(
                    f"Service '{svc_name}' uses 'network_mode: host' — not allowed"
                )

            if svc_config.get("pid") == "host":
                raise ValueError(
                    f"Service '{svc_name}' uses 'pid: host' — not allowed"
                )

            if svc_config.get("ipc") == "host":
                raise ValueError(
                    f"Service '{svc_name}' uses 'ipc: host' — not allowed"
                )

            # Check volume mounts for dangerous host paths
            volumes = svc_config.get("volumes", [])
            for vol in volumes:
                vol_str = str(vol) if not isinstance(vol, str) else vol
                # Block docker socket mounts
                if "docker.sock" in vol_str:
                    raise ValueError(
                        f"Service '{svc_name}' mounts Docker socket — not allowed"
                    )
                # Block host root mounts (e.g. "/:/mnt")
                if isinstance(vol, str) and ":" in vol:
                    host_part = vol.split(":")[0]
                    real_host = os.path.realpath(host_part)
                    if real_host == "/" or real_host.startswith("/var/run"):
                        raise ValueError(
                            f"Service '{svc_name}' mounts dangerous host path "
                            f"'{host_part}' — not allowed"
                        )

    # ------------------------------------------------------------------
    # Public tools
    # ------------------------------------------------------------------

    async def deploy(
        self,
        project_path: str,
        project_name: str,
        project_type: str = "react",
        container_port: int | None = None,
        env_vars: dict | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Build and deploy a project. Returns a live URL."""
        # Validate project path is within allowed workspace
        self._validate_project_path(project_path)

        # Auto-detect compose project if compose file present and type not explicitly set
        if project_type not in ("compose",) and self._find_compose_file(project_path):
            project_type = "compose"

        # Auto-detect project subdirectory if workspace root was given
        project_path = self._resolve_project_dir(project_path, project_type)

        if not os.path.isdir(project_path):
            raise ValueError(f"Project path does not exist: {project_path}")

        # Route compose deployments to dedicated method
        if project_type == "compose":
            return await self.deploy_compose(
                project_path=project_path,
                project_name=project_name,
                env_vars=env_vars,
                user_id=user_id,
            )

        deploy_id = self._generate_deploy_id(project_name)
        port = self._allocate_port()
        internal_port = container_port or _DEFAULT_PORTS.get(project_type, DEPLOY_INTERNAL_PORT)
        env_vars = env_vars or {}

        deployment = Deployment(
            id=deploy_id,
            project_name=project_name,
            project_type=project_type,
            port=port,
            user_id=user_id,
        )
        self.deployments[deploy_id] = deployment

        container_name = f"deploy-{deploy_id}"
        image_name = f"deploy-{deploy_id}"

        try:
            # --- Step 1: prepare Dockerfile ---
            generated_dockerfile = False
            if project_type != "docker":
                template = _TEMPLATES.get(project_type)
                if not template:
                    raise ValueError(f"Unknown project type: {project_type}")
                # Next.js static export needs nginx instead of next start
                if project_type == "nextjs" and self._is_nextjs_export(project_path):
                    template = DOCKERFILE_NEXTJS_EXPORT
                    internal_port = DEPLOY_INTERNAL_PORT
                    logger.info("nextjs_static_export_detected", deploy_id=deploy_id)
                dockerfile_path = os.path.join(project_path, "Dockerfile.deploy")
                with open(dockerfile_path, "w") as fh:
                    fh.write(template)
                dockerfile_name = "Dockerfile.deploy"
                generated_dockerfile = True
            else:
                if not os.path.isfile(os.path.join(project_path, "Dockerfile")):
                    raise ValueError(
                        "Project type is 'docker' but no Dockerfile found in project_path"
                    )
                dockerfile_name = "Dockerfile"

            # --- Step 2: build image (tar | docker build) ---
            logger.info("build_starting", deploy_id=deploy_id, type=project_type)
            await self._build_image(project_path, image_name, dockerfile_name)

            # Clean up generated Dockerfile
            if generated_dockerfile:
                try:
                    os.unlink(os.path.join(project_path, "Dockerfile.deploy"))
                except OSError:
                    pass

            # --- Step 3: run container ---
            cid = await self._run_container(
                container_name, image_name, port, internal_port,
                deploy_id, env_vars,
            )
            deployment.container_id = cid

            # --- Step 4: resolve URL ---
            subdomain_url = f"https://{deploy_id}.{DEPLOY_BASE_DOMAIN}"
            direct_url = f"http://localhost:{port}"
            deployment.url = subdomain_url

            # --- Step 5: health check ---
            healthy = await self._health_check(container_name, internal_port)
            deployment.status = "running"

            if not healthy:
                logger.warning("deploy_health_check_failed", deploy_id=deploy_id)

            logger.info("deploy_success", deploy_id=deploy_id, url=subdomain_url)
            return {
                "deploy_id": deploy_id,
                "project_name": project_name,
                "project_type": project_type,
                "url": subdomain_url,
                "direct_url": direct_url,
                "port": port,
                "container_id": cid,
                "status": "running",
                "healthy": healthy,
            }

        except Exception as e:
            deployment.status = "failed"
            self._free_port(port)
            await self._remove_container(container_name)
            await self._remove_image(image_name)
            del self.deployments[deploy_id]
            logger.error("deploy_failed", deploy_id=deploy_id, error=str(e))
            raise

    def _get_deployment(self, deploy_id: str, user_id: str | None = None) -> Deployment:
        """Look up a deployment, enforcing ownership when user_id is provided."""
        deployment = self.deployments.get(deploy_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deploy_id}")
        if user_id and deployment.user_id and deployment.user_id != user_id:
            raise ValueError(f"Deployment not found: {deploy_id}")
        return deployment

    async def list_deployments(self, user_id: str | None = None) -> dict:
        """List active deployments for the given user."""
        if user_id:
            deploys = [d for d in self.deployments.values() if d.user_id == user_id]
        else:
            deploys = list(self.deployments.values())
        return {
            "deployments": [d.to_dict() for d in deploys],
            "total": len(deploys),
        }

    async def teardown(self, deploy_id: str, user_id: str | None = None) -> dict:
        """Stop and remove a single deployment."""
        deployment = self._get_deployment(deploy_id, user_id)

        if deployment.project_type == "compose":
            # Remove all proxy bridge containers BEFORE compose down
            # (they're attached to the compose network, blocking removal)
            await self._remove_compose_proxies(deploy_id, deployment.all_ports)
            await self._compose_down(
                deploy_id, deployment.compose_project_dir,
                deployment.deploy_compose_file,
            )
            # Free all tracked ports
            for port_info in deployment.all_ports:
                self._free_port(port_info.get("host", 0))
        else:
            container_name = f"deploy-{deploy_id}"
            await self._remove_container(container_name)
            await self._remove_image(f"deploy-{deploy_id}")
            self._free_port(deployment.port)

        del self.deployments[deploy_id]

        logger.info("deployment_torn_down", deploy_id=deploy_id)
        return {"deploy_id": deploy_id, "status": "removed"}

    async def teardown_all(self, user_id: str | None = None) -> dict:
        """Stop and remove all deployments for the given user."""
        if user_id:
            ids = [d.id for d in self.deployments.values() if d.user_id == user_id]
        else:
            ids = list(self.deployments.keys())
        results = []
        for did in ids:
            try:
                results.append(await self.teardown(did, user_id=user_id))
            except Exception as e:
                results.append({"deploy_id": did, "error": str(e)})
        return {"removed": results, "total": len(results)}

    async def get_logs(
        self, deploy_id: str, lines: int = 50, user_id: str | None = None
    ) -> dict:
        """Return recent logs from a deployment container."""
        deployment = self._get_deployment(deploy_id, user_id)

        if deployment.project_type == "compose":
            compose_file = self._get_compose_file_for(deployment)
            cmd = [
                "docker", "compose",
                "-p", f"deploy-{deploy_id}",
                "-f", compose_file or "docker-compose.yml",
                "logs", "--tail", str(lines), "--no-color",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=deployment.compose_project_dir or None,
            )
        else:
            container_name = f"deploy-{deploy_id}"
            proc = await asyncio.create_subprocess_exec(
                "docker", "logs", "--tail", str(lines), container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout, stderr = await proc.communicate()

        return {
            "deploy_id": deploy_id,
            "logs": (
                stdout.decode("utf-8", errors="replace")
                + stderr.decode("utf-8", errors="replace")
            ),
            "lines_requested": lines,
        }

    # ------------------------------------------------------------------
    # Compose deployment
    # ------------------------------------------------------------------

    @staticmethod
    def _find_compose_file(project_path: str) -> str | None:
        """Find a docker-compose/compose file in the given directory."""
        for name in _COMPOSE_FILENAMES:
            path = os.path.join(project_path, name)
            if os.path.isfile(path):
                return path
        return None

    def _get_compose_file_for(self, deployment: Deployment) -> str | None:
        """Get the compose file to use for commands on a deployment.

        Prefers the generated deploy file (with remapped ports),
        falls back to the original compose file.
        """
        if deployment.deploy_compose_file and os.path.isfile(deployment.deploy_compose_file):
            return deployment.deploy_compose_file
        return self._find_compose_file(deployment.compose_project_dir)

    @staticmethod
    def _read_env_file(path: str) -> dict[str, str]:
        """Parse a .env file into a dict."""
        env = {}
        if not os.path.isfile(path):
            return env
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    env[key.strip()] = value.strip()
        return env

    @staticmethod
    def _write_env_file(path: str, env_vars: dict[str, str]) -> None:
        """Write a dict to a .env file."""
        with open(path, "w") as f:
            for key, value in sorted(env_vars.items()):
                f.write(f"{key}={value}\n")

    def _remap_compose_ports(
        self, compose_path: str, deploy_id: str
    ) -> tuple[str, list[dict]]:
        """Parse compose file, remap host ports to managed range, write modified file.

        Returns (modified_file_path, all_ports_list).
        Internal container ports and service-to-service networking are unchanged.
        Only host-facing port bindings are remapped.
        """
        with open(compose_path) as f:
            compose = yaml.safe_load(f)

        all_ports: list[dict] = []
        services = compose.get("services", {})

        for svc_name, svc_config in services.items():
            ports = svc_config.get("ports")
            if not ports:
                continue

            remapped: list = []
            for port_spec in ports:
                if isinstance(port_spec, dict):
                    # Long syntax: {target: 80, published: 8080, protocol: tcp}
                    container_port = port_spec.get("target")
                    original_host = port_spec.get("published")
                    protocol = port_spec.get("protocol", "tcp")
                    if original_host is not None:
                        allocated = self._allocate_port()
                        all_ports.append({
                            "service": svc_name,
                            "host": allocated,
                            "container": int(container_port),
                            "protocol": protocol,
                            "original_host": int(original_host),
                        })
                        port_spec = {**port_spec, "published": allocated}
                    remapped.append(port_spec)

                elif isinstance(port_spec, (str, int)):
                    spec = str(port_spec)
                    protocol = "tcp"
                    if "/" in spec:
                        spec, protocol = spec.rsplit("/", 1)

                    parts = spec.split(":")
                    if len(parts) >= 2:
                        # host_port:container_port or ip:host_port:container_port
                        if len(parts) == 3:
                            # ip:host:container
                            container_port = int(parts[2])
                            original_host = int(parts[1])
                        else:
                            # host:container
                            container_port = int(parts[1])
                            original_host = int(parts[0])

                        allocated = self._allocate_port()
                        all_ports.append({
                            "service": svc_name,
                            "host": allocated,
                            "container": container_port,
                            "protocol": protocol,
                            "original_host": original_host,
                        })
                        remapped.append(f"{allocated}:{container_port}")
                    else:
                        # Container-only port (e.g. "80") — no host binding, keep as-is
                        remapped.append(port_spec)
                else:
                    remapped.append(port_spec)

            svc_config["ports"] = remapped

        # Write modified compose file next to the original
        compose_dir = os.path.dirname(compose_path)
        deploy_file = os.path.join(compose_dir, f"docker-compose.deploy-{deploy_id}.yml")
        with open(deploy_file, "w") as f:
            yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

        logger.info(
            "compose_ports_remapped",
            deploy_id=deploy_id,
            remapped_ports=len(all_ports),
        )
        return deploy_file, all_ports

    async def _compose_ps(
        self, deploy_id: str, compose_dir: str, compose_file: str | None = None
    ) -> list[dict]:
        """Run ``docker compose ps --format json`` and return parsed output."""
        compose_file = compose_file or self._find_compose_file(compose_dir)
        cmd = [
            "docker", "compose",
            "-p", f"deploy-{deploy_id}",
        ]
        if compose_file:
            cmd.extend(["-f", compose_file])
        cmd.extend(["ps", "-a", "--format", "json"])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=compose_dir or None,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []

        results = []
        for line in stdout.decode().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return results

    async def _inspect_service_ports(self, container_name: str) -> list[dict]:
        """Extract all port mappings from a container via docker inspect."""
        info = await self._inspect_container(container_name)
        if not info:
            return []

        ports = []
        bindings = info.get("HostConfig", {}).get("PortBindings") or {}
        for container_port_proto, mappings in bindings.items():
            if not mappings:
                continue
            container_port = container_port_proto.split("/")[0]
            protocol = container_port_proto.split("/")[1] if "/" in container_port_proto else "tcp"
            for mapping in mappings:
                host_port = mapping.get("HostPort")
                if host_port:
                    ports.append({
                        "host": int(host_port),
                        "container": int(container_port),
                        "protocol": protocol,
                    })
        return ports

    async def _build_compose_services(
        self, deploy_id: str, compose_dir: str, compose_file: str | None = None
    ) -> list[ServiceInfo]:
        """Enumerate services from a running compose project."""
        ps_output = await self._compose_ps(deploy_id, compose_dir, compose_file)
        services = []
        for svc in ps_output:
            name = svc.get("Service", svc.get("Name", "unknown"))
            container_name = svc.get("Name", "")
            container_id = svc.get("ID", "")[:12] if svc.get("ID") else None
            state = svc.get("State", "unknown").lower()
            image = svc.get("Image", "")

            # Map compose states to our status values
            if state in ("running",):
                status = "running"
            elif state in ("exited", "dead"):
                status = "exited"
            else:
                status = state

            ports = await self._inspect_service_ports(container_name) if container_name else []

            services.append(ServiceInfo(
                name=name,
                container_id=container_id,
                container_name=container_name,
                status=status,
                ports=ports,
                image=image,
            ))
        return services

    async def _create_compose_proxies(
        self,
        deploy_id: str,
        allocated_ports: list[dict],
    ) -> list[str]:
        """Create lightweight nginx proxies bridging compose network to deploy-net.

        One proxy per unique service.  The first service gets the plain
        ``deploy-{deploy_id}`` name (→ ``{deploy_id}.apps.…``), additional
        services get ``deploy-{deploy_id}-{service}`` (→ ``{deploy_id}-{service}.apps.…``).

        Each proxy container:
        * Joins the compose default network (to reach compose services)
        * Joins deploy-net (so the outer nginx can reach it)
        * Listens on port 3000 and reverse-proxies to the target service
        """
        compose_network = f"deploy-{deploy_id}_default"

        # Deduplicate: one proxy per unique HTTP service (skip TCP-only ports)
        http_services: dict[str, dict] = {}
        for port_info in allocated_ports:
            svc = port_info["service"]
            container_port = port_info["container"]
            if svc not in http_services and container_port not in _TCP_ONLY_PORTS:
                http_services[svc] = port_info

        created: list[str] = []
        for idx, (service_name, port_info) in enumerate(http_services.items()):
            internal_port = port_info["container"]

            # First service = primary, rest get -{service} suffix
            if idx == 0:
                proxy_name = f"deploy-{deploy_id}"
            else:
                proxy_name = f"deploy-{deploy_id}-{self._slugify(service_name)}"

            nginx_conf = (
                f"server {{ listen 3000; "
                f"location / {{ "
                f"proxy_pass http://{service_name}:{internal_port}; "
                f"proxy_set_header Host $host; "
                f"proxy_set_header X-Real-IP $remote_addr; "
                f"proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; "
                f"proxy_set_header X-Forwarded-Proto $scheme; "
                f"proxy_http_version 1.1; "
                f"proxy_set_header Upgrade $http_upgrade; "
                f'proxy_set_header Connection "upgrade"; '
                f"}} }}"
            )

            try:
                cmd: list[str] = [
                    "docker", "run", "-d",
                    "--name", proxy_name,
                    f"--network={compose_network}",
                    "--restart=unless-stopped",
                    "nginx:alpine",
                    "sh", "-c",
                    f"echo '{nginx_conf}' > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'",
                ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    logger.warning(
                        "compose_proxy_run_failed",
                        deploy_id=deploy_id,
                        service=service_name,
                        error=stderr.decode("utf-8", errors="replace")[:500],
                    )
                    continue

                # Connect the proxy to deploy-net so the outer nginx can reach it
                proc2 = await asyncio.create_subprocess_exec(
                    "docker", "network", "connect", self._network, proxy_name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr2 = await proc2.communicate()

                if proc2.returncode != 0:
                    logger.warning(
                        "compose_proxy_network_connect_failed",
                        deploy_id=deploy_id,
                        service=service_name,
                        error=stderr2.decode("utf-8", errors="replace")[:500],
                    )

                created.append(proxy_name)
                logger.info(
                    "compose_proxy_created",
                    deploy_id=deploy_id,
                    proxy=proxy_name,
                    target=f"{service_name}:{internal_port}",
                )

            except Exception as exc:
                logger.warning(
                    "compose_proxy_failed",
                    deploy_id=deploy_id,
                    service=service_name,
                    error=str(exc),
                )

        return created

    async def _remove_compose_proxies(
        self, deploy_id: str, all_ports: list[dict]
    ) -> None:
        """Remove all proxy bridge containers for a compose deployment."""
        # Always remove the primary proxy
        await self._remove_container(f"deploy-{deploy_id}")

        # Remove per-service proxies (for services beyond the first)
        seen_services: list[str] = []
        for port_info in all_ports:
            svc = port_info.get("service", "")
            if svc and svc not in seen_services:
                seen_services.append(svc)
                if len(seen_services) > 1:
                    slug = self._slugify(svc)
                    await self._remove_container(f"deploy-{deploy_id}-{slug}")

    async def deploy_compose(
        self,
        project_path: str,
        project_name: str,
        env_vars: dict | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Deploy a docker-compose project with remapped ports.

        Host-facing ports are remapped to the managed 4000-4100 range to
        avoid collisions.  Internal service-to-service communication is
        unaffected (compose creates an isolated network).
        """
        # Validate project path
        self._validate_project_path(project_path)

        compose_file = self._find_compose_file(project_path)
        if not compose_file:
            raise ValueError(
                f"No docker-compose.yml or compose.yml found in {project_path}"
            )

        # Validate compose file for dangerous options
        self._validate_compose_file(compose_file)

        deploy_id = self._generate_deploy_id(project_name)
        env_vars = env_vars or {}

        deployment = Deployment(
            id=deploy_id,
            project_name=project_name,
            project_type="compose",
            port=0,
            user_id=user_id,
            compose_project_dir=project_path,
            env_vars=env_vars,
        )
        self.deployments[deploy_id] = deployment

        deploy_compose_file = ""
        allocated_ports: list[dict] = []

        try:
            # Write .env file if env vars provided (merge with existing)
            env_path = os.path.join(project_path, ".env")
            if env_vars:
                existing = self._read_env_file(env_path)
                existing.update(env_vars)
                self._write_env_file(env_path, existing)
                deployment.env_vars = existing
            elif os.path.isfile(env_path):
                deployment.env_vars = self._read_env_file(env_path)

            # Remap host ports to managed range
            deploy_compose_file, allocated_ports = self._remap_compose_ports(
                compose_file, deploy_id
            )
            deployment.deploy_compose_file = deploy_compose_file
            deployment.all_ports = allocated_ports

            # Track allocated ports
            for port_info in allocated_ports:
                self._used_ports.add(port_info["host"])

            # Set primary URL from first HTTP-capable port
            if allocated_ports:
                deployment.port = allocated_ports[0]["host"]
                first_http = next(
                    (p for p in allocated_ports if p["container"] not in _TCP_ONLY_PORTS),
                    None,
                )
                if first_http:
                    deployment.url = f"https://{deploy_id}.{DEPLOY_BASE_DOMAIN}"

            # Build and start services
            logger.info("compose_build_starting", deploy_id=deploy_id)
            cmd = [
                "docker", "compose",
                "-p", f"deploy-{deploy_id}",
                "-f", deploy_compose_file,
                "up", "-d", "--build",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=project_path,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=COMPOSE_BUILD_TIMEOUT
            )

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace")[:3000]
                raise RuntimeError(f"Docker compose up failed:\n{err}")

            # Enumerate live services
            services = await self._build_compose_services(
                deploy_id, project_path, deploy_compose_file
            )
            deployment.services = services
            deployment.status = "running"

            # Create proxy containers to bridge compose network → deploy-net
            # One proxy per HTTP service so each gets its own subdomain
            if allocated_ports:
                await self._create_compose_proxies(deploy_id, allocated_ports)

                # Add URLs to each port entry:
                # - HTTP services get subdomain URLs (via proxy)
                # - TCP-only services get direct host:port access only
                http_idx = 0
                http_seen: set[str] = set()
                for port_info in allocated_ports:
                    svc = port_info["service"]
                    container_port = port_info["container"]
                    # Always include the direct port for all services
                    port_info["direct"] = f":{port_info['host']}"

                    if container_port in _TCP_ONLY_PORTS:
                        # TCP-only — no subdomain, only direct port access
                        continue

                    if svc not in http_seen:
                        http_seen.add(svc)
                        if http_idx == 0:
                            port_info["url"] = f"https://{deploy_id}.{DEPLOY_BASE_DOMAIN}"
                        else:
                            slug = self._slugify(svc)
                            port_info["url"] = f"https://{deploy_id}-{slug}.{DEPLOY_BASE_DOMAIN}"
                        http_idx += 1
                    elif "url" not in port_info:
                        for prev in allocated_ports:
                            if prev["service"] == svc and "url" in prev:
                                port_info["url"] = prev["url"]
                                break

                deployment.all_ports = allocated_ports

            logger.info(
                "compose_deploy_success",
                deploy_id=deploy_id,
                services=len(services),
                ports=len(allocated_ports),
            )

            return {
                "deploy_id": deploy_id,
                "project_name": project_name,
                "project_type": "compose",
                "url": deployment.url,
                "port": deployment.port,
                "status": "running",
                "services": [s.to_dict() for s in services],
                "all_ports": allocated_ports,
            }

        except Exception as e:
            deployment.status = "failed"
            # Free allocated ports
            for port_info in allocated_ports:
                self._free_port(port_info["host"])
            # Remove all proxy bridge containers before compose down
            await self._remove_compose_proxies(deploy_id, allocated_ports)
            # Try to clean up containers
            await self._compose_down(deploy_id, project_path, deploy_compose_file)
            # Clean up generated file
            if deploy_compose_file and os.path.isfile(deploy_compose_file):
                try:
                    os.unlink(deploy_compose_file)
                except OSError:
                    pass
            del self.deployments[deploy_id]
            logger.error("compose_deploy_failed", deploy_id=deploy_id, error=str(e))
            raise

    async def _compose_down(
        self, deploy_id: str, compose_dir: str, deploy_file: str = ""
    ) -> None:
        """Tear down a compose project and clean up generated files."""
        # Prefer the deploy file (has remapped ports), fall back to original
        file_to_use = deploy_file or self._find_compose_file(compose_dir)
        cmd = [
            "docker", "compose",
            "-p", f"deploy-{deploy_id}",
        ]
        if file_to_use:
            cmd.extend(["-f", file_to_use])
        cmd.extend(["down", "--volumes", "--remove-orphans"])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=compose_dir or None,
            )
            await asyncio.wait_for(proc.wait(), timeout=60)
        except Exception as exc:
            logger.warning("compose_down_failed", deploy_id=deploy_id, error=str(exc))

        # Clean up generated deploy compose file
        if deploy_file and os.path.isfile(deploy_file):
            try:
                os.unlink(deploy_file)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # New tool methods (compose + general)
    # ------------------------------------------------------------------

    async def get_services(
        self, deploy_id: str, user_id: str | None = None
    ) -> dict:
        """Return live service info for a compose deployment."""
        deployment = self._get_deployment(deploy_id, user_id)
        if deployment.project_type != "compose":
            return {
                "deploy_id": deploy_id,
                "services": [],
                "message": "Not a compose deployment",
            }

        # Refresh service info from Docker
        compose_file = self._get_compose_file_for(deployment)
        services = await self._build_compose_services(
            deploy_id, deployment.compose_project_dir, compose_file
        )
        deployment.services = services

        # Refresh port info
        all_ports: list[dict] = []
        for svc in services:
            for port in svc.ports:
                all_ports.append({**port, "service": svc.name})
        deployment.all_ports = all_ports

        return {
            "deploy_id": deploy_id,
            "services": [s.to_dict() for s in services],
            "all_ports": all_ports,
        }

    async def get_service_logs(
        self,
        deploy_id: str,
        service_name: str,
        lines: int = 50,
        user_id: str | None = None,
    ) -> dict:
        """Return logs for a specific service in a compose deployment."""
        deployment = self._get_deployment(deploy_id, user_id)
        if deployment.project_type != "compose":
            raise ValueError("Service logs only available for compose deployments")

        compose_file = self._get_compose_file_for(deployment)
        cmd = [
            "docker", "compose",
            "-p", f"deploy-{deploy_id}",
        ]
        if compose_file:
            cmd.extend(["-f", compose_file])
        cmd.extend(["logs", "--tail", str(lines), "--no-color", service_name])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=deployment.compose_project_dir or None,
        )
        stdout, stderr = await proc.communicate()

        return {
            "deploy_id": deploy_id,
            "service_name": service_name,
            "logs": (
                stdout.decode("utf-8", errors="replace")
                + stderr.decode("utf-8", errors="replace")
            ),
            "lines_requested": lines,
        }

    async def get_env_vars(
        self, deploy_id: str, user_id: str | None = None
    ) -> dict:
        """Return current .env vars for a deployment."""
        deployment = self._get_deployment(deploy_id, user_id)

        if deployment.project_type == "compose" and deployment.compose_project_dir:
            env_path = os.path.join(deployment.compose_project_dir, ".env")
            env_vars = self._read_env_file(env_path)
            deployment.env_vars = env_vars
        else:
            env_vars = deployment.env_vars

        return {
            "deploy_id": deploy_id,
            "env_vars": env_vars,
        }

    async def update_env_vars(
        self,
        deploy_id: str,
        env_vars: dict,
        restart: bool = True,
        user_id: str | None = None,
    ) -> dict:
        """Update .env vars and optionally restart the deployment."""
        deployment = self._get_deployment(deploy_id, user_id)

        if deployment.project_type == "compose" and deployment.compose_project_dir:
            env_path = os.path.join(deployment.compose_project_dir, ".env")
            # Merge: existing values are overwritten, new keys added
            existing = self._read_env_file(env_path)
            existing.update(env_vars)
            self._write_env_file(env_path, existing)
            deployment.env_vars = existing

            if restart:
                # Recreate services with new env
                compose_file = self._get_compose_file_for(deployment)
                cmd = [
                    "docker", "compose",
                    "-p", f"deploy-{deploy_id}",
                ]
                if compose_file:
                    cmd.extend(["-f", compose_file])
                cmd.extend(["up", "-d"])

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=deployment.compose_project_dir,
                )
                await asyncio.wait_for(proc.communicate(), timeout=120)

                # Refresh services
                deployment.services = await self._build_compose_services(
                    deploy_id, deployment.compose_project_dir, compose_file
                )
        else:
            deployment.env_vars = env_vars
            # For single-container, restart is needed to apply env vars
            if restart:
                await self.restart_deployment(deploy_id, user_id)

        return {
            "deploy_id": deploy_id,
            "env_vars": deployment.env_vars,
            "restarted": restart,
        }

    async def restart_deployment(
        self, deploy_id: str, user_id: str | None = None
    ) -> dict:
        """Restart a deployment (compose or single-container)."""
        deployment = self._get_deployment(deploy_id, user_id)

        if deployment.project_type == "compose":
            compose_file = self._get_compose_file_for(deployment)
            cmd = [
                "docker", "compose",
                "-p", f"deploy-{deploy_id}",
            ]
            if compose_file:
                cmd.extend(["-f", compose_file])
            cmd.append("restart")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=deployment.compose_project_dir or None,
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)

            # Refresh services
            deployment.services = await self._build_compose_services(
                deploy_id, deployment.compose_project_dir, compose_file
            )
        else:
            container_name = f"deploy-{deploy_id}"
            proc = await asyncio.create_subprocess_exec(
                "docker", "restart", container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=60)

        deployment.status = "running"
        return {"deploy_id": deploy_id, "status": "restarted"}

    # ------------------------------------------------------------------
    # Docker helpers
    # ------------------------------------------------------------------

    async def _build_image(
        self, project_path: str, image_name: str, dockerfile: str
    ) -> None:
        """Build a Docker image by piping a tar context to ``docker build``.

        Uses a shell pipe so the OS connects the file descriptors natively.
        asyncio.StreamReader objects (from create_subprocess_exec) don't
        expose fileno(), so passing one process's stdout as another's stdin
        fails with "'StreamReader' object has no attribute 'fileno'".
        """
        cmd = (
            f"tar -C {shlex.quote(project_path)} -c . "
            f"| docker build -f {shlex.quote(dockerfile)} "
            f"-t {shlex.quote(image_name)} -"
        )

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=BUILD_TIMEOUT
        )

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:3000]
            raise RuntimeError(f"Docker build failed:\n{err}")

    async def _run_container(
        self,
        container_name: str,
        image_name: str,
        host_port: int,
        internal_port: int,
        deploy_id: str,
        env_vars: dict[str, str],
    ) -> str:
        """Start a deployment container. Returns the container ID."""
        cmd: list[str] = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{host_port}:{internal_port}",
            f"--network={self._network}",
            # Traefik labels
            "-l", "traefik.enable=true",
            "-l", f"traefik.http.routers.{deploy_id}.rule=Host(`{deploy_id}.{DEPLOY_BASE_DOMAIN}`)",
            "-l", f"traefik.http.services.{deploy_id}.loadbalancer.server.port={internal_port}",
        ]

        for key, value in env_vars.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.append(image_name)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Failed to start container: {err}")

        return stdout.decode().strip()[:12]

    async def _health_check(
        self, container_name: str, internal_port: int
    ) -> bool:
        """Check if the deployed service is responding (via Docker network)."""
        url = f"http://{container_name}:{internal_port}/"
        for attempt in range(HEALTH_CHECK_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url)
                    if resp.status_code < 500:
                        return True
            except Exception:
                pass
            if attempt < HEALTH_CHECK_RETRIES - 1:
                await asyncio.sleep(HEALTH_CHECK_DELAY)
        return False

    async def _remove_container(self, name: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass

    async def _remove_image(self, name: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rmi", "-f", name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass
