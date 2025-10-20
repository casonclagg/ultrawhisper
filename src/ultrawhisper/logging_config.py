#!/usr/bin/env python3
"""
Enhanced logging configuration using Loguru for UltraWhisper.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
from platformdirs import user_config_dir


def setup_loguru(config: Dict[str, Any], verbose: bool = False) -> None:
    """
    Setup Loguru logging with beautiful colors and formatting.

    Args:
        config: Configuration dictionary
        verbose: Enable verbose logging
    """
    # Remove default handler
    logger.remove()

    # Get logging config
    log_config = config.get("logging", {})

    # Determine log level
    if verbose:
        level = "DEBUG"
    else:
        level_name = log_config.get("level", "info").upper()
        level = (
            level_name
            if level_name
            in ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
            else "INFO"
        )

    # Console handler with beautiful formatting
    console_format = get_console_format(verbose)
    logger.add(
        sys.stdout,
        format=console_format,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=verbose,  # Only show variables in verbose mode
        catch=True,
    )

    # File handler if specified
    log_file = log_config.get("file")
    if log_file:
        try:
            # Expand path
            if log_file.startswith("~"):
                log_file = os.path.expanduser(log_file)
            elif not os.path.isabs(log_file):
                # Relative to config directory/logs subfolder
                config_dir = Path(user_config_dir("ultrawhisper"))
                logs_dir = config_dir / "logs"
                log_file = logs_dir / log_file

            # Ensure parent directory exists (including logs folder)
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)

            # Add file handler with rotation
            file_format = get_file_format()
            logger.add(
                log_file,
                format=file_format,
                level=level,
                rotation="10 MB",
                retention="7 days",
                compression="gz",
                backtrace=True,
                diagnose=verbose,
                catch=True,
            )

            logger.info(f"📁 Logging to file: {log_file}")

        except Exception as e:
            logger.warning(f"⚠️ Could not setup file logging: {e}")

    # Configure component-specific log levels
    setup_component_logging(config, verbose)

    logger.info("🎨 Enhanced Loguru logging initialized")


def get_console_format(verbose: bool = False) -> str:
    """Get console format with colors and icons."""
    if verbose:
        return (
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name: <20}</cyan> | "
            "{message}"
        )
    else:
        return (
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "{message}"
        )


def get_file_format() -> str:
    """Get file format without colors."""
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name: <20} | "
        "{function}:{line} | "
        "{message}"
    )


def setup_component_logging(config: Dict[str, Any], verbose: bool = False) -> None:
    """Setup component-specific logging levels."""
    log_config = config.get("logging", {})

    # Default level for all components
    base_level = "DEBUG" if verbose else "INFO"

    # Component-specific settings
    components = {
        "ultrawhisper.audio": base_level,
        "ultrawhisper.transcription": base_level,
        "ultrawhisper.llm": base_level,
        "ultrawhisper.context": "DEBUG" if log_config.get("log_context") else "INFO",
        "ultrawhisper.config": "DEBUG" if log_config.get("log_prompts") else "INFO",
        "ultrawhisper.corrections": (
            "INFO" if log_config.get("log_corrections") else "WARNING"
        ),
        "ultrawhisper.ui": base_level,
    }

    # Set levels for each component
    for component, level in components.items():
        logger.bind(component=component)


def get_logger(name: str) -> Any:
    """
    Get a logger instance with component binding.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Loguru logger instance
    """
    return logger.bind(component=name)


# Logging helpers for different event types
class LogHelper:
    """Helper methods for consistent logging across components."""

    @staticmethod
    def recording_start():
        """Log recording start."""
        logger.info("Recording started")

    @staticmethod
    def recording_stop(duration: float):
        """Log recording stop."""
        logger.info(f"Recording stopped ({duration:.2f}s)")

    @staticmethod
    def transcription_start(file_path: str):
        """Log transcription start."""
        logger.info(f"Transcribing audio: {Path(file_path).name}")

    @staticmethod
    def transcription_result(text: str, duration: float):
        """Log transcription result."""
        logger.info(f'► User said ({duration:.2f}s): "{text}"')

    @staticmethod
    def llm_request(provider: str, model: str, url: str, text_length: int):
        """Log LLM request."""
        logger.info(f"LLM request: {provider}/{model} @ {url} ({text_length} chars)")

    @staticmethod
    def llm_response(
        corrected_text: str, duration: float, usage: Dict[str, Any] = None
    ):
        """Log LLM response."""
        usage_str = f" ({usage.get('total_tokens', 0)} tokens)" if usage else ""
        logger.info(f'◄ Corrected ({duration:.2f}s){usage_str}: "{corrected_text}"')

    @staticmethod
    def llm_error(provider: str, error: str):
        """Log LLM error."""
        logger.error(f"LLM error ({provider}): {error}")

    @staticmethod
    def context_detected(app: str, title: str, method: str):
        """Log context detection."""
        logger.info(
            f"● Context: {app} ({method}) - \"{title[:50]}{'...' if len(title) > 50 else ''}\""
        )

    @staticmethod
    def prompt_construction(base_length: int, layers: list, final_length: int):
        """Log prompt construction."""
        layers_str = " + ".join(layers) if layers else "base only"
        logger.info(
            f"Prompt built: {layers_str} ({base_length} → {final_length} chars)"
        )

    @staticmethod
    def pattern_matched(pattern: str, prompt: str):
        """Log pattern matching."""
        logger.debug(
            f"Pattern matched: \"{pattern}\" → \"{prompt[:50]}{'...' if len(prompt) > 50 else ''}\""
        )

    @staticmethod
    def text_output(text: str, mode: str):
        """Log text output."""
        logger.info(f'Text output ({mode}): "{text}"')

    @staticmethod
    def config_loaded(config_path: str):
        """Log config loading."""
        logger.info(f"⚙️ Config loaded: {config_path}")

    @staticmethod
    def service_status(service: str, status: str, details: str = ""):
        """Log service status."""
        icon = "✅" if status == "enabled" else "❌" if status == "disabled" else "⚠️"
        details_str = f" - {details}" if details else ""
        logger.info(f"{icon} {service}: {status}{details_str}")


def redirect_stdlib_logging():
    """Redirect standard library logging to Loguru."""
    import logging

    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# Convenience function for backward compatibility
def get_logging_status(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get current logging configuration status."""
    log_config = config.get("logging", {})

    return {
        "level": log_config.get("level", "info"),
        "file": log_config.get("file"),
        "log_context": log_config.get("log_context", False),
        "log_prompts": log_config.get("log_prompts", False),
        "log_corrections": log_config.get("log_corrections", False),
        "redact_content": log_config.get("redact_content", False),
    }
