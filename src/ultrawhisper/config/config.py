#!/usr/bin/env python3
"""
Configuration management for UltraWhisper with XDG Base Directory support.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Union

import yaml
from platformdirs import user_config_dir
from loguru import logger
from pydantic import ValidationError

from .models import UltraWhisperConfig

DEFAULT_CONFIG = {
    "notifications": {
        "visual_enabled": False,
        "audio_enabled": True,
    },
    "use_double_tap": False,
    "push_to_talk": {
        "enabled": True,
        "key": "Key.cmd",
    },
    "hotkey": {
        "key": "cmd",
        "modifier": "Key.cmd",
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "dtype": "float32",
    },
    "whisper": {
        "model_name": "tiny",
        "language": "en",
    },
    "llm": {
        "provider": "openai",
        "model": "gpt-4.1",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "base_prompt": (
            "You are correcting speech-to-text transcription errors. "
            "Fix grammar, spelling, and misheard words while preserving the original meaning."
        ),
        "skip_if_unavailable": True,
    },
    "context_detection": True,
    "context_prompts": {
        "applications": {
            "code": "Preserve code syntax, variable names, and technical terms. Format comments properly.",
            "google-chrome": "Format for web: use proper capitalization and punctuation for comments/posts.",
            "firefox": "Format for web: use proper capitalization and punctuation for comments/posts.",
            "sublime_text": "Preserve code syntax and technical terms.",
            "vim": "Preserve code syntax, commands, and technical terms.",
            "gnome-terminal": "Preserve commands, paths, and technical syntax. Don't add unnecessary punctuation.",
            "kitty": "Preserve commands and technical syntax.",
            "alacritty": "Preserve commands and technical syntax.",
            "slack": "Keep casual tone, use appropriate punctuation for chat.",
            "discord": "Keep casual tone for chat messages.",
            "obsidian": "Format as markdown. Improve clarity and structure.",
            "libreoffice": "Professional tone, proper grammar and punctuation.",
        },
        "patterns": [
            {
                "match": r".*\.py\s*[-–]\s*.*",
                "prompt": "Format as Python code or comments. Use proper syntax.",
            },
            {
                "match": r".*\.js\s*[-–]\s*.*",
                "prompt": "Format as JavaScript code or comments. Use proper syntax.",
            },
            {
                "match": r".*\.md\s*[-–]\s*.*",
                "prompt": "Format as markdown with proper syntax and structure.",
            },
            {
                "match": r".*GitHub.*",
                "prompt": "Format as markdown for GitHub. Use proper formatting for issues/PRs.",
            },
            {
                "match": r".*Stack Overflow.*",
                "prompt": "Technical writing with clear problem descriptions and code examples.",
            },
            {
                "match": r".*(Terminal|console).*",
                "prompt": "Preserve command syntax and technical terms.",
            },
        ],
    },
    "logging": {
        "level": "info",
        "log_context": False,
        "log_prompts": False,
        "log_corrections": False,
        "redact_content": False,
        "file": None,
    },
    "output": {
        "paste_mode": False,
        "typing_delay": 0.02,
    },
}


class ConfigManager:
    """Manages configuration with XDG Base Directory compliance."""

    def __init__(self, config_name: str = "ultrawhisper"):
        """Initialize the config manager."""
        self.config_name = config_name
        self.config_dir = Path(user_config_dir(config_name))
        self.config_file = self.config_dir / "config.yml"
        self._config: Optional[UltraWhisperConfig] = None

    def get_config_path(self) -> Path:
        """Get the configuration file path."""
        return self.config_file

    def config_exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_file.exists()

    def load_config(self) -> UltraWhisperConfig:
        """Load configuration from file or return default config."""
        if self._config is not None:
            return self._config

        if self.config_exists():
            try:
                with open(self.config_file, "r") as f:
                    user_config = yaml.safe_load(f) or {}

                # Merge with default config and validate with Pydantic
                merged_config = self._deep_merge(DEFAULT_CONFIG.copy(), user_config)
                self._config = UltraWhisperConfig.from_dict(merged_config)
                logger.info(f"Loaded configuration from {self.config_file}")
            except ValidationError as e:
                logger.error(f"Configuration validation error: {e}")
                logger.info("Using default configuration")
                self._config = UltraWhisperConfig()
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                logger.info("Using default configuration")
                self._config = UltraWhisperConfig()
        else:
            logger.info("No configuration file found, using defaults")
            self._config = UltraWhisperConfig()

        return self._config

    def save_config(self, config: Union[UltraWhisperConfig, Dict[str, Any]]) -> None:
        """Save configuration to file."""
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Convert to dict if it's a Pydantic model
            if isinstance(config, UltraWhisperConfig):
                config_dict = config.model_dump_yaml_compatible()
                self._config = config
            else:
                config_dict = config
                self._config = UltraWhisperConfig.from_dict(config)

            # Write config file
            with open(self.config_file, "w") as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
            raise

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        config = self.load_config()
        config_dict = config.model_dump_yaml_compatible()
        updated_config = self._deep_merge(config_dict, updates)
        self.save_config(updated_config)

    def _deep_merge(
        self, base: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in updates.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result


def create_default_config() -> UltraWhisperConfig:
    """Create a default configuration."""
    return UltraWhisperConfig()


def detect_llm_providers() -> Dict[str, Dict[str, Any]]:
    """Get available LLM providers for setup (don't check if servers are running)."""
    providers = {}

    # OpenAI-compatible (LMStudio, LocalAI, etc.) - always available
    providers["openai-compatible"] = {
        "available": True,  # Always available during setup
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-5-nano", "gpt-4.1"],
        "requires_key": False,
        "base_url": "http://localhost:1234/v1",
        "description": "LMStudio or other OpenAI-compatible server",
    }

    # OpenAI (requires API key)
    providers["openai"] = {
        "available": True,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-5-nano", "gpt-4.1"],
        "requires_key": True,
        "base_url": "https://api.openai.com/v1",
        "description": "OpenAI's official API",
    }

    # Anthropic (requires API key)
    providers["anthropic"] = {
        "available": True,
        "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        "requires_key": True,
        "base_url": "https://api.anthropic.com",
        "description": "Anthropic's Claude API",
    }

    return providers


def interactive_setup() -> Dict[str, Any]:
    """Run interactive setup wizard."""
    print("🎤 UltraWhisper Setup")
    print("=" * 50)

    config = create_default_config()
    # Convert to dict for easier manipulation during setup
    config_dict = config.model_dump_yaml_compatible()

    # Get available LLM providers
    print("\n🔍 Configuring LLM provider...")
    providers = detect_llm_providers()

    # Show available providers
    print("\nAvailable LLM providers:")
    available_providers = []

    for name, info in providers.items():
        description = info.get("description", "")
        status = "✓" if not info.get("requires_key", False) else "✓ (requires API key)"
        print(
            f"  {len(available_providers) + 1}. {name.replace('-', ' ').title()} - {description} {status}"
        )
        available_providers.append(name)

    # Let user choose provider
    if available_providers:
        while True:
            try:
                choice = input(
                    f"\nSelect LLM provider (1-{len(available_providers)}): "
                )
                provider_idx = int(choice) - 1
                if 0 <= provider_idx < len(available_providers):
                    selected_provider = available_providers[provider_idx]
                    break
                else:
                    print("Invalid choice. Please try again.")
            except (ValueError, KeyboardInterrupt):
                print("\nSetup cancelled.")
                return config

        # Configure selected provider
        config_dict["llm"]["provider"] = selected_provider
        provider_info = providers[selected_provider]

        # Set base URL
        base_url = provider_info.get("base_url", "")
        if base_url:
            config_dict["llm"]["base_url"] = base_url

        # Handle custom base URL for openai-compatible
        if selected_provider == "openai-compatible":
            current_url = config_dict["llm"]["base_url"]
            custom_url = input(f"\nEnter base URL (default: {current_url}): ").strip()
            if custom_url:
                config_dict["llm"]["base_url"] = custom_url

        if provider_info.get("requires_key", False):
            api_key = input(
                f"\nEnter your {selected_provider.replace('-', ' ').title()} API key: "
            ).strip()
            config_dict["llm"]["api_key"] = api_key

        # Select model with custom option
        models = provider_info.get("models", [])
        if models:
            print(f"\nAvailable {selected_provider.replace('-', ' ')} models:")
            for i, model in enumerate(models):
                print(f"  {i + 1}. {model}")
            print(f"  {len(models) + 1}. Custom (type your own)")

            while True:
                try:
                    choice = input(
                        f"Select model (1-{len(models) + 1}, default: 1): "
                    ).strip()
                    if not choice:
                        model_idx = 0
                        config_dict["llm"]["model"] = models[0]
                        break
                    else:
                        model_idx = int(choice) - 1

                    if 0 <= model_idx < len(models):
                        config_dict["llm"]["model"] = models[model_idx]
                        break
                    elif model_idx == len(models):
                        # Custom model
                        custom_model = input("Enter custom model name: ").strip()
                        if custom_model:
                            config_dict["llm"]["model"] = custom_model
                            break
                        else:
                            print("Model name cannot be empty. Please try again.")
                    else:
                        print("Invalid choice. Please try again.")
                except (ValueError, KeyboardInterrupt):
                    print("\nUsing default model.")
                    if models:
                        config_dict["llm"]["model"] = models[0]
                    break

    # Configure Whisper model
    whisper_models = ["tiny", "base", "small", "medium", "large"]
    print(f"\nWhisper models (smaller = faster, larger = more accurate):")
    for i, model in enumerate(whisper_models):
        default_marker = " (default)" if model == "small" else ""
        print(f"  {i + 1}. {model}{default_marker}")

    while True:
        try:
            choice = input(
                f"Select Whisper model (1-{len(whisper_models)}, default: 3): "
            ).strip()
            if not choice:
                model_idx = 2  # small
            else:
                model_idx = int(choice) - 1

            if 0 <= model_idx < len(whisper_models):
                config_dict["whisper"]["model_name"] = whisper_models[model_idx]
                break
            else:
                print("Invalid choice. Please try again.")
        except (ValueError, KeyboardInterrupt):
            print("\nUsing default model (small).")
            break

    # Check and configure context detection
    print(f"\n🔍 Checking context detection capabilities...")
    from ultrawhisper.context import ContextDetector

    detector = ContextDetector({"context_detection": True})
    status = detector.get_dependency_status()

    if status["can_detect"]:
        print("✓ Context detection available")
        print(f"  Methods: {', '.join(status['available_methods'])}")

        enable_context = (
            input("\nEnable context-aware prompts? (Y/n): ").strip().lower()
        )
        if enable_context in ("", "y", "yes"):
            config_dict["context_detection"] = True
            print("✓ Context detection enabled")
        else:
            config_dict["context_detection"] = False
            print("✗ Context detection disabled")
    else:
        print("✗ Context detection unavailable")
        for dep, available in status["dependencies"].items():
            print(f"  {dep}: {'✓' if available else '✗'}")

        if status["recommendations"]:
            print("\nTo enable context detection:")
            for rec in status["recommendations"]:
                print(f"  • {rec}")

        config_dict["context_detection"] = False

    print(f"\n✓ Setup complete!")
    print(f"Configuration will be saved to: {ConfigManager().get_config_path()}")

    return config_dict


def construct_layered_prompt(
    config: Any, context: Dict[str, Any] = None
) -> str:
    """
    Construct a layered prompt from base + context + pattern prompts.

    Args:
        config: Configuration (UltraWhisperConfig Pydantic model)
        context: Current application context

    Returns:
        Complete system prompt string
    """
    import logging
    from ultrawhisper.context import ContextDetector

    logger = logging.getLogger("ultrawhisper.config")

    # Start with base prompt
    base_prompt = config.llm.base_prompt
    prompt_parts = []

    if base_prompt:
        prompt_parts.append(base_prompt)

    # Skip context processing if disabled or no context provided
    if not config.context_detection or not context:
        return " ".join(prompt_parts)

    # Add application-specific prompt
    app_prompts = config.context_prompts.applications
    app_name = context.get("app", "")

    if app_name in app_prompts:
        app_prompt = app_prompts[app_name]
        prompt_parts.append(app_prompt)
        logger.debug(f"Added app prompt for {app_name}: {app_prompt[:50]}...")

    # Add pattern-specific prompt
    patterns = config.context_prompts.patterns
    if patterns:
        detector = ContextDetector(config)
        matched_pattern = detector.match_context_patterns(context, patterns)

        if matched_pattern:
            pattern_prompt = matched_pattern.get("prompt", "")
            if pattern_prompt:
                prompt_parts.append(pattern_prompt)
                logger.debug(f"Added pattern prompt: {pattern_prompt[:50]}...")
                # Log pattern match details
                from ultrawhisper.logging_config import LogHelper

                LogHelper.pattern_matched(
                    matched_pattern.get("match", ""), pattern_prompt
                )

    # Join all parts
    final_prompt = " ".join(prompt_parts)

    # Log prompt construction if enabled
    log_prompts = config.logging.log_prompts

    # Debug: Always log whether prompt logging is enabled
    logger.debug(
        f"🔧 Prompt logging enabled: {log_prompts}"
    )

    if log_prompts:
        from ultrawhisper.logging_config import LogHelper

        layers = []
        if len(prompt_parts) > 1:
            if app_name:
                layers.append("app")
            if matched_pattern:
                layers.append("pattern")
        base_length = len(base_prompt) if base_prompt else 0
        LogHelper.prompt_construction(base_length, layers, len(final_prompt))

        logger.info("🎯 Detailed Prompt Construction:")
        if base_prompt:
            logger.info(f"  Base: {base_prompt[:100]}...")
        if len(prompt_parts) > 1:
            for i, part in enumerate(prompt_parts[1:], 1):
                layer_name = "App" if i == 1 else "Pattern"
                logger.info(f"  {layer_name}: {part[:100]}...")
        logger.info(f"  Final: {len(final_prompt)} characters")
        logger.info(f"  Complete prompt: {final_prompt}")

    return final_prompt


def setup_logging(config: Union[UltraWhisperConfig, Dict[str, Any]], verbose: bool = False) -> None:
    """
    Setup Loguru logging configuration for UltraWhisper.

    Args:
        config: Configuration (UltraWhisperConfig or dict)
        verbose: Enable verbose logging
    """
    from ultrawhisper.logging_config import setup_loguru

    # Convert to dict if it's a Pydantic model for compatibility
    if isinstance(config, UltraWhisperConfig):
        config_dict = config.model_dump()
    else:
        config_dict = config

    setup_loguru(config_dict, verbose)


def log_correction(
    original: str,
    corrected: str,
    context: Dict[str, Any] = None,
    config: Any = None,
) -> None:
    """
    Log a correction with optional redaction for privacy.

    Args:
        original: Original transcribed text
        corrected: Corrected text
        context: Application context
        config: Configuration (UltraWhisperConfig Pydantic model)
    """
    if not config:
        return

    # Skip if correction logging not enabled
    if not config.logging.log_corrections:
        return

    # Use loguru logger
    # Check if we should redact content
    if config.logging.redact_content:
        # Log metadata without sensitive content
        logger.info(f"Correction Applied:")
        logger.info(
            f"  Length: {len(original)} → {len(corrected)} characters"
        )
        logger.info(f"  Change ratio: {len(corrected)/len(original):.2f}")

        if context:
            app = context.get("app", "unknown")
            logger.info(f"  Context: {app}")
    else:
        # Full logging
        logger.info(f"Transcription Correction:")
        logger.info(f"  Original: {original}")
        logger.info(f"  Corrected: {corrected}")

        if context:
            app = context.get("app", "unknown")
            title = context.get("title", "")[:50]
            logger.info(f"  Context: {app} - {title}")


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
