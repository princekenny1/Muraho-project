"""
Safety Service — Pre-LLM and post-LLM content filtering.

Critical for Muraho Rwanda given the sensitive nature of genocide
memorial content. This is the FIRST line of defense — it runs
BEFORE the query reaches the LLM.

Layers:
  1. Blocklist: regex patterns for known harmful queries
  2. Pattern detection: genocide denial, ideology promotion
  3. Output filtering: post-generation check on LLM responses
  4. Audit logging: all flagged queries logged for human review
"""

import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Harmful Query Patterns ───────────────────────────────
# These patterns are checked BEFORE the query reaches the LLM.
# Queries matching these are blocked immediately.

GENOCIDE_DENIAL_PATTERNS = [
    r"genocide\s+(didn'?t|did\s+not|never)\s+happen",
    r"(hoax|fake|fabricat|invent|exaggerat)\w*\s+genocide",
    r"tutsi\s+(deserv|provok|caus|start)\w*",
    r"hutu\s+(innocent|victim|framed|falsely)",
    r"double\s+genocide",
    r"(justify|defend|support)\w*\s+(killing|massacre|violence)\s+against",
    r"genocide\s+ideology\s+is\s+(right|correct|true|justified)",
]

VIOLENCE_PROMOTION_PATTERNS = [
    r"how\s+to\s+(kill|harm|attack|destroy)",
    r"(weapons|bombs|poison)\s+(for|against|to\s+use)",
    r"ethnic\s+(cleansing|purification|superiority)",
    r"(hate|eliminate|exterminate)\s+(tutsi|hutu|twa)",
]

# Compile patterns for efficiency
DENIAL_RE = [re.compile(p, re.IGNORECASE) for p in GENOCIDE_DENIAL_PATTERNS]
VIOLENCE_RE = [re.compile(p, re.IGNORECASE) for p in VIOLENCE_PROMOTION_PATTERNS]


# ── Safe Responses ───────────────────────────────────────
# Respectful, educational responses for blocked queries.

SAFE_RESPONSES = {
    "genocide_denial": (
        "The 1994 Genocide against the Tutsi is a historically documented event "
        "recognized by the United Nations, the International Criminal Tribunal for "
        "Rwanda, and the international community. Over 1 million Tutsi were killed "
        "in approximately 100 days.\n\n"
        "Denial or minimization of the Genocide against the Tutsi is not only "
        "historically inaccurate but is also a criminal offense under Rwandan law.\n\n"
        "If you'd like to learn more about the history, I can share information from "
        "verified memorial archives and educational resources."
    ),
    "violence_promotion": (
        "I'm unable to provide information that promotes violence or hatred. "
        "Muraho Rwanda is dedicated to education, remembrance, and cultural "
        "understanding.\n\n"
        "If you're interested in learning about Rwanda's history, culture, or "
        "reconciliation journey, I'm here to help."
    ),
    "inappropriate_content": (
        "I'm not able to help with that request. As a cultural guide for Rwanda, "
        "I focus on helping visitors understand the country's rich history, culture, "
        "and heritage.\n\n"
        "Would you like to explore a story, museum, or cultural route instead?"
    ),
}


class SafetyService:
    """
    Content safety for Muraho Rwanda AI.
    Pre-query and post-generation filtering.
    """

    def __init__(self):
        self.audit_enabled = settings.ENABLE_AUDIT_LOG
        self.audit_path = Path(settings.AUDIT_LOG_PATH)

        # Ensure audit log directory exists
        if self.audit_enabled:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def check_query(self, query: str) -> dict:
        """
        Pre-LLM safety check. Runs BEFORE the query reaches the model.

        Returns:
            {
                "blocked": bool,
                "reason": str | None,
                "safe_response": str | None,
            }
        """
        # Check query length
        if len(query) > settings.SAFETY_MAX_QUERY_LENGTH:
            return {
                "blocked": True,
                "reason": "query_too_long",
                "safe_response": "Please keep your question shorter. I work best with concise questions.",
            }

        # Check genocide denial patterns
        for pattern in DENIAL_RE:
            if pattern.search(query):
                self._log_flagged(query, "genocide_denial")
                return {
                    "blocked": True,
                    "reason": "genocide_denial",
                    "safe_response": SAFE_RESPONSES["genocide_denial"],
                }

        # Check violence promotion patterns
        for pattern in VIOLENCE_RE:
            if pattern.search(query):
                self._log_flagged(query, "violence_promotion")
                return {
                    "blocked": True,
                    "reason": "violence_promotion",
                    "safe_response": SAFE_RESPONSES["violence_promotion"],
                }

        return {"blocked": False, "reason": None, "safe_response": None}

    def check_output(self, response: str) -> dict:
        """
        Post-LLM safety check. Runs on the model's generated response.
        Catches cases where the LLM generates problematic content
        despite safety instructions in the system prompt.

        Returns:
            {
                "flagged": bool,
                "reason": str | None,
                "filtered_response": str | None,
            }
        """
        response_lower = response.lower()

        # Check for genocide denial in output
        denial_signals = [
            "genocide did not happen",
            "genocide is a hoax",
            "double genocide",
            "tutsi provoked",
            "both sides were equally",
        ]
        for signal in denial_signals:
            if signal in response_lower:
                self._log_flagged(
                    response[:500], "output_genocide_denial", is_output=True
                )
                return {
                    "flagged": True,
                    "reason": "output_genocide_denial",
                    "filtered_response": SAFE_RESPONSES["genocide_denial"],
                }

        # Check for violence in output
        violence_signals = [
            "how to make a weapon",
            "how to harm",
            "instructions for violence",
        ]
        for signal in violence_signals:
            if signal in response_lower:
                self._log_flagged(
                    response[:500], "output_violence", is_output=True
                )
                return {
                    "flagged": True,
                    "reason": "output_violence",
                    "filtered_response": SAFE_RESPONSES["violence_promotion"],
                }

        return {"flagged": False, "reason": None, "filtered_response": None}

    def get_sensitivity_for_mode(self, mode: str) -> str:
        """Return the max sensitivity level allowed for a given mode."""
        return {
            "kid_friendly": "standard",
            "standard": "sensitive",
            "personal_voices": "highly_sensitive",
        }.get(mode, "standard")

    def _log_flagged(self, content: str, reason: str, is_output: bool = False):
        """Log flagged content for human review."""
        if not self.audit_enabled:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "output_flagged" if is_output else "query_blocked",
            "reason": reason,
            "content_preview": content[:500],
        }

        logger.warning(f"Safety flagged: reason={reason}, preview={content[:100]}")

        try:
            with open(self.audit_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
