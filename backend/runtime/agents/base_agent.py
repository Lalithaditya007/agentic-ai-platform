"""
Base Agent Class
=================
All runtime agents inherit from this base class.
Provides:
  - Consistent LLM access with automatic provider fallback
  - Rate-limit retry with exponential backoff
  - Timing & metrics tracking
  - Error handling with graceful degradation
  - Capability registry access
  - Structured output logging
"""

import time
import json
import re
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime, timezone

from config import settings


# ── LLM Factory ───────────────────────────────────────────────────────────────

def _build_groq_llm(temperature: float = 0.3, model: str = None):
    """Build a Groq LLM client. Returns None if key is missing."""
    if not settings.GROQ_API_KEY:
        return None
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=model or settings.GROQ_MODEL,
        temperature=temperature,
        groq_api_key=settings.GROQ_API_KEY,
    )


def _build_gemini_llm(temperature: float = 0.3, model: str = None):
    """Build a Google Gemini LLM client. Returns None if key is missing."""
    if not settings.GOOGLE_API_KEY:
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=model or settings.GEMINI_MODEL,
        temperature=temperature,
        google_api_key=settings.GOOGLE_API_KEY,
    )


def _build_openai_llm(temperature: float = 0.3, model: str = None):
    """Build an OpenAI LLM client. Returns None if key is missing."""
    if not settings.OPENAI_API_KEY:
        return None
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model or "gpt-4o-mini",
        temperature=temperature,
        openai_api_key=settings.OPENAI_API_KEY,
    )


def _build_openrouter_llm(temperature: float = 0.3, model: str = None):
    """Build an OpenRouter LLM client. Returns None if key is missing."""
    if not settings.OPEN_ROUTER:
        return None
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPEN_ROUTER,
        model=model or settings.OPENROUTER_MODEL,
        temperature=temperature,
    )


_PROVIDER_BUILDERS = {
    "groq": _build_groq_llm,
    "google": _build_gemini_llm,
    "openai": _build_openai_llm,
    "openrouter": _build_openrouter_llm,
}

# Fallback order when primary provider fails or is rate-limited
_FALLBACK_ORDER = ["openrouter", "groq", "google", "openai"]


def get_llm_for_provider(provider: str, temperature: float = 0.3, model: str = None):
    """Build an LLM for a specific provider name."""
    builder = _PROVIDER_BUILDERS.get(provider)
    if builder:
        # Only pass explicit model override for OpenRouter to avoid 404s on fallback
        if provider == "openrouter" and model:
            return builder(temperature=temperature, model=model)
        return builder(temperature=temperature, model=None)
    return None


def get_primary_llm(temperature: float = 0.3, model: str = None):
    """
    Return the configured primary LLM.
    Falls back through groq → google → openai if the primary provider has no key.
    """
    # Try primary provider first
    primary = _PROVIDER_BUILDERS.get(settings.LLM_PROVIDER)
    if primary:
        if settings.LLM_PROVIDER == "openrouter" and model:
            llm = primary(temperature=temperature, model=model)
        else:
            llm = primary(temperature=temperature, model=None)
        if llm:
            return llm

    # Try fallbacks
    for provider in _FALLBACK_ORDER:
        if provider == settings.LLM_PROVIDER:
            continue  # Already tried
        llm = get_llm_for_provider(provider, temperature, None)
        if llm:
            print(f"[LLM] Primary provider '{settings.LLM_PROVIDER}' unavailable — using '{provider}' as fallback")
            return llm

    raise RuntimeError(
        "No LLM configured. Set at least one of: GROQ_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY in .env"
    )


def _is_rate_limit_error(e: Exception) -> bool:
    """Detect rate limit / quota errors from any provider."""
    msg = str(e).lower()
    return any(kw in msg for kw in [
        "rate limit", "ratelimit", "rate_limit",
        "429", "quota", "too many requests",
        "resource_exhausted", "tokens per minute",
    ])


