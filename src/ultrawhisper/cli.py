#!/usr/bin/env python3
"""
Command-line interface for UltraWhisper.
"""

import os
import sys
import argparse
from typing import Optional
from loguru import logger

from ultrawhisper.config.config import ConfigManager, interactive_setup, setup_logging
from ultrawhisper.app import TranscriptionApp
from ultrawhisper.logging_config import LogHelper


def setup_basic_logging(verbose: bool = False) -> None:
    """Set up basic Loguru logging configuration for CLI startup."""
    # Loguru will be configured properly later, just ensure it works for startup
    if not verbose:
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>",
            level="INFO",
        )


def main() -> None:
    """Main entry point for UltraWhisper CLI."""
    parser = argparse.ArgumentParser(
        description="UltraWhisper - Voice transcription with global hotkeys and LLM correction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ultrawhisper                    # Launch terminal user interface (default)
  ultrawhisper setup              # Run interactive setup wizard
  ultrawhisper tui                # Explicitly launch TUI
  ultrawhisper --verbose          # Enable debug logging

For more information, visit: https://github.com/casonclagg/ultrawhisper
        """,
    )

    # Commands
    parser.add_argument(
        "command",
        nargs="?",
        choices=["setup", "tui"],
        help="Command to run (optional)",
    )

    # TUI options
    parser.add_argument(
        "--show-prompts", action="store_true", help="Show LLM prompts in TUI"
    )

    # Other options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    args = parser.parse_args()

    # Set up basic logging for startup
    setup_basic_logging(args.verbose)

    # Handle setup command
    if args.command == "setup":
        config = interactive_setup()
        config_manager = ConfigManager()
        config_manager.save_config(config)
        print(f"\n✓ Configuration saved to: {config_manager.get_config_path()}")
        print("\nYou can now run 'ultrawhisper' to start the application!")
        return

    # Handle TUI command (or default behavior)
    if args.command == "tui" or args.command is None:
        try:
            from ultrawhisper.ui.simple_tui import SimpleUltraWhisperTUI

            tui = SimpleUltraWhisperTUI(show_prompts=args.show_prompts)
            tui.run()
        except KeyboardInterrupt:
            print("\n\nTUI closed. Goodbye! 👋")
        except Exception as e:
            print(f"\n❌ TUI Error: {e}")
            if args.verbose:
                import traceback

                traceback.print_exc()
            sys.exit(1)
        return


if __name__ == "__main__":
    main()
