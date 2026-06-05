"""
LLM Helper - Unified interface for Claude, OpenAI, and Ollama
Handles all LLM interactions with fallback support

Provider routing strategy:
  OLLAMA        → Free local model (llama3.1:8b / mistral)
                  Use for: extraction, classification, matching, JSON parsing
  CLAUDE_HAIKU  → Claude Haiku ($0.80/$4 per MTok estimate)
                  Use for: high-match resume tailoring
  CLAUDE        → Claude Sonnet ($3/$15 per MTok estimate)
                  Use for: interview prep only
  OPENAI        → GPT-4 fallback (if no Anthropic key)
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum

from config import settings
from utils.usage_ledger import UsageLimitExceeded, usage_ledger

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_MODEL_PATH = PROJECT_ROOT / ".cache" / "active_ollama_model.txt"


class LLMProvider(Enum):
    """Available LLM providers"""
    OLLAMA        = "ollama"          # Free — local Ollama (extraction/classification)
    CLAUDE_HAIKU  = "claude_haiku"   # Cheap — Haiku 4.5 (medium quality tasks)
    CLAUDE        = "claude"          # Best  — Sonnet 4.6 (writing/interview prep)
    OPENAI        = "openai"          # Fallback if no Anthropic key


# ── Convenience aliases so agents can import cleanly ─────────────────────────
USE_OLLAMA  = LLMProvider.OLLAMA
USE_HAIKU   = LLMProvider.CLAUDE_HAIKU
USE_SONNET  = LLMProvider.CLAUDE


class LLMHelper:
    """Unified LLM interface — Ollama first (free), cloud APIs as fallback only."""

    # Preferred models in priority order (first match that's installed wins)
    MODEL_PRIORITY = [
        "llama3.1:8b", "llama3.1",
        "mistral:7b-instruct", "mistral:7b", "mistral",
        "qwen2.5:7b", "qwen2.5",
        "llama3.2:3b", "llama3.2",
        "gemma2:9b", "gemma2",
        "phi3:medium", "phi3",
        "codellama", "vicuna",
    ]

    def __init__(self):
        self.claude_available = bool(settings.anthropic_api_key)
        self.openai_available = bool(settings.openai_api_key)
        self._ollama_models: Optional[List[str]] = None  # cached
        self._active_ollama_model: Optional[str] = self._load_active_model()
        self.ollama_available = self._check_ollama()

    def _load_active_model(self) -> Optional[str]:
        try:
            value = ACTIVE_MODEL_PATH.read_text(encoding="utf-8").strip()
            return value or None
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Could not read active Ollama model preference: {e}")
            return None

    def _save_active_model(self, model_name: Optional[str]) -> None:
        try:
            ACTIVE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            if model_name:
                ACTIVE_MODEL_PATH.write_text(model_name, encoding="utf-8")
            elif ACTIVE_MODEL_PATH.exists():
                ACTIVE_MODEL_PATH.unlink()
        except Exception as e:
            logger.warning(f"Could not save active Ollama model preference: {e}")

    def _check_ollama(self) -> bool:
        """Check if Ollama is running and cache available models."""
        try:
            import requests
            response = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
            if response.status_code == 200:
                self._ollama_models = [
                    m["name"] for m in response.json().get("models", [])
                ]
                if self._ollama_models:
                    logger.info(f"Ollama online — {len(self._ollama_models)} model(s): {', '.join(self._ollama_models[:3])}")
                    return True
                logger.warning("Ollama running but no models installed. Run: ollama pull mistral")
                return False
            return False
        except Exception as e:
            logger.warning(f"Ollama not reachable at {settings.ollama_base_url}: {e}")
            return False

    def get_best_model(self) -> str:
        """Return the best available Ollama model name."""
        installed = self._ollama_models or []
        if self._active_ollama_model:
            if self._active_ollama_model in installed:
                return self._active_ollama_model
            self._active_ollama_model = None
            self._save_active_model(None)
        for preferred in self.MODEL_PRIORITY:
            for inst in installed:
                base = inst.split(":")[0]
                if preferred == inst or preferred == base or inst.startswith(preferred + ":"):
                    return inst
        # Fall back to anything installed, then config default
        return installed[0] if installed else settings.ollama_model

    def set_active_model(self, model_name: str) -> None:
        """Persist the user's selected Ollama model for this server process."""
        installed = self._ollama_models or []
        if model_name not in installed:
            raise ValueError(f"Model '{model_name}' is not installed")
        self._active_ollama_model = model_name
        self._save_active_model(model_name)

    def get_installed_models(self) -> List[Dict[str, Any]]:
        """Return list of installed Ollama models with metadata."""
        try:
            import requests
            r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
            if r.ok:
                models = r.json().get("models", [])
                best = self.get_best_model()
                return [
                    {
                        "name": m["name"],
                        "size_gb": round(m.get("size", 0) / 1_000_000_000, 1),
                        "modified_at": m.get("modified_at", ""),
                        "is_active": m["name"] == best,
                    }
                    for m in models
                ]
        except Exception:
            pass
        return []

    async def generate(
        self,
        prompt: str,
        provider: Optional[LLMProvider] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
        force_json: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate text using LLM with automatic fallback

        Args:
            prompt: The main prompt
            provider: Specific provider to use (None = auto-select best)
            temperature: Creativity level (0-1)
            max_tokens: Maximum response length
            system_prompt: Optional system instructions
            force_json: If True, attempt to parse response as JSON

        Returns:
            {
                "content": "Generated text",
                "provider": "claude|openai|ollama",
                "tokens_used": {"input": 100, "output": 50},
                "cost": 0.001,
                "error": None
            }
        """

        # Auto-select best provider
        if provider is None:
            provider = self._select_best_provider(prompt)

        # Try primary provider
        result = await self._try_generate(
            provider=provider,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            force_json=force_json,
        )

        # Fallback if primary fails
        if result.get("error") and provider != LLMProvider.OLLAMA:
            logger.warning(
                f"Primary provider {provider.value} failed, trying fallback"
            )
            fallback = LLMProvider.OLLAMA if self.ollama_available else LLMProvider.OPENAI
            result = await self._try_generate(
                provider=fallback,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                force_json=force_json,
            )

        return result

    def _select_best_provider(self, prompt: str, force_ollama: bool = False) -> LLMProvider:
        """Select provider — Ollama always first (free/local), cloud APIs only as fallback."""

        # 1. Ollama: always preferred — $0 cost, fully local, private
        if self.ollama_available:
            return LLMProvider.OLLAMA

        # 2. Cloud fallback — only when Ollama is not running
        if self.claude_available:
            logger.warning("Ollama offline — falling back to Anthropic Claude (paid API)")
            return LLMProvider.CLAUDE
        if self.openai_available:
            logger.warning("Ollama offline — falling back to OpenAI (paid API)")
            return LLMProvider.OPENAI

        raise Exception(
            "No LLM available. Start Ollama: 'ollama serve' then 'ollama pull mistral'. "
            "Or set ANTHROPIC_API_KEY / OPENAI_API_KEY in .env as fallback."
        )

    async def _try_generate(
        self,
        provider: LLMProvider,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        force_json: bool,
    ) -> Dict[str, Any]:
        """Try to generate using specific provider"""

        try:
            if provider == LLMProvider.CLAUDE:
                estimated_cost = self._estimate_claude_request_cost(
                    prompt, system_prompt, max_tokens, is_haiku=False
                )
                usage_ledger.ensure_monthly_cost_capacity(
                    "claude", settings.claude_sonnet_monthly_budget_usd, estimated_cost
                )
                return await self._generate_claude(
                    prompt, temperature, max_tokens, system_prompt, force_json,
                    model=settings.claude_sonnet_model,
                )
            elif provider == LLMProvider.CLAUDE_HAIKU:
                estimated_cost = self._estimate_claude_request_cost(
                    prompt, system_prompt, max_tokens, is_haiku=True
                )
                usage_ledger.ensure_monthly_cost_capacity(
                    "claude_haiku", settings.claude_haiku_monthly_budget_usd, estimated_cost
                )
                return await self._generate_claude(
                    prompt, temperature, max_tokens, system_prompt, force_json,
                    model=settings.claude_haiku_model,
                )
            elif provider == LLMProvider.OPENAI:
                estimated_cost = self._estimate_openai_request_cost(prompt, system_prompt, max_tokens)
                usage_ledger.ensure_monthly_cost_capacity(
                    "openai", settings.openai_monthly_budget_usd, estimated_cost
                )
                return await self._generate_openai(
                    prompt, temperature, max_tokens, system_prompt, force_json
                )
            elif provider == LLMProvider.OLLAMA:
                return await self._generate_ollama(
                    prompt, temperature, max_tokens, system_prompt, force_json
                )
        except UsageLimitExceeded as e:
            logger.warning(f"Budget guard blocked {provider.value}: {e}")
            return {"content": "", "provider": provider.value, "error": str(e), "budget_blocked": True}
        except Exception as e:
            logger.error(f"Error with {provider.value}: {e}")
            return {"content": "", "provider": provider.value, "error": str(e)}

    async def _generate_claude(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        force_json: bool,
        model: str = "claude-sonnet-4-6",
    ) -> Dict[str, Any]:
        """Generate using Anthropic Claude (Sonnet or Haiku)"""
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=settings.anthropic_api_key)

            messages = [{"role": "user", "content": prompt}]

            create_kwargs: Dict[str, Any] = dict(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )
            if system_prompt:
                create_kwargs["system"] = system_prompt

            response = client.messages.create(**create_kwargs)

            content = response.content[0].text
            if force_json:
                content = self._extract_json(content)

            is_haiku = "haiku" in model
            cost = self._calculate_claude_cost(
                response.usage.input_tokens, response.usage.output_tokens, is_haiku=is_haiku
            )
            logger.debug(f"Claude [{model}] — ${cost:.5f} ({response.usage.input_tokens}in / {response.usage.output_tokens}out tokens)")
            provider_name = "claude_haiku" if is_haiku else "claude"
            budget = (
                settings.claude_haiku_monthly_budget_usd
                if is_haiku else settings.claude_sonnet_monthly_budget_usd
            )
            usage_ledger.ensure_monthly_cost_capacity(provider_name, budget, cost)
            usage_ledger.record(
                service="llm",
                operation="generate",
                provider=provider_name,
                model=model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=cost,
            )

            return {
                "content": content,
                "provider": provider_name,
                "model": model,
                "tokens_used": {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
                "cost": cost,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Claude error: {e}")
            raise

    async def _generate_openai(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        force_json: bool,
    ) -> Dict[str, Any]:
        """Generate using OpenAI GPT"""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)

            messages = [{"role": "system", "content": system_prompt or "You are a helpful assistant."}]
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=settings.openai_fallback_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content
            if force_json:
                content = self._extract_json(content)

            cost = self._calculate_openai_cost(
                response.usage.prompt_tokens, response.usage.completion_tokens
            )
            usage_ledger.ensure_monthly_cost_capacity("openai", settings.openai_monthly_budget_usd, cost)
            usage_ledger.record(
                service="llm",
                operation="generate",
                provider="openai",
                model=settings.openai_fallback_model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                cost_usd=cost,
            )

            return {
                "content": content,
                "provider": "openai",
                "model": settings.openai_fallback_model,
                "tokens_used": {
                    "input": response.usage.prompt_tokens,
                    "output": response.usage.completion_tokens,
                },
                "cost": cost,
                "error": None,
            }
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            raise

    async def _generate_ollama(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        force_json: bool,
    ) -> Dict[str, Any]:
        """Generate using local Ollama — uses best available installed model."""
        try:
            import asyncio
            import requests

            model = self.get_best_model()

            # Build prompt — add JSON instruction if needed
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            if force_json and "json" not in full_prompt.lower()[:200]:
                full_prompt += "\n\nRespond with valid JSON only. No explanation, no markdown."

            payload = {
                "model": model,
                "prompt": full_prompt,
                "temperature": temperature,
                "num_predict": max_tokens,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "stop": [],
                },
            }

            def _post():
                resp = requests.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json=payload,
                    timeout=120,  # Give more time for complex prompts
                )
                if resp.status_code != 200:
                    raise Exception(f"Ollama returned {resp.status_code}: {resp.text[:200]}")
                return resp.json()

            result = await asyncio.to_thread(_post)
            content = result.get("response", "")

            if force_json:
                content = self._extract_json(content)

            logger.debug(f"Ollama [{model}] generated {result.get('eval_count', 0)} tokens (free)")

            return {
                "content": content,
                "provider": f"ollama/{model}",
                "model": model,
                "tokens_used": {
                    "input": result.get("prompt_eval_count", 0),
                    "output": result.get("eval_count", 0),
                },
                "cost": 0.0,  # Always $0 — fully local
                "error": None,
            }
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise

    @staticmethod
    def _calculate_claude_cost(input_tokens: int, output_tokens: int, is_haiku: bool = False) -> float:
        """Calculate Claude API cost estimate.
           Sonnet: $3/MTok input,    $15/MTok output
           Haiku:  $0.80/MTok input, $4/MTok output
        """
        if is_haiku:
            return (input_tokens * 0.8 + output_tokens * 4.0) / 1_000_000
        return (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000

    def _estimate_claude_request_cost(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        is_haiku: bool = False,
    ) -> float:
        """Conservative pre-call estimate so one request cannot exceed a budget cap."""
        input_tokens = max(1, int((len(prompt or "") + len(system_prompt or "")) / 4) + 200)
        output_tokens = max(1, int(max_tokens or 0))
        return self._calculate_claude_cost(input_tokens, output_tokens, is_haiku=is_haiku)

    @staticmethod
    def _calculate_openai_cost(input_tokens: int, output_tokens: int) -> float:
        """Calculate OpenAI GPT-4 cost"""
        # GPT-4 pricing: $0.03 per 1K input, $0.06 per 1K output
        return (input_tokens * 0.03 + output_tokens * 0.06) / 1000

    def _estimate_openai_request_cost(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
    ) -> float:
        input_tokens = max(1, int((len(prompt or "") + len(system_prompt or "")) / 4) + 200)
        output_tokens = max(1, int(max_tokens or 0))
        return self._calculate_openai_cost(input_tokens, output_tokens)

    @staticmethod
    def _extract_json(content: str) -> str:
        """Extract JSON from response, handling backticks and trailing text"""
        try:
            # 1. Look for Markdown JSON blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end != -1:
                    return content[start:end].strip()
            
            # 2. Look for any generic code blocks
            if "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end != -1:
                    return content[start:end].strip()
            
            # 3. Find first { and last }
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = content[start:end+1]
                # Validate it's actually JSON
                json.loads(json_str)
                return json_str
            
            return content
        except Exception as e:
            logger.warning(f"Could not extract JSON: {e}")
            return content


# Singleton instance
llm_helper = LLMHelper()


# Convenience functions
async def generate_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    provider: Optional[LLMProvider] = None,
) -> str:
    """Generate text and return just the content.

    Pass `provider` to force a specific model:
      generate_text(prompt, provider=USE_SONNET)   # Cover letters, emails
      generate_text(prompt, provider=USE_HAIKU)    # Resume tips, answers
      generate_text(prompt, provider=USE_OLLAMA)   # Extraction (free)
    """
    result = await llm_helper.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        provider=provider,
    )
    return result.get("content", "")


async def generate_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2000,
    provider: Optional[LLMProvider] = None,
) -> Dict[str, Any]:
    """Generate JSON response.

    Pass `provider` to force a specific model:
      generate_json(prompt, provider=USE_OLLAMA)   # Extraction, parsing (free)
      generate_json(prompt, provider=USE_HAIKU)    # Medium quality JSON tasks
    """
    result = await llm_helper.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        force_json=True,
        provider=provider,
    )
    try:
        return json.loads(result.get("content", "{}"))
    except json.JSONDecodeError:
        return {}
