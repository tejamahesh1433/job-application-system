"""
LLM Management Router
Endpoints for Ollama model status, switching, and pulling new models.
"""
from fastapi import APIRouter
from typing import Dict, Any, List
import asyncio
import logging
import requests as req_lib

from config import settings
from utils.llm_helper import llm_helper
from utils.usage_ledger import usage_ledger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["llm"])

RECOMMENDED_MODELS = [
    {
        "name": "mistral",
        "display": "Mistral 7B",
        "size": "4.1 GB",
        "speed": "Fast",
        "quality": "Great",
        "best_for": "All tasks — best balance of speed & quality",
        "pull_cmd": "ollama pull mistral",
        "vram_gb": 5,
    },
    {
        "name": "llama3.2:3b",
        "display": "Llama 3.2 3B",
        "size": "2.0 GB",
        "speed": "Very Fast",
        "quality": "Good",
        "best_for": "Fast JSON extraction, quick analysis",
        "pull_cmd": "ollama pull llama3.2:3b",
        "vram_gb": 3,
    },
    {
        "name": "qwen2.5:7b",
        "display": "Qwen 2.5 7B",
        "size": "4.7 GB",
        "speed": "Fast",
        "quality": "Excellent",
        "best_for": "Technical roles, complex reasoning",
        "pull_cmd": "ollama pull qwen2.5:7b",
        "vram_gb": 6,
    },
    {
        "name": "llama3.1:8b",
        "display": "Llama 3.1 8B",
        "size": "4.9 GB",
        "speed": "Medium",
        "quality": "Excellent",
        "best_for": "Cover letters, detailed writing",
        "pull_cmd": "ollama pull llama3.1:8b",
        "vram_gb": 6,
    },
    {
        "name": "gemma2:9b",
        "display": "Gemma 2 9B",
        "size": "5.5 GB",
        "speed": "Medium",
        "quality": "Excellent",
        "best_for": "Structured data, JSON accuracy",
        "pull_cmd": "ollama pull gemma2:9b",
        "vram_gb": 7,
    },
]


@router.get("/status")
async def get_llm_status() -> Dict[str, Any]:
    """Full LLM provider status — active model, installed models, cost info."""
    ollama_ok = False
    installed = []
    active_model = settings.ollama_model

    try:
        r = req_lib.get(f"{settings.ollama_base_url}/api/tags", timeout=1.5)
        if r.ok:
            ollama_ok = True
            raw = r.json().get("models", [])
            # Re-init helper to pick up any newly pulled models
            llm_helper._ollama_models = [m["name"] for m in raw]
            active_model = llm_helper.get_best_model()
            installed = [
                {
                    "name": m["name"],
                    "size_gb": round(m.get("size", 0) / 1_000_000_000, 1),
                    "is_active": m["name"] == active_model,
                }
                for m in raw
            ]
    except Exception as e:
        logger.warning(f"Ollama status check: {e}")

    active_provider = (
        "ollama" if ollama_ok
        else "anthropic" if settings.anthropic_api_key
        else "openai" if settings.openai_api_key
        else "none"
    )

    usage = usage_ledger.monthly_summary()
    target_total = (
        settings.jsearch_monthly_budget_usd
        + settings.claude_haiku_monthly_budget_usd
        + settings.claude_sonnet_monthly_budget_usd
        + settings.openai_monthly_budget_usd
    )

    return {
        "ollama": {
            "available": ollama_ok,
            "url": settings.ollama_base_url,
            "active_model": active_model,
            "installed": installed,
            "model_count": len(installed),
        },
        "cloud": {
            "anthropic_configured": bool(settings.anthropic_api_key),
            "openai_configured": bool(settings.openai_api_key),
            "haiku_model": settings.claude_haiku_model,
            "sonnet_model": settings.claude_sonnet_model,
            "openai_fallback_model": settings.openai_fallback_model,
        },
        "active_provider": active_provider,
        "routing": {
            "job_discovery": "JSearch with cache and request caps",
            "job_analysis": "Ollama",
            "cover_letters": "Ollama",
            "form_answers": "Ollama",
            "resume_tailoring": "Claude Haiku",
            "interview_prep": "Claude Sonnet",
            "fallback": "OpenAI",
        },
        "budget": {
            "target_monthly_total_usd": target_total,
            "jsearch_usd": settings.jsearch_monthly_budget_usd,
            "claude_haiku_usd": settings.claude_haiku_monthly_budget_usd,
            "claude_sonnet_usd": settings.claude_sonnet_monthly_budget_usd,
            "openai_fallback_usd": settings.openai_monthly_budget_usd,
        },
        "limits": {
            "applications_per_day": settings.applications_per_day,
            "jsearch_per_minute_request_cap": settings.jsearch_per_minute_request_cap,
            "jsearch_daily_request_cap": settings.jsearch_daily_request_cap,
            "jsearch_monthly_request_cap": settings.jsearch_monthly_request_cap,
        },
        "usage": usage,
        "cost_estimate": f"Target cap: ~${target_total:.0f}/month with 30 applications/day routing",
        "recommended": RECOMMENDED_MODELS,
    }


