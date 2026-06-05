"""
Usage ledger for paid APIs.

Stores lightweight JSONL records under logs/ so the app can enforce daily and
monthly guardrails without needing a database migration.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / settings.logs_dir / "usage_ledger.jsonl"


class UsageLimitExceeded(Exception):
    """Raised when a configured daily/monthly API cap would be exceeded."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date_key(dt: Optional[datetime] = None) -> str:
    return (dt or _utc_now()).strftime("%Y-%m-%d")


def _month_key(dt: Optional[datetime] = None) -> str:
    return (dt or _utc_now()).strftime("%Y-%m")


class UsageLedger:
    """Append-only local usage tracker for JSearch and cloud LLM calls."""

    def __init__(self, path: Path = LOG_PATH):
        self.path = path

    def record(
        self,
        service: str,
        operation: str,
        provider: str,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": _utc_now().isoformat(),
            "date": _date_key(),
            "month": _month_key(),
            "service": service,
            "operation": operation,
            "provider": provider,
            "model": model,
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cost_usd": round(float(cost_usd or 0.0), 6),
            "metadata": metadata or {},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
        return entry

    def iter_entries(self) -> Iterable[Dict[str, Any]]:
        if not self.path.exists():
            return []

        entries = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def count(
        self,
        service: str,
        operation: Optional[str] = None,
        date: Optional[str] = None,
        month: Optional[str] = None,
    ) -> int:
        count = 0
        for entry in self.iter_entries():
            if entry.get("service") != service:
                continue
            if operation and entry.get("operation") != operation:
                continue
            if date and entry.get("date") != date:
                continue
            if month and entry.get("month") != month:
                continue
            count += 1
        return count

    def count_since(
        self,
        service: str,
        operation: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        if since is None:
            return self.count(service=service, operation=operation)

        count = 0
        for entry in self.iter_entries():
            if entry.get("service") != service:
                continue
            if operation and entry.get("operation") != operation:
                continue
            try:
                timestamp = datetime.fromisoformat(str(entry.get("timestamp", "")))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if timestamp >= since:
                count += 1
        return count

    def cost(
        self,
        provider: Optional[str] = None,
        service: Optional[str] = None,
        month: Optional[str] = None,
    ) -> float:
        total = 0.0
        for entry in self.iter_entries():
            if provider and entry.get("provider") != provider:
                continue
            if service and entry.get("service") != service:
                continue
            if month and entry.get("month") != month:
                continue
            total += float(entry.get("cost_usd") or 0.0)
        return round(total, 6)

    def ensure_request_capacity(
        self,
        service: str,
        operation: str,
        daily_cap: int,
        monthly_cap: int,
        per_minute_cap: Optional[int] = None,
        amount: int = 1,
    ) -> None:
        if per_minute_cap is not None and per_minute_cap > 0:
            minute_count = self.count_since(
                service=service,
                operation=operation,
                since=_utc_now() - timedelta(minutes=1),
            )
            if minute_count + amount > per_minute_cap:
                raise UsageLimitExceeded(
                    f"{service} rate limit reached: {minute_count}/{per_minute_cap} {operation} requests used in the last minute."
                )

        today_count = self.count(service=service, operation=operation, date=_date_key())
        month_count = self.count(service=service, operation=operation, month=_month_key())
        if today_count + amount > daily_cap:
            raise UsageLimitExceeded(
                f"{service} daily cap reached: {today_count}/{daily_cap} {operation} requests used today."
            )
        if month_count + amount > monthly_cap:
            raise UsageLimitExceeded(
                f"{service} monthly cap reached: {month_count}/{monthly_cap} {operation} requests used this month."
            )

    def ensure_monthly_cost_capacity(
        self,
        provider: str,
        monthly_budget_usd: float,
        next_cost_usd: float = 0.0,
    ) -> None:
        used = self.cost(provider=provider, month=_month_key())
        if used + next_cost_usd > monthly_budget_usd:
            raise UsageLimitExceeded(
                f"{provider} monthly budget reached: ${used:.2f}/${monthly_budget_usd:.2f} used this month."
            )

    def monthly_summary(self) -> Dict[str, Any]:
        month = _month_key()
        jsearch_month = self.count("jsearch", "request", month=month)
        jsearch_today = self.count("jsearch", "request", date=_date_key())
        jsearch_minute = self.count_since(
            "jsearch",
            "request",
            since=_utc_now() - timedelta(minutes=1),
        )
        haiku_cost = self.cost(provider="claude_haiku", month=month)
        sonnet_cost = self.cost(provider="claude", month=month)
        openai_cost = self.cost(provider="openai", month=month)
        return {
            "month": month,
            "jsearch": {
                "requests": jsearch_month,
                "monthly_cap": settings.jsearch_monthly_request_cap,
                "monthly_remaining": max(settings.jsearch_monthly_request_cap - jsearch_month, 0),
                "per_minute_requests": jsearch_minute,
                "per_minute_cap": settings.jsearch_per_minute_request_cap,
                "per_minute_remaining": max(settings.jsearch_per_minute_request_cap - jsearch_minute, 0),
                "estimated_plan_cost_usd": settings.jsearch_monthly_budget_usd,
            },
            "cloud": {
                "claude_haiku_cost_usd": haiku_cost,
                "claude_haiku_budget_usd": settings.claude_haiku_monthly_budget_usd,
                "claude_haiku_remaining_usd": max(settings.claude_haiku_monthly_budget_usd - haiku_cost, 0),
                "claude_sonnet_cost_usd": sonnet_cost,
                "claude_sonnet_budget_usd": settings.claude_sonnet_monthly_budget_usd,
                "claude_sonnet_remaining_usd": max(settings.claude_sonnet_monthly_budget_usd - sonnet_cost, 0),
                "openai_cost_usd": openai_cost,
                "openai_budget_usd": settings.openai_monthly_budget_usd,
                "openai_remaining_usd": max(settings.openai_monthly_budget_usd - openai_cost, 0),
            },
            "daily": {
                "date": _date_key(),
                "jsearch_requests": jsearch_today,
                "jsearch_daily_cap": settings.jsearch_daily_request_cap,
                "jsearch_daily_remaining": max(settings.jsearch_daily_request_cap - jsearch_today, 0),
            },
        }


usage_ledger = UsageLedger()
