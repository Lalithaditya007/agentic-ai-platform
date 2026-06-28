"""
LLM Structured Extraction Capability
======================================
Uses the configured LLM to extract structured data from raw text.
Automatically uses the platform's provider fallback chain (Groq → Gemini → OpenAI).
"""

import json
import re
import asyncio
from typing import Any
from capabilities.base import CapabilityPlugin
from config import settings


class LLMStructuredExtractionPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "data_processing.structured_extraction"

    @property
    def display_name(self) -> str:
        return "LLM Structured Data Extraction"

    @property
    def description(self) -> str:
        return "Use an LLM to extract structured JSON data from raw text content."

    def health_check(self) -> bool:
        return bool(
            settings.GROQ_API_KEY
            or settings.GOOGLE_API_KEY
            or settings.OPENAI_API_KEY
        )

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"text": str, "schema": str (JSON description), "prompt_prefix": str (optional)}
        """
        text = input.get("text", "")
        schema = input.get("schema", "")
        prompt_prefix = input.get("prompt_prefix", "Extract structured information from the following text.")

        prompt = f"""{prompt_prefix}

Schema to extract (return ONLY valid JSON matching this schema):
{schema}

Text to process:
{text[:3000]}

Return ONLY valid JSON. No markdown fences, no explanation."""

        try:
            from langchain_core.messages import HumanMessage
            from runtime.agents.base_agent import invoke_with_retry

            # Run the async invoke_with_retry in a sync context
            result = asyncio.run(invoke_with_retry([HumanMessage(content=prompt)], temperature=0.0))
            raw = result.content if hasattr(result, "content") else str(result)
            # Clean markdown fences
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned.strip())
            parsed = json.loads(cleaned.strip())
            return {"success": True, "data": parsed, "source": "llm_extraction"}
        except Exception as e:
            return {"success": False, "data": {}, "source": "llm_extraction", "error": str(e)}
