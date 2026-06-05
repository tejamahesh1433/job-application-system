"""
Backend storage for the Job Discovery inbox.

The UI treats discovered jobs like an inbox: cards stay visible until the user
removes them or starts an application workflow. Keeping this as project-local
JSON avoids browser localStorage and prevents repeat API calls for the same
search filters.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORE_PATH = PROJECT_ROOT / "data" / "job_discovery_inbox.json"


class DiscoveryStore:
    def __init__(self, path: Path = STORE_PATH):
        self.path = path
        self._lock = RLock()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"jobs": {}, "searches": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"jobs": {}, "searches": {}}
            data.setdefault("jobs", {})
            data.setdefault("searches", {})
            return data
        except Exception:
            return {"jobs": {}, "searches": {}}

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def job_key(self, job: Dict[str, Any]) -> str:
        raw = (job.get("url") or "").strip().lower()
        if not raw:
            raw = f"{job.get('company','')}|{job.get('title','')}|{job.get('source','')}".lower()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def search_key(self, params: Dict[str, Any]) -> str:
        normalized = {
            str(k): str(v or "").strip().lower()
            for k, v in sorted(params.items())
            if k not in {"force", "_"}
        }
        raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def list_jobs(
        self,
        user_id: int = 1,
        include_removed: bool = False,
        include_applied: bool = False,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._load()
            jobs = []
            for key, record in data["jobs"].items():
                if int(record.get("user_id", 1)) != int(user_id):
                    continue
                status = record.get("discovery_status", "active")
                if status == "removed" and not include_removed:
                    continue
                if status == "applied" and not include_applied:
                    continue
                job = dict(record.get("job") or {})
                job["id"] = key
                job["discovery_status"] = status
                job["saved_at"] = record.get("saved_at")
                job["last_seen_at"] = record.get("last_seen_at")
                jobs.append(job)
            jobs.sort(key=lambda item: item.get("last_seen_at") or item.get("saved_at") or "", reverse=True)
            return jobs

    def has_search(self, search_key: str, user_id: int = 1) -> bool:
        with self._lock:
            search = self._load()["searches"].get(search_key)
            return bool(search and int(search.get("user_id", 1)) == int(user_id))

    def save_search(
        self,
        search_key: str,
        params: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        user_id: int = 1,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._load()
            now = self._now()
            ids = []
            for job in jobs:
                key = self.job_key(job)
                existing = data["jobs"].get(key, {})
                record = {
                    "user_id": int(user_id),
                    "discovery_status": existing.get("discovery_status", "active"),
                    "saved_at": existing.get("saved_at", now),
                    "last_seen_at": now,
                    "job": {**job, "id": key},
                }
                if record["discovery_status"] != "applied":
                    data["jobs"][key] = record
                ids.append(key)
            data["searches"][search_key] = {
                "user_id": int(user_id),
                "params": params,
                "job_ids": ids,
                "searched_at": now,
            }
            self._save(data)
            return self.list_jobs(user_id=user_id)

    def update_status(self, job_id: str, status: str, user_id: int = 1) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._load()
            record = data["jobs"].get(job_id)
            if not record or int(record.get("user_id", 1)) != int(user_id):
                return None
            record["discovery_status"] = status
            record["updated_at"] = self._now()
            data["jobs"][job_id] = record
            self._save(data)
            job = dict(record.get("job") or {})
            job["id"] = job_id
            job["discovery_status"] = status
            return job

    def mark_applied_by_url(self, url: str, user_id: int = 1) -> None:
        if not url:
            return
        target = url.strip().lower()
        with self._lock:
            data = self._load()
            changed = False
            for key, record in data["jobs"].items():
                if int(record.get("user_id", 1)) != int(user_id):
                    continue
                job_url = (record.get("job") or {}).get("url", "").strip().lower()
                if job_url == target:
                    record["discovery_status"] = "applied"
                    record["updated_at"] = self._now()
                    data["jobs"][key] = record
                    changed = True
            if changed:
                self._save(data)


discovery_store = DiscoveryStore()