@router.post("/set-model")
async def set_active_model(model_name: str) -> Dict[str, Any]:
    """Switch active Ollama model for all future requests."""
    # Update the in-memory helper so it uses the chosen model next call
    if not llm_helper.ollama_available:
        return {"success": False, "message": "Ollama is not running"}

    installed_names = [m["name"] for m in llm_helper.get_installed_models()]
    if model_name not in installed_names:
        return {"success": False, "message": f"Model '{model_name}' not installed. Pull it first."}

    llm_helper._ollama_models = installed_names
    try:
        llm_helper.set_active_model(model_name)
    except ValueError as e:
        return {"success": False, "message": str(e)}
    logger.info(f"Active Ollama model switched to: {model_name}")
    return {"success": True, "active_model": model_name, "message": f"Now using {model_name}"}


@router.post("/pull")
async def pull_model(model_name: str) -> Dict[str, Any]:
    """Download an Ollama model (runs in background for large models)."""
    if not model_name.strip():
        return {"success": False, "message": "model_name is required"}

    def _do_pull():
        try:
            r = req_lib.post(
                f"{settings.ollama_base_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=600,
                headers={"User-Agent": "APEX/1.0"},
            )
            return r.ok, r.text[:300] if not r.ok else ""
        except req_lib.Timeout:
            return True, "timeout_ok"  # large download still running
        except Exception as e:
            return False, str(e)

    ok, detail = await asyncio.to_thread(_do_pull)

    if ok:
        # Refresh cached model list
        llm_helper._ollama_models = None
        llm_helper.ollama_available = llm_helper._check_ollama()
        return {
            "success": True,
            "model": model_name,
            "message": f"✓ {model_name} pulled successfully" if detail != "timeout_ok"
                       else f"⏳ {model_name} is downloading in background (large model)...",
        }
    return {"success": False, "model": model_name, "message": f"Pull failed: {detail}"}


@router.delete("/model")
async def delete_model(model_name: str) -> Dict[str, Any]:
    """Remove an installed Ollama model to free disk space."""
    try:
        r = req_lib.delete(
            f"{settings.ollama_base_url}/api/delete",
            json={"name": model_name},
            timeout=15,
        )
        if r.ok:
            llm_helper._ollama_models = None
            if llm_helper._active_ollama_model == model_name:
                llm_helper._active_ollama_model = None
                llm_helper._save_active_model(None)
            llm_helper.ollama_available = llm_helper._check_ollama()
            return {"success": True, "message": f"Model '{model_name}' removed"}
        return {"success": False, "message": r.text[:200]}
    except Exception as e:
        return {"success": False, "message": str(e)}
