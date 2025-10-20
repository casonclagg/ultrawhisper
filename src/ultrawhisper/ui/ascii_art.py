"""
Shared ASCII art utilities for UltraWhisper TUI.

This module provides reusable ASCII art generation functionality that can be
used across different UI components while maintaining consistent styling and
responsive layout behavior.
"""

from typing import Optional
from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText


def get_ultrawhisper_ascii_art(
    application: Optional[Application] = None,
    animation_frame: int = 0,
    subtitle: Optional[str] = None
) -> FormattedText:
    """Generate ASCII art header with responsive layout and colors.

    Args:
        application: The prompt-toolkit Application instance for getting terminal width
        animation_frame: Current animation frame for pulse indicator
        subtitle: Optional subtitle to display (e.g., "Settings")

    Returns:
        FormattedText object containing the ASCII art with styling
    """
    # Get terminal width for centering
    try:
        width = (
            application.output.get_size().columns if application else 80
        )
    except:
        width = 80

    # Check if we can fit both words on one line (need ~95 characters)
    one_line_mode = width >= 95

    lines = []

    if one_line_mode:
        # Single line layout for wide terminals - Rainbow scheme
        # Split into ULTRA and WHISPER parts for different colors
        ultra_whisper_art = [
            ("border", "╔═════════════════════════════════════════════════════════════════════════════════════════════╗"),
            ("ultra", "║  ██╗   ██╗██╗  ████████╗██████╗  █████╗", "whisper", " ██╗    ██╗██╗  ██╗██╗███████╗██████╗ ███████╗██████╗  ║"),
            ("ultra", "║  ██║   ██║██║  ╚══██╔══╝██╔══██╗██╔══██╗", "whisper", "██║    ██║██║  ██║██║██╔════╝██╔══██╗██╔════╝██╔══██╗ ║"),
            ("ultra", "║  ██║   ██║██║     ██║   ██████╔╝███████║", "whisper", "██║ █╗ ██║███████║██║███████╗██████╔╝█████╗  ██████╔╝ ║"),
            ("ultra", "║  ██║   ██║██║     ██║   ██╔══██╗██╔══██║", "whisper", "██║███╗██║██╔══██║██║╚════██║██╔═══╝ ██╔══╝  ██╔══██╗ ║"),
            ("ultra", "║  ╚██████╔╝███████╗██║   ██║  ██║██║  ██║", "whisper", "╚███╔███╔╝██║  ██║██║███████║██║     ███████╗██║  ██║ ║"),
            ("ultra", "║   ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝", "whisper", " ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝ ║"),
            ("border", "╚═════════════════════════════════════════════════════════════════════════════════════════════╝"),
        ]

        # Add decorative elements and center
        for item in ultra_whisper_art:
            if isinstance(item, tuple) and len(item) == 2:
                # Border lines
                line_type, line = item
                padding = max(0, (width - len(line)) // 2)
                centered_line = " " * padding + line
                lines.append((f"class:ascii.{line_type}", centered_line + "\n"))
            elif isinstance(item, tuple) and len(item) == 4:
                # Split lines (ULTRA + WHISPER)
                ultra_type, ultra_part, whisper_type, whisper_part = item
                padding = max(0, (width - len(ultra_part + whisper_part)) // 2)
                lines.append(("", " " * padding))
                lines.append((f"class:ascii.{ultra_type}", ultra_part))
                lines.append((f"class:ascii.{whisper_type}", whisper_part + "\n"))

    else:
        # Two line layout for narrow terminals - Rainbow scheme
        ultra_art = [
            ("border", "╔═══════════════════════════════════════════════╗"),
            ("ultra", "║  ██╗   ██╗██╗  ████████╗██████╗  █████╗     ║"),
            ("ultra", "║  ██║   ██║██║  ╚══██╔══╝██╔══██╗██╔══██╗    ║"),
            ("ultra", "║  ██║   ██║██║     ██║   ██████╔╝███████║    ║"),
            ("ultra", "║  ██║   ██║██║     ██║   ██╔══██╗██╔══██║    ║"),
            ("ultra", "║  ╚██████╔╝███████╗██║   ██║  ██║██║  ██║    ║"),
            ("ultra", "║   ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝    ║"),
        ]

        whisper_art = [
            ("waves", "║                                              ║"),
            ("whisper", "║  ██╗    ██╗██╗  ██╗██╗███████╗██████╗ ███████╗██████╗  ║"),
            ("whisper", "║  ██║    ██║██║  ██║██║██╔════╝██╔══██╗██╔════╝██╔══██╗ ║"),
            ("whisper", "║  ██║ █╗ ██║███████║██║███████╗██████╔╝█████╗  ██████╔╝ ║"),
            ("whisper", "║  ██║███╗██║██╔══██║██║╚════██║██╔═══╝ ██╔══╝  ██╔══██╗ ║"),
            ("whisper", "║  ╚███╔███╔╝██║  ██║██║███████║██║     ███████╗██║  ██║ ║"),
            ("whisper", "║   ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝ ║"),
            ("border", "╚═══════════════════════════════════════════════╝"),
        ]

        # Add ULTRA section
        for line_type, line in ultra_art:
            padding = max(0, (width - len(line)) // 2)
            centered_line = " " * padding + line
            lines.append((f"class:ascii.{line_type}", centered_line + "\n"))

        # Add WHISPER section
        for line_type, line in whisper_art:
            padding = max(0, (width - len(line)) // 2)
            centered_line = " " * padding + line
            lines.append((f"class:ascii.{line_type}", centered_line + "\n"))

    # Add subtitle if provided
    if subtitle:
        subtitle_text = f"── {subtitle} ──"
        subtitle_padding = max(0, (width - len(subtitle_text)) // 2)
        subtitle_line = " " * subtitle_padding + subtitle_text
        lines.append(("class:ascii.accent", subtitle_line + "\n"))

    # Add animated decorative pulse indicator
    pulse_patterns = [
        "● ○ ○ ○ ○ ○ ○ ○",
        "○ ● ○ ○ ○ ○ ○ ○",
        "○ ○ ● ○ ○ ○ ○ ○",
        "○ ○ ○ ● ○ ○ ○ ○",
        "○ ○ ○ ○ ● ○ ○ ○",
        "○ ○ ○ ○ ○ ● ○ ○",
        "○ ○ ○ ○ ○ ○ ● ○",
        "○ ○ ○ ○ ○ ○ ○ ●",
    ]

    pulse_indicator = pulse_patterns[animation_frame % len(pulse_patterns)]
    pulse_padding = max(0, (width - len(pulse_indicator)) // 2)
    pulse_line = " " * pulse_padding + pulse_indicator
    lines.append(("class:ascii.accent", pulse_line + "\n"))

    return FormattedText(lines)


def get_ascii_height(application: Optional[Application] = None, subtitle: Optional[str] = None) -> int:
    """Get dynamic height for ASCII art based on actual content.

    Args:
        application: The prompt-toolkit Application instance for getting terminal width
        subtitle: Optional subtitle that affects height

    Returns:
        Height needed for the ASCII art in lines
    """
    try:
        width = (
            application.output.get_size().columns if application else 80
        )
    except:
        width = 80

    # Check layout mode
    one_line_mode = width >= 95

    base_height = 9 if one_line_mode else 16  # 8 art lines + 1 pulse line (or 15 + 1)

    # Add 1 for subtitle if present
    if subtitle:
        base_height += 1

    return base_height