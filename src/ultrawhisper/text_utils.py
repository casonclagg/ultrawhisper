#!/usr/bin/env python3
"""
Text utility functions for UltraWhisper.

Provides text processing utilities for various features.
"""

import re
from typing import Tuple


def strip_urls_for_speech(text: str) -> Tuple[str, int]:
    """
    Replace URLs in text with the word "URL" for TTS output.

    Matches common URL patterns including:
    - http:// and https:// URLs
    - www. prefixed URLs
    - Common domain patterns

    Args:
        text: Input text that may contain URLs

    Returns:
        Tuple of (sanitized text, count of URLs replaced)

    Examples:
        >>> strip_urls_for_speech("Check https://example.com for info")
        ('Check URL for info', 1)

        >>> strip_urls_for_speech("Visit www.example.com and http://test.org")
        ('Visit URL and URL', 2)
    """
    # Pattern matches:
    # - http:// or https:// followed by non-whitespace
    # - www. followed by domain-like patterns
    # - Common TLDs without protocol
    url_pattern = r'(?:https?://|www\.)[^\s<>"\'{}\[\]|\\^`]+'

    # Count URLs before replacement
    urls_found = re.findall(url_pattern, text)
    url_count = len(urls_found)

    # Replace URLs with "URL"
    sanitized_text = re.sub(url_pattern, "URL", text)

    return sanitized_text, url_count