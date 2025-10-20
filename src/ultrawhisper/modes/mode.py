"""
Mode enumeration for UltraWhisper.
"""

from enum import Enum
from typing import Optional


class Mode(Enum):
    """Available modes for UltraWhisper."""
    TRANSCRIPTION = "transcription"
    QUESTION = "question"

    @classmethod
    def from_string(cls, mode_str: str) -> Optional['Mode']:
        """Convert string to Mode enum."""
        try:
            return cls(mode_str.lower())
        except ValueError:
            return None

    def __str__(self) -> str:
        return self.value
