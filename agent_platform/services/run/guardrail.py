import logging
import re

from agent_platform.exceptions import PromptInjectionError

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|context)",
    r"disregard\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|context)",
    r"forget\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|context)",
    r"you\s+are\s+now\s+",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"system\s*:\s*",
    r"\bdo\s+not\s+follow\s+(your|the)\s+(instructions|rules|guidelines)\b",
    r"override\s+(your|the)\s+(instructions|rules|guidelines|system\s+prompt)",
    r"reveal\s+(your|the)\s+(system\s+prompt|instructions|rules)",
    r"what\s+(are|is)\s+your\s+(system\s+prompt|instructions|rules)",
    r"<\s*/?\s*system\s*>",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


class PromptInjectionGuardrail:
    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def check(self, text: str) -> None:
        """Check text for prompt injection patterns. Raises PromptInjectionError if detected."""
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(text):
                self._logger.warning(f"Prompt injection detected pattern={pattern.pattern}")
                raise PromptInjectionError
