#!/usr/bin/env python3
"""
Text-to-Speech service for UltraWhisper.

Provides a unified interface for different TTS providers.
"""

import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from loguru import logger


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def speak(self, text: str) -> bool:
        """
        Speak the given text.

        Args:
            text: Text to speak

        Returns:
            True if speech was successful, False otherwise
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this TTS provider is available on the system.

        Returns:
            True if provider is available, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this TTS provider.

        Returns:
            Provider name string
        """
        pass

    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get configuration schema for this provider.

        Returns:
            Dictionary describing configuration options
        """
        return {}

    def configure(self, config: Dict[str, Any]) -> bool:
        """
        Configure the TTS provider with given settings.

        Args:
            config: Configuration dictionary

        Returns:
            True if configuration was successful
        """
        return True


class TTSService:
    """Main TTS service that manages multiple providers."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the TTS service.

        Args:
            config: TTS configuration dictionary
        """
        self.config = config or {}
        self.providers: Dict[str, TTSProvider] = {}
        self.current_provider: Optional[TTSProvider] = None

        # Threading for async playback
        self._speaking = False
        self._speech_thread: Optional[threading.Thread] = None
        self._current_provider_ref: Optional[TTSProvider] = None  # Store provider ref for stopping

        logger.info("🔊 Initializing TTS service...")

    def register_provider(self, provider: TTSProvider) -> bool:
        """
        Register a TTS provider.

        Args:
            provider: TTS provider instance

        Returns:
            True if registration was successful
        """
        try:
            provider_name = provider.get_provider_name()

            if provider.is_available():
                self.providers[provider_name] = provider
                logger.info(f"🔊 Registered TTS provider: {provider_name}")
                return True
            else:
                logger.warning(f"🔊 TTS provider {provider_name} is not available")
                return False

        except Exception as e:
            logger.error(f"🔊 Failed to register TTS provider: {e}")
            return False

    def set_provider(self, provider_name: str) -> bool:
        """
        Set the active TTS provider.

        Args:
            provider_name: Name of the provider to use

        Returns:
            True if provider was set successfully
        """
        if provider_name in self.providers:
            self.current_provider = self.providers[provider_name]
            logger.info(f"🔊 Active TTS provider: {provider_name}")
            return True
        else:
            logger.warning(f"🔊 TTS provider '{provider_name}' not found")
            return False

    def get_available_providers(self) -> List[str]:
        """
        Get list of available TTS provider names.

        Returns:
            List of provider names
        """
        return list(self.providers.keys())

    def is_available(self) -> bool:
        """
        Check if TTS service is available (has at least one provider).

        Returns:
            True if service is available
        """
        return len(self.providers) > 0

    def speak(self, text: str, provider: Optional[str] = None, async_playback: bool = True) -> bool:
        """
        Speak the given text.

        Args:
            text: Text to speak
            provider: Specific provider to use (optional)
            async_playback: Whether to play speech asynchronously

        Returns:
            True if speech was initiated successfully
        """
        if not text or not text.strip():
            logger.debug("🔊 Empty text, skipping TTS")
            return False

        # Select provider
        active_provider = None
        if provider and provider in self.providers:
            active_provider = self.providers[provider]
        elif self.current_provider:
            active_provider = self.current_provider
        elif self.providers:
            # Use first available provider
            active_provider = next(iter(self.providers.values()))

        if not active_provider:
            logger.warning("🔊 No TTS provider available")
            return False

        try:
            if async_playback:
                return self._speak_async(active_provider, text)
            else:
                return active_provider.speak(text)

        except Exception as e:
            logger.error(f"🔊 TTS error: {e}")
            return False

    def _speak_async(self, provider: TTSProvider, text: str) -> bool:
        """
        Speak text asynchronously in a separate thread.

        Args:
            provider: TTS provider to use
            text: Text to speak

        Returns:
            True if async speech was started
        """
        if self._speaking:
            logger.debug("🔊 Already speaking, stopping it first")
            self.stop_speaking()
            # Give it a moment to stop
            import time
            time.sleep(0.1)

        # Store provider reference for stopping
        self._current_provider_ref = provider

        def _speech_worker():
            try:
                self._speaking = True
                logger.debug(f"🔊 Speaking: {text[:50]}...")
                provider.speak(text)
            except Exception as e:
                logger.error(f"🔊 Async speech error: {e}")
            finally:
                self._speaking = False
                self._current_provider_ref = None

        try:
            self._speech_thread = threading.Thread(target=_speech_worker, daemon=True)
            self._speech_thread.start()
            return True
        except Exception as e:
            logger.error(f"🔊 Failed to start async speech: {e}")
            self._speaking = False
            return False

    def stop_speaking(self) -> bool:
        """
        Stop current speech.

        Returns:
            True if stop was successful
        """
        self._speaking = False

        # Try to stop the currently speaking provider (from async thread)
        provider = self._current_provider_ref if self._current_provider_ref else self.current_provider

        if provider and hasattr(provider, 'stop'):
            try:
                result = provider.stop()
                logger.debug(f"🔊 TTS stop requested and executed: {result}")
                return result
            except Exception as e:
                logger.error(f"🔊 Failed to stop TTS provider: {e}")
                return False

        logger.debug("🔊 TTS stop requested (no provider or stop method available)")
        return True

    def configure_provider(self, provider_name: str, config: Dict[str, Any]) -> bool:
        """
        Configure a specific TTS provider.

        Args:
            provider_name: Name of provider to configure
            config: Configuration dictionary

        Returns:
            True if configuration was successful
        """
        if provider_name in self.providers:
            return self.providers[provider_name].configure(config)
        else:
            logger.warning(f"🔊 Cannot configure unknown provider: {provider_name}")
            return False

    def get_status_info(self) -> Dict[str, Any]:
        """
        Get status information about the TTS service.

        Returns:
            Dictionary with TTS service status
        """
        return {
            "available": self.is_available(),
            "providers": list(self.providers.keys()),
            "current_provider": self.current_provider.get_provider_name() if self.current_provider else None,
            "speaking": self._speaking,
        }