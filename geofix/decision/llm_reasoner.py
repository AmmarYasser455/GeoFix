"""LLM-based reasoning — Tier 2 of the decision engine.

Used for ambiguous cases where rules can't decide (confidence too low
or no matching rule). Sends error context + feature metadata to the LLM
and parses a structured fix recommendation.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from geofix.core.config import LLMConfig
from geofix.core.exceptions import LLMError
from geofix.core.models import (
    DetectedError,
    FeatureMetadata,
    FixStrategy,
    FixTier,
)

logger = logging.getLogger("geofix.decision.llm")

SYSTEM_PROMPT = """\
You are GeoFix, an expert geospatial data quality engineer.

You are given a detected spatial error with metadata about the affected
features. Your job is to recommend the best fix strategy.

Available fix types: snap, trim, merge, delete, make_valid, simplify, clip, nudge

Respond ONLY with valid JSON in this format:
{
  "fix_type": "<one of the fix types above>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one-line explanation>",
  "parameters": {}
}

Consider:
- Feature accuracy (lower accuracy_m = more positional trust)
- Source reliability (survey > digitized > osm > unknown)
- Overlap magnitude (ratio, area)
- Risk of the fix (prefer conservative actions)
"""


class LLMReasoner:
    """Sends error context to an LLM for fix recommendation.

    Uses the Anthropic Claude API via langchain-anthropic.

    If the LLM call fails or returns unparseable output, returns None
    (which causes the decision engine to escalate to human review).
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._llm = None

    def _get_llm(self):
        """Lazy-init the LLM client based on config.provider."""
        if self._llm is None:
            provider = getattr(self.config, "provider", "ollama")
            if provider == "ollama":
                try:
                    from langchain_ollama import ChatOllama

                    self._llm = ChatOllama(
                        model=self.config.model,
                        temperature=self.config.temperature,
                        base_url=getattr(self.config, "ollama_base_url", "http://localhost:11434"),
                    )
                except ImportError:
                    raise LLMError(
                        "langchain-ollama not installed. "
                        "Run: pip install langchain-ollama"
                    )
            else:
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI

                    self._llm = ChatGoogleGenerativeAI(
                        model=self.config.model,
                        temperature=self.config.temperature,
                        max_output_tokens=self.config.max_tokens,
                    )
                except ImportError:
                    raise LLMError(
                        "langchain-google-genai not installed. "
                        "Run: pip install langchain-google-genai"
                    )
        return self._llm

    def reason(
        self,
        error: DetectedError,
        metadata: dict[str, FeatureMetadata],
        context: Optional[FixStrategy] = None,
    ) -> Optional[FixStrategy]:
        """Ask the LLM for a fix recommendation.

        Parameters
        ----------
        error : DetectedError
            The error to reason about.
        metadata : dict
            Feature metadata keyed by feature ID.
        context : FixStrategy, optional
            A partially-evaluated strategy from the rule engine
            (used to show the LLM what rules already considered).

        Returns
        -------
        FixStrategy or None
            The LLM's recommendation, or None if it fails.
        """
        prompt = self._build_prompt(error, metadata, context)

        try:
            llm = self._get_llm()
            from langchain_core.messages import SystemMessage, HumanMessage

            response = llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            return self._parse_response(response.content, error)

        except LLMError:
            raise
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None

    def _build_prompt(
        self,
        error: DetectedError,
        metadata: dict[str, FeatureMetadata],
        context: Optional[FixStrategy],
    ) -> str:
        """Construct the user prompt with error + metadata context."""
        parts = [
            "## Detected Error",
            f"- Type: {error.error_type}",
            f"- Severity: {error.severity.value}",
        ]

        for key, val in error.properties.items():
            parts.append(f"- {key}: {val}")

        parts.append("\n## Affected Features")
        for fid in error.affected_features:
            m = metadata.get(fid, FeatureMetadata(feature_id=fid))
            parts.append(
                f"- Feature {fid}: source={m.source}, "
                f"accuracy={m.accuracy_m}m, confidence={m.confidence}, "
                f"date={m.source_date}"
            )

        if context:
            parts.append(f"\n## Rule Engine Attempt")
            parts.append(f"- Suggested: {context.fix_type}")
            parts.append(f"- Confidence: {context.confidence:.2f}")
            parts.append(f"- Reasoning: {context.reasoning}")
            parts.append("The confidence was too low for auto-fix.")

        parts.append("\nWhat fix do you recommend?")
        return "\n".join(parts)

    def _parse_response(
        self, content: str, error: DetectedError
    ) -> Optional[FixStrategy]:
        """Parse the LLM's JSON response into a FixStrategy."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            text = content.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)

            return FixStrategy(
                error=error,
                fix_type=data.get("fix_type", "human_review"),
                tier=FixTier.LLM_REASONING,
                confidence=float(data.get("confidence", 0.5)),
                parameters=data.get("parameters", {}),
                reasoning=data.get("reasoning", "LLM recommendation"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Cannot parse LLM response: %s — %s", exc, content[:200])
            return None
