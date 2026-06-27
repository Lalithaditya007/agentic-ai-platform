"""
Base Agent Class
=================
All runtime agents inherit from this base class.
Provides:
  - Consistent LLM access
  - Timing & metrics tracking
  - Error handling with graceful degradation
  - Capability registry access
  - Structured output logging
"""

import time
import json
import re
from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime, timezone

from config import settings


class BaseAgent(ABC):
    """
    Abstract base class for all runtime agents in the platform.
    
    Subclasses must implement:
        run(state: dict) -> dict   — main execution logic
    """

    agent_name: str = "base_agent"
    llm_model: str = "gemini-1.5-flash"

    def __init__(self, icp_config: dict, agent_spec: dict = None, capabilities: dict = None):
        self.icp_config = icp_config
        self.agent_spec = agent_spec or {}
        self.capabilities = capabilities or {}
        self._start_time: float | None = None
        self._metrics: dict = {}

    # ── LLM Access ────────────────────────────────────────────────────────────

    def get_llm(self, model: str = None, temperature: float = 0.3):
        """Get the appropriate LLM based on platform config."""
        model = model or self.llm_model

        if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model="llama-3.3-70b-versatile",
                temperature=temperature,
                groq_api_key=settings.GROQ_API_KEY,
            )
        elif settings.LLM_PROVIDER == "google" and settings.GOOGLE_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        elif settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=temperature)
        else:
            raise RuntimeError("No LLM configured. Set GROQ_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY.")

    # ── JSON Parsing ─────────────────────────────────────────────────────────

    def parse_json_response(self, raw: str) -> Any:
        """Strip markdown fences and parse JSON from LLM response."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())
        return json.loads(cleaned.strip())

    async def ask_llm_for_json(self, prompt: str, model: str = None) -> Any:
        """Send a prompt to the LLM and parse the JSON response."""
        from langchain_core.messages import HumanMessage
        llm = self.get_llm(model=model)
        result = await llm.ainvoke([HumanMessage(content=prompt)])
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
