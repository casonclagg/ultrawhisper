#!/usr/bin/env python3
"""
Text output functionality for UltraWhisper.
"""

import time
import logging
from typing import Dict, Any

from pynput.keyboard import Controller, Key

try:
    from unidecode import unidecode

    HAS_UNIDECODE = True
except ImportError:
    HAS_UNIDECODE = False

# Configure logging
logger = logging.getLogger("ultrawhisper.ui")


class TextOutputter:
    """Handles outputting text to the active application."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the text outputter.

        Args:
            config: Output configuration dictionary
        """
        self.typing_delay = config.get("typing_delay", 0.01)
        self.paste_mode = config.get("paste_mode", False)

        # Initialize keyboard controller
        self.keyboard = Controller()

        logger.info(
            f"Initialized TextOutputter with typing_delay={self.typing_delay}, paste_mode={self.paste_mode}"
        )

    def output_text(self, text: str):
        """
        Output text to the active application.

        Args:
            text: Text to output
        """
        if not text:
            logger.warning("No text to output")
            return

        # Normalize text to fix encoding issues
        normalized_text = self._normalize_text(text)

        logger.info(f"Outputting text: {normalized_text}")

        if self.paste_mode:
            self._paste_text(normalized_text)
        else:
            self._type_text(normalized_text)

    def _type_text(self, text: str):
        """
        Type text character by character.

        Args:
            text: Text to type
        """
        logger.debug(f"Typing text: {text}")

        try:
            # Type each character with a delay
            for char in text:
                self.keyboard.type(char)
                time.sleep(self.typing_delay)

            logger.debug("Finished typing text")
        except Exception as e:
            logger.error(f"Error typing text: {e}")

    def _paste_text(self, text: str):
        """
        Paste text using the clipboard.

        Args:
            text: Text to paste
        """
        logger.debug(f"Pasting text: {text}")

        try:
            # Try to use pyperclip for clipboard operations
            try:
                import pyperclip

                pyperclip.copy(text)

                # Simulate Ctrl+V to paste
                with self.keyboard.pressed(Key.ctrl):
                    self.keyboard.press("v")
                    self.keyboard.release("v")

                logger.debug("Pasted text using pyperclip")
            except ImportError:
                logger.warning("pyperclip not available, falling back to typing")
                self._type_text(text)
        except Exception as e:
            logger.error(f"Error pasting text: {e}")
            # Fall back to typing
            self._type_text(text)

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text to fix encoding and character issues.

        Args:
            text: Input text to normalize

        Returns:
            Normalized text with problematic characters replaced
        """
        # Log the original text with character codes for debugging
        if any(ord(c) > 127 for c in text):
            char_codes = [f"'{c}'({ord(c):04x})" for c in text if ord(c) > 127]
            logger.debug(f"Non-ASCII characters found: {char_codes}")

        if HAS_UNIDECODE:
            # Use unidecode for comprehensive Unicode-to-ASCII conversion
            normalized = unidecode(text)
            logger.debug(f"Used unidecode for text normalization")
        else:
            # Fallback to manual replacements if unidecode is not available
            logger.warning(
                "unidecode not available, using manual character replacements"
            )
            replacements = {
                # Smart quotes to straight quotes (multiple variants)
                """: "'",  # U+2018 (left single quotation mark)
                """: "'",  # U+2019 (right single quotation mark)
                "`": "'",  # U+0060 (grave accent used as quote)
                "´": "'",  # U+00B4 (acute accent used as quote)
                '"': '"',  # U+201C (left double quotation mark)
                '"': '"',  # U+201D (right double quotation mark)
                "„": '"',  # U+201E (double low-9 quotation mark)
                "‚": "'",  # U+201A (single low-9 quotation mark)
                # Em/en dashes to regular hyphens
                "—": "-",  # U+2014 (em dash)
                "–": "-",  # U+2013 (en dash)
                # Other problematic characters
                "…": "...",  # U+2026 (horizontal ellipsis)
                " ": " ",  # U+00A0 (non-breaking space) to regular space
                # Possible smart apostrophe variants
                "ʼ": "'",  # U+02BC (modifier letter apostrophe)
                "ˈ": "'",  # U+02C8 (modifier letter vertical line)
            }

            normalized = text
            for old_char, new_char in replacements.items():
                if old_char in normalized:
                    logger.debug(
                        f"Replacing '{old_char}' (U+{ord(old_char):04X}) with '{new_char}'"
                    )
                    normalized = normalized.replace(old_char, new_char)

        if normalized != text:
            logger.debug(f"Text normalized: '{text}' -> '{normalized}'")

        return normalized
