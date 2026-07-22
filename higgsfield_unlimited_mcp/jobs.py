"""In-process job registry.

Tracks jobs submitted during this server's lifetime so tools like
``queue_status``, ``list_jobs`` and ``wait_for_job`` can report on them without
re-hitting the API for every poll.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

_TERMINAL = {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED}


@dataclass
class JobRecord:
    id: str
    model: str
    kind: str  # image | video | audio | raw | storyboard
    status: str = STATUS_QUEUED
    prompt: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    results: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def touch(self, status: str | None = None) -> None:
        if status is not None:
            self.status = status
        self.updated_at = time.time()

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_terminal"] = self.is_terminal
        return d


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def add(self, record: JobRecord) -> JobRecord:
        with self._lock:
            self._jobs[record.id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: Any) -> JobRecord | None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                return None
            for k, v in changes.items():
                setattr(rec, k, v)
            rec.updated_at = time.time()
            return rec

    def all(self) -> list[JobRecord]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda r: r.created_at, reverse=True)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            jobs = list(self._jobs.values())
        counts: dict[str, int] = {}
        for j in jobs:
            counts[j.status] = counts.get(j.status, 0) + 1
        active = [j.id for j in jobs if not j.is_terminal]
        return {
            "total": len(jobs),
            "counts": counts,
            "active": active,
            "active_count": len(active),
        }
