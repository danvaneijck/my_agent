"""Deployer tool implementations."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
import structlog

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
HEALTH_CHECK_RETRIES = 5
HEALTH_CHECK_DELAY = 2.0


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
class Deployment:
    id: str
    project_name: str
    project_type: str
    port: int
    container_id: str | None = None
    url: str = ""
    status: str = "building"  # building | running | failed | stopped
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "deploy_id": self.id,
            "project_name": self.project_name,
            "project_type": self.project_type,
            "port": self.port,
            "container_id": self.container_id,
            "url": self.url,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
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
EXPOSE 80
"""

DOCKERFILE_NEXTJS = """\
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci 2>/dev/null || npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
"""

DOCKERFILE_STATIC = """\
FROM nginx:alpine
COPY . /usr/share/nginx/html/
EXPOSE 80
"""

DOCKERFILE_NODE = """\
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci 2>/dev/null || npm install
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
"""

_TEMPLATES: dict[str, str] = {
    "react": DOCKERFILE_REACT,
    "nextjs": DOCKERFILE_NEXTJS,
    "static": DOCKERFILE_STATIC,
    "node": DOCKERFILE_NODE,
}

_DEFAULT_PORTS: dict[str, int] = {
    "react": 80,
    "static": 80,
    "nextjs": 3000,
    "node": 3000,
    "docker": 8000,
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
                    url=f"http://localhost:{port}",
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
        if not os.path.isdir(project_path):
            raise ValueError(f"Project path does not exist: {project_path}")

        deploy_id = uuid.uuid4().hex[:8]
        port = self._allocate_port()
        internal_port = container_port or _DEFAULT_PORTS.get(project_type, 8000)
        env_vars = env_vars or {}

        deployment = Deployment(
            id=deploy_id,
            project_name=project_name,
            project_type=project_type,
            port=port,
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
            direct_url = f"http://localhost:{port}"
            deployment.url = direct_url

            # --- Step 5: health check ---
            healthy = await self._health_check(container_name, internal_port)
            deployment.status = "running"

            if not healthy:
                logger.warning("deploy_health_check_failed", deploy_id=deploy_id)

            logger.info("deploy_success", deploy_id=deploy_id, url=direct_url)
            return {
                "deploy_id": deploy_id,
                "project_name": project_name,
                "project_type": project_type,
                "url": direct_url,
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

    async def list_deployments(self, user_id: str | None = None) -> dict:
        """List all active deployments."""
        return {
            "deployments": [d.to_dict() for d in self.deployments.values()],
            "total": len(self.deployments),
        }

    async def teardown(self, deploy_id: str, user_id: str | None = None) -> dict:
        """Stop and remove a single deployment."""
        deployment = self.deployments.get(deploy_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deploy_id}")

        container_name = f"deploy-{deploy_id}"
        await self._remove_container(container_name)
        await self._remove_image(f"deploy-{deploy_id}")
        self._free_port(deployment.port)
        del self.deployments[deploy_id]

        logger.info("deployment_torn_down", deploy_id=deploy_id)
        return {"deploy_id": deploy_id, "status": "removed"}

    async def teardown_all(self, user_id: str | None = None) -> dict:
        """Stop and remove all deployments."""
        ids = list(self.deployments.keys())
        results = []
        for did in ids:
            try:
                results.append(await self.teardown(did))
            except Exception as e:
                results.append({"deploy_id": did, "error": str(e)})
        return {"removed": results, "total": len(results)}

    async def get_logs(
        self, deploy_id: str, lines: int = 50, user_id: str | None = None
    ) -> dict:
        """Return recent logs from a deployment container."""
        if deploy_id not in self.deployments:
            raise ValueError(f"Deployment not found: {deploy_id}")

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