async def invoke_with_retry(
    prompt_messages: list,
    temperature: float = 0.3,
    max_retries: int = 3,
    model: str = None,
) -> Any:
    """
    Invoke the LLM with automatic retry + exponential backoff on rate limits.
    Falls back to the next provider if all retries fail.
    """
    from langchain_core.messages import HumanMessage

    # Build the provider list: primary first, then fallbacks
    providers_to_try = [settings.LLM_PROVIDER] + [
        p for p in _FALLBACK_ORDER if p != settings.LLM_PROVIDER
    ]

    last_error = None
    for provider in providers_to_try:
        llm = get_llm_for_provider(provider, temperature, model)
        if not llm:
            continue  # Skip — no key configured

        for attempt in range(1, max_retries + 1):
            try:
                result = await llm.ainvoke(prompt_messages)
                return result
            except Exception as e:
                last_error = e
                if _is_rate_limit_error(e):
                    wait_secs = 2 ** attempt  # 2, 4, 8 seconds
                    print(
                        f"[LLM] Rate limit on '{provider}' "
                        f"(attempt {attempt}/{max_retries}) — waiting {wait_secs}s..."
                    )
                    await asyncio.sleep(wait_secs)
                else:
                    print(f"[LLM] Non-rate-limit error on '{provider}': {e}")
                    break  # Non-retryable — try next provider

        # All retries for this provider exhausted — try next
        print(f"[LLM] Exhausted retries on '{provider}' — trying next provider...")

    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}"
    )


# ── Base Agent ────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base class for all runtime agents in the platform.
    
    Subclasses must implement:
        run(state: dict) -> dict   — main execution logic
    """

    agent_name: str = "base_agent"
    llm_model: str = None  # Deprecated: use settings.GROQ_MODEL / settings.GEMINI_MODEL

    def __init__(self, icp_config: dict, agent_spec: dict = None, capabilities: dict = None):
        self.icp_config = icp_config
        self.agent_spec = agent_spec or {}
        self.capabilities = capabilities or {}
        self._start_time: float | None = None
        self._metrics: dict = {}

    # ── LLM Access ────────────────────────────────────────────────────────────

    def get_llm(self, model: str = None, temperature: float = 0.3):
        """
        Get the appropriate LLM based on platform config.
        Falls back automatically if the primary provider has no key.
        """
        return get_primary_llm(temperature=temperature, model=model or self.llm_model)

    # ── JSON Parsing ─────────────────────────────────────────────────────────

    def parse_json_response(self, raw: str) -> Any:
        """Strip markdown fences and parse JSON from LLM response."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())
        return json.loads(cleaned.strip())

    async def ask_llm_for_json(self, prompt: str, model: str = None) -> Any:
        """
        Send a prompt to the LLM and parse the JSON response.
        Automatically retries on rate limits and falls back across providers.
        """
        from langchain_core.messages import HumanMessage
        result = await invoke_with_retry(
            prompt_messages=[HumanMessage(content=prompt)],
            temperature=0.3,
            model=model or self.llm_model,
        )
        raw = result.content if hasattr(result, "content") else str(result)
        return self.parse_json_response(raw)

    # ── Metrics ───────────────────────────────────────────────────────────────

    def start_timer(self):
        self._start_time = time.time()

    def get_duration_ms(self) -> int:
        if self._start_time is None:
            return 0
        return int((time.time() - self._start_time) * 1000)

    def build_metric(
        self,
        status: str,
        tokens_used: int = 0,
        cost_estimate: float = 0.0,
        output_summary: str = "",
    ) -> dict:
        return {
            "agent_name": self.agent_name,
            "status": status,
            "duration_ms": self.get_duration_ms(),
            "tokens_used": tokens_used,
            "cost_estimate": cost_estimate,
            "output_summary": output_summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Web Search ────────────────────────────────────────────────────────────

    async def web_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Perform a web search using Tavily."""
        if not settings.TAVILY_API_KEY:
            print(f"[{self.agent_name}] WARN: No Tavily API key — skipping web search")
            return []
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            response = client.search(query=query, max_results=max_results)
            return response.get("results", [])
        except Exception as e:
            print(f"[{self.agent_name}] Web search failed: {e}")
            return []

    # ── Abstract Interface ────────────────────────────────────────────────────

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """
        Execute the agent's main logic.
        
        Args:
            state: Current PlatformState dict
            
        Returns:
            dict of state updates (partial state)
        """
        ...

    async def execute(self, state: dict) -> dict:
        """
        Wrapper around run() that adds timing, error handling, and metrics.
        Use this instead of calling run() directly.
        """
        self.start_timer()
        print(f"[{self.agent_name}] Starting execution")

        try:
            result = await self.run(state)
            duration = self.get_duration_ms()
            print(f"[{self.agent_name}] Completed in {duration}ms")
            return result

        except Exception as e:
            duration = self.get_duration_ms()
            print(f"[{self.agent_name}] ERROR after {duration}ms: {e}")

            existing_errors = state.get("errors", [])
            existing_metrics = state.get("agent_metrics", [])

            return {
                "errors": existing_errors + [{
                    "agent": self.agent_name,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
                "agent_metrics": existing_metrics + [
                    self.build_metric(
                        status="failure",
                        output_summary=f"Error: {str(e)[:200]}",
                    )
                ],
            }
