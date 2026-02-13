"""Three-tier decision engine — the brain of GeoFix.

Routes each detected error through:
  Tier 1: Rule-based (deterministic, fast)
  Tier 2: LLM reasoning (ambiguous cases)
  Tier 3: Human review (low confidence)
"""

from __future__ import annotations

import logging
from typing import Optional

from geofix.core.config import GeoFixConfig, DEFAULT_CONFIG
from geofix.core.models import (
    DetectedError,
    FeatureMetadata,
    FixStrategy,
    FixTier,
)
from geofix.decision.rules import RuleSet, build_default_ruleset
from geofix.decision.llm_reasoner import LLMReasoner

logger = logging.getLogger("geofix.decision.engine")


class DecisionEngine:
    """Three-tier decision system: Rules → LLM → Human.

    Usage::

        engine = DecisionEngine()
        strategy = engine.decide(error, metadata)
        if strategy.tier == FixTier.HUMAN_REVIEW:
            # present to user for approval
        else:
            result = fix_registry.get(strategy.fix_type).apply(strategy)
    """

    def __init__(
        self,
        config: GeoFixConfig = DEFAULT_CONFIG,
        rules: Optional[RuleSet] = None,
        llm: Optional[LLMReasoner] = None,
    ):
        self.config = config
        self.rules = rules or build_default_ruleset()
        self.llm = llm or LLMReasoner(config.llm)

    def decide(
        self,
        error: DetectedError,
        metadata: dict[str, FeatureMetadata],
        rules_only: bool = False,
    ) -> FixStrategy:
        """Route an error through the decision pipeline.

        Parameters
        ----------
        error : DetectedError
            The error to decide about.
        metadata : dict[str, FeatureMetadata]
            Feature metadata keyed by feature ID.
        rules_only : bool
            If True, skip the LLM tier (Tier 2). Useful for batch
            operations or when the API is rate-limited.

        Returns
        -------
        FixStrategy
            Always returns a strategy. If no tier can decide with
            sufficient confidence, returns a ``HUMAN_REVIEW`` strategy.
        """
        # ── Tier 1: Rules ───────────────────────────────────────────
        strategy = self.rules.evaluate(error, metadata)
        if strategy and strategy.confidence >= self.config.decision.auto_fix_min:
            logger.info(
                "[Tier1] Auto-fix: %s for %s (conf=%.2f)",
                strategy.fix_type,
                error.error_id,
                strategy.confidence,
            )
            return strategy

        # ── Tier 2: LLM (skip if rules_only) ───────────────────────
        llm_strategy = None
        if not rules_only:
            try:
                llm_strategy = self.llm.reason(error, metadata, context=strategy)
                if (
                    llm_strategy
                    and llm_strategy.confidence >= self.config.decision.llm_fix_min
                ):
                    logger.info(
                        "[Tier2] LLM fix: %s for %s (conf=%.2f)",
                        llm_strategy.fix_type,
                        error.error_id,
                        llm_strategy.confidence,
                    )
                    return llm_strategy
            except Exception as exc:
                logger.warning("[Tier2] LLM reasoning failed: %s", exc)

        # ── Tier 3: Human Review ────────────────────────────────────
        best = llm_strategy or strategy
        logger.info(
            "[Tier3] Human review needed for %s (best_conf=%.2f)",
            error.error_id,
            best.confidence if best else 0.0,
        )
        return FixStrategy(
            error=error,
            fix_type="human_review",
            tier=FixTier.HUMAN_REVIEW,
            confidence=best.confidence if best else 0.0,
            reasoning=(
                best.reasoning + " — confidence too low for auto-fix."
                if best
                else "No rule or LLM recommendation available."
            ),
        )

    def decide_batch(
        self,
        errors: list[DetectedError],
        metadata: dict[str, FeatureMetadata],
    ) -> list[FixStrategy]:
        """Decide fix strategies for a list of errors."""
        return [self.decide(e, metadata) for e in errors]
