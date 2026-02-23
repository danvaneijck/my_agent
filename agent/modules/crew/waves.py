"""Dependency graph analysis and wave computation for crew sessions."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


def compute_waves(tasks: list[dict]) -> list[list[str]]:
    """Topologically sort tasks into parallelisable waves.

    Each task dict must have at minimum:
        - task_id: str (UUID)
        - depends_on: list[str] | None  (list of task_id strings)

    Returns a list of waves, where each wave is a list of task_ids that
    can be executed in parallel.  Wave 0 contains tasks with no
    dependencies; wave N contains tasks whose dependencies are all
    satisfied in waves < N.

    Raises ``ValueError`` on dependency cycles or references to unknown
    task IDs.
    """
    task_ids = {t["task_id"] for t in tasks}

    # Build adjacency: task_id → set of prerequisite task_ids
    deps: dict[str, set[str]] = {}
    for t in tasks:
        raw = t.get("depends_on") or []
        resolved = set()
        for dep_id in raw:
            if dep_id not in task_ids:
                logger.warning(
                    "unknown_dependency_ignored",
                    task_id=t["task_id"],
                    unknown_dep=dep_id,
                )
                continue
            resolved.add(dep_id)
        deps[t["task_id"]] = resolved

    waves: list[list[str]] = []
    assigned: set[str] = set()
    remaining = set(task_ids)

    while remaining:
        # Find tasks whose deps are fully satisfied
        wave = [
            tid for tid in remaining
            if deps[tid].issubset(assigned)
        ]
        if not wave:
            cycle_tasks = ", ".join(sorted(remaining))
            raise ValueError(
                f"Dependency cycle detected among tasks: {cycle_tasks}"
            )
        wave.sort()  # deterministic ordering
        waves.append(wave)
        assigned.update(wave)
        remaining -= set(wave)

    return waves


def get_ready_tasks(
    tasks: list[dict],
    completed_task_ids: set[str],
) -> list[dict]:
    """Return tasks whose dependencies are all in *completed_task_ids*
    and whose own status is still ``todo``.
    """
    ready = []
    completed = set(completed_task_ids)
    for t in tasks:
        if t.get("status") != "todo":
            continue
        dep_ids = set(t.get("depends_on") or [])
        if dep_ids.issubset(completed):
            ready.append(t)
    return ready
