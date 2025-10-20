#!/usr/bin/env python3
"""
System TTS provider for UltraWhisper.

Uses system-level TTS commands like espeak, say, etc.
"""

import os
import platform
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from loguru import logger

from .tts_service import TTSProvider


class SystemTTSProvider(TTSProvider):
    """System-level TTS provider using command-line tools."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the system TTS provider.

        Args:
            config: TTS configuration dictionary
        """
        self.config = config or {}
        self.system = platform.system().lower()
        self.available_commands = self._detect_available_commands()
        self.selected_command = self._select_best_command()

        # Configuration options
        self.voice = self.config.get('voice')
        self.rate = self.config.get('rate', 200)  # Words per minute
        self.volume = self.config.get('volume', 1.0)  # 0.0 to 1.0

        # Track current subprocess for stopping
        self._current_process = None

        if self.selected_command:
            logger.info(f"🔊 System TTS using: {self.selected_command}")
        else:
            logger.warning("🔊 No system TTS commands available")

    def _detect_available_commands(self) -> List[str]:
        """
        Detect available TTS commands on the system.

        Returns:
            List of available command names
        """
        commands = []

        # Linux TTS commands
        linux_commands = ['espeak', 'espeak-ng', 'festival', 'spd-say', 'flite']

        # macOS TTS command
        macos_commands = ['say']

        # Windows TTS (future implementation)
        windows_commands = []  # TODO: Windows SAPI integration

        if self.system == 'linux':
            candidates = linux_commands
        elif self.system == 'darwin':  # macOS
            candidates = macos_commands
        elif self.system == 'windows':
            candidates = windows_commands
        else:
            candidates = linux_commands + macos_commands  # Try both

        for cmd in candidates:
            if shutil.which(cmd):
                commands.append(cmd)

        return commands

    def _select_best_command(self) -> Optional[str]:
        """
        Select the best available TTS command.

        Returns:
            Name of selected command or None if none available
        """
        if not self.available_commands:
            return None

        # Preference order for each platform
        if self.system == 'darwin':  # macOS
            preference = ['say']
        elif self.system == 'linux':
            preference = ['espeak-ng', 'espeak', 'spd-say', 'festival', 'flite']
        else:
            preference = ['espeak-ng', 'espeak', 'say', 'spd-say', 'festival', 'flite']

        # Select first available command from preference list
        for cmd in preference:
            if cmd in self.available_commands:
                return cmd

        # If no preferred command found, use first available
        return self.available_commands[0]

    def speak(self, text: str) -> bool:
        """
        Speak the given text using system TTS.

        Args:
            text: Text to speak

        Returns:
            True if speech was successful
        """
        if not self.is_available() or not text.strip():
            return False

        try:
            command_args = self._build_command_args(text)
            if not command_args:
                return False

            # Execute the TTS command and store process
            self._current_process = subprocess.Popen(
                command_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                # Wait for completion with timeout
                stdout, stderr = self._current_process.communicate(timeout=30)

                if self._current_process.returncode == 0:
                    logger.debug(f"🔊 TTS successful: {self.selected_command}")
                    return True
                else:
                    logger.warning(f"🔊 TTS command failed: {stderr}")
                    return False

            except subprocess.TimeoutExpired:
                logger.error("🔊 TTS command timed out")
                self._current_process.kill()
                return False
            finally:
                self._current_process = None

        except Exception as e:
            logger.error(f"🔊 TTS error: {e}")
            if self._current_process:
                try:
                    self._current_process.kill()
                except:
                    pass
                self._current_process = None
            return False

    def _build_command_args(self, text: str) -> Optional[List[str]]:
        """
        Build command arguments for the selected TTS command.

        Args:
            text: Text to speak

        Returns:
            List of command arguments or None if unsupported command
        """
        if not self.selected_command:
            return None

        # Clean text for TTS (remove problematic characters)
        clean_text = self._clean_text_for_tts(text)

        if self.selected_command == 'say':  # macOS
            args = ['say']
            if self.voice:
                args.extend(['-v', self.voice])
            if self.rate and self.rate != 200:
                args.extend(['-r', str(self.rate)])
            args.append(clean_text)
            return args

        elif self.selected_command in ['espeak', 'espeak-ng']:  # Linux
            args = [self.selected_command]
            if self.voice:
                args.extend(['-v', self.voice])
            # espeak uses words per minute
            args.extend(['-s', str(int(self.rate or 200))])
            args.append(clean_text)
            return args

        elif self.selected_command == 'spd-say':  # Linux (speech-dispatcher)
            args = ['spd-say']
            if self.voice:
                args.extend(['-o', self.voice])
            if self.rate and self.rate != 200:
                # spd-say uses -10 to 10 scale, convert from WPM
                rate_scale = max(-10, min(10, int((self.rate - 200) / 20)))
                args.extend(['-r', str(rate_scale)])
            args.append(clean_text)
            return args

        elif self.selected_command == 'festival':  # Linux
            # Festival is more complex, use simple text input
            args = ['festival', '--tts']
            return args  # Text will be piped to stdin

        elif self.selected_command == 'flite':  # Linux
            args = ['flite']
            if self.voice:
                args.extend(['-voice', self.voice])
            args.extend(['-t', clean_text])
            return args

        else:
            logger.warning(f"🔊 Unsupported TTS command: {self.selected_command}")
            return None

    def _clean_text_for_tts(self, text: str) -> str:
        """
        Clean text for TTS to avoid issues with special characters.

        Args:
            text: Raw text

        Returns:
            Cleaned text suitable for TTS
        """
        # Remove or replace problematic characters
        clean_text = text.strip()

        # Remove excessive whitespace
        import re
        clean_text = re.sub(r'\s+', ' ', clean_text)

        # Limit length to prevent very long speech
        if len(clean_text) > 500:
            clean_text = clean_text[:497] + "..."

        return clean_text

    def is_available(self) -> bool:
        """
        Check if system TTS is available.

        Returns:
            True if TTS commands are available
        """
        return self.selected_command is not None

    def get_provider_name(self) -> str:
        """
        Get the provider name.

        Returns:
            Provider name string
        """
        return "system"

    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get configuration schema for system TTS.

        Returns:
            Configuration schema dictionary
        """
        return {
            "voice": {
                "type": "string",
                "description": "Voice name (system-dependent)",
                "default": None,
            },
            "rate": {
                "type": "integer",
                "description": "Speech rate in words per minute",
                "default": 200,
                "min": 50,
                "max": 500,
            },
            "volume": {
                "type": "float",
                "description": "Speech volume (0.0 to 1.0)",
                "default": 1.0,
                "min": 0.0,
                "max": 1.0,
            },
        }

    def configure(self, config: Dict[str, Any]) -> bool:
        """
        Configure the system TTS provider.

        Args:
            config: Configuration dictionary

        Returns:
            True if configuration was successful
        """
        try:
            self.voice = config.get('voice', self.voice)
            self.rate = config.get('rate', self.rate)
            self.volume = config.get('volume', self.volume)

            # Validate rate
            if self.rate and not (50 <= self.rate <= 500):
                logger.warning(f"🔊 Invalid TTS rate {self.rate}, using default 200")
                self.rate = 200

            # Validate volume
            if self.volume and not (0.0 <= self.volume <= 1.0):
                logger.warning(f"🔊 Invalid TTS volume {self.volume}, using default 1.0")
                self.volume = 1.0

            logger.info(f"🔊 System TTS configured: voice={self.voice}, rate={self.rate}")
            return True

        except Exception as e:
            logger.error(f"🔊 System TTS configuration error: {e}")
            return False

    def get_available_voices(self) -> List[str]:
        """
        Get list of available voices (if supported by the command).

        Returns:
            List of voice names
        """
        if not self.is_available():
            return []

        try:
            if self.selected_command == 'say':  # macOS
                result = subprocess.run(
                    ['say', '-v', '?'],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    voices = []
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            # Extract voice name (first word)
                            voice_name = line.split()[0]
                            if voice_name:
                                voices.append(voice_name)
                    return voices

            elif self.selected_command in ['espeak', 'espeak-ng']:
                result = subprocess.run(
                    [self.selected_command, '--voices'],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    voices = []
                    for line in result.stdout.split('\n')[1:]:  # Skip header
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 2:
                                voices.append(parts[1])  # Language code
                    return voices

            return []

        except Exception as e:
            logger.debug(f"🔊 Could not get available voices: {e}")
            return []

    def stop(self) -> bool:
        """
        Stop current TTS playback.

        Returns:
            True if stop was successful
        """
        if self._current_process:
            try:
                self._current_process.kill()
                self._current_process = None
                logger.debug("🔊 TTS playback stopped")
                return True
            except Exception as e:
                logger.error(f"🔊 Failed to stop TTS: {e}")
                return False
        return True

    def test_speech(self, test_text: str = "Hello, this is a test of the text to speech system.") -> bool:
        """
        Test TTS with sample text.

        Args:
            test_text: Text to use for testing

        Returns:
            True if test was successful
        """
        logger.info(f"🔊 Testing system TTS with: {self.selected_command}")
        return self.speak(test_text)