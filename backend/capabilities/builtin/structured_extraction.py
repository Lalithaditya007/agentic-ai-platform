"""
LLM Structured Extraction Capability
======================================
Uses the configured LLM to extract structured data from raw text.
"""

import json
import re
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
        return bool(settings.GOOGLE_API_KEY or settings.OPENAI_API_KEY)

    def _get_llm(self):
        if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model="llama-3.3-70b-versatile",
                temperature=0.0,
                groq_api_key=settings.GROQ_API_KEY,
            )
        elif settings.LLM_PROVIDER == "google" and settings.GOOGLE_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.0,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        elif settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
        return None

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {"text": str, "schema": str (JSON description), "prompt_prefix": str (optional)}
        """
        text = input.get("text", "")
        schema = input.get("schema", "")
        prompt_prefix = input.get("prompt_prefix", "Extract structured information from the following text.")

        llm = self._get_llm()
        if not llm:
            return {"success": False, "data": {}, "source": "llm_extraction", "error": "No LLM configured"}

        prompt = f"""{prompt_prefix}

Schema to extract (return ONLY valid JSON matching this schema):
{schema}

Text to process:
{text[:3000]}

Return ONLY valid JSON. No markdown fences, no explanation."""

        try:
            from langchain_core.messages import HumanMessage
            result = llm.invoke([HumanMessage(content=prompt)])
            raw = result.content if hasattr(result, "content") else str(result)
            # Clean markdown fences
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned.strip())
            parsed = json.loads(cleaned.strip())
            return {"success": True, "data": parsed, "source": "llm_extraction"}
        except Exception as e:
            return {"success": False, "data": {}, "source": "llm_extraction", "error": str(e)}
