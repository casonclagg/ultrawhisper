#!/usr/bin/env python3
"""
Notification utilities for UltraWhisper.
"""

import os
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger("ultrawhisper.ui.notifications")


class NotificationManager:
    """Manages audio and visual notifications."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the notification manager.

        Args:
            config: Notification configuration dictionary
        """
        self.config = config or {}
        self.sounds_dir = Path(__file__).parent.parent / "audio" / "sounds"
        self.sounds_dir.mkdir(exist_ok=True)

        # Default sound files
        self.start_sound = self.sounds_dir / "start.wav"
        self.stop_sound = self.sounds_dir / "stop.wav"

        # Check if sound files exist, if not, create them
        self._ensure_sound_files()

        # Check if notifications are enabled
        self.audio_enabled = self.config.get("audio_enabled", True)
        self.visual_enabled = self.config.get("visual_enabled", True)

    def _ensure_sound_files(self):
        """Ensure sound files exist, create them if they don't."""
        # We'll use simple beep sounds if files don't exist
        if not self.start_sound.exists():
            self._create_pleasant_sound(
                self.start_sound, frequency=1000, duration=0.15, fade_in=True
            )

        if not self.stop_sound.exists():
            self._create_pleasant_sound(
                self.stop_sound, frequency=800, duration=0.15, fade_out=True
            )

    def _create_beep_sound(
        self, file_path: Path, frequency: int = 1000, duration: float = 0.1
    ):
        """
        Create a simple beep sound file.

        Args:
            file_path: Path to save the sound file
            frequency: Frequency of the beep in Hz
            duration: Duration of the beep in seconds
        """
        try:
            import numpy as np
            from scipy.io import wavfile

            # Generate a simple beep sound
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            beep = 0.5 * np.sin(2 * np.pi * frequency * t)

            # Save as WAV file
            wavfile.write(file_path, sample_rate, beep.astype(np.float32))
            logger.info(f"Created beep sound file: {file_path}")
        except ImportError:
            logger.warning(
                "Could not create beep sound file: scipy or numpy not installed"
            )

    def _create_pleasant_sound(
        self,
        file_path: Path,
        frequency: int = 1000,
        duration: float = 0.15,
        fade_in: bool = False,
        fade_out: bool = False,
    ):
        """
        Create a more pleasant notification sound with optional fade in/out.

        Args:
            file_path: Path to save the sound file
            frequency: Base frequency of the sound in Hz
            duration: Duration of the sound in seconds
            fade_in: Whether to apply fade-in effect
            fade_out: Whether to apply fade-out effect
        """
        try:
            import numpy as np
            from scipy.io import wavfile

            # Generate a more pleasant sound
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration), False)

            # Create a sound with harmonics for a more pleasant tone
            sound = 0.3 * np.sin(2 * np.pi * frequency * t)  # Base frequency
            sound += 0.15 * np.sin(
                2 * np.pi * (frequency * 1.5) * t
            )  # Add first harmonic
            sound += 0.05 * np.sin(
                2 * np.pi * (frequency * 2) * t
            )  # Add second harmonic

            # Apply fade in/out if requested
            if fade_in or fade_out:
                fade_duration = min(0.05, duration / 3)
                fade_samples = int(fade_duration * sample_rate)

                if fade_in and fade_samples > 0:
                    fade_in_curve = np.linspace(0, 1, fade_samples)
                    sound[:fade_samples] *= fade_in_curve

                if fade_out and fade_samples > 0:
                    fade_out_curve = np.linspace(1, 0, fade_samples)
                    sound[-fade_samples:] *= fade_out_curve

            # Save as WAV file
            wavfile.write(file_path, sample_rate, sound.astype(np.float32))
            logger.info(f"Created pleasant sound file: {file_path}")
        except ImportError:
            logger.warning("Could not create sound file: scipy or numpy not installed")
            # Fall back to simple beep sound
            self._create_beep_sound(file_path, frequency, duration)

    def play_sound(self, sound_type: str):
        """
        Play a notification sound.

        Args:
            sound_type: Type of sound to play ('start' or 'stop')
        """
        if not self.audio_enabled:
            return

        sound_file = self.start_sound if sound_type == "start" else self.stop_sound

        if not sound_file.exists():
            logger.warning(f"Sound file not found: {sound_file}")
            return

        # Play sound in a separate thread to avoid blocking
        threading.Thread(
            target=self._play_sound_file, args=(sound_file,), daemon=True
        ).start()

    def _play_sound_file(self, sound_file: Path):
        """
        Play a sound file using an appropriate player.

        Args:
            sound_file: Path to the sound file
        """
        try:
            # Try using different players based on availability
            for player in ["aplay", "paplay", "play", "afplay"]:
                try:
                    subprocess.run(
                        [player, str(sound_file)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    return
                except FileNotFoundError:
                    continue

            logger.warning("No suitable audio player found")
        except Exception as e:
            logger.error(f"Error playing sound: {e}")

    def show_notification(self, title: str, message: str):
        """
        Show a desktop notification.

        Args:
            title: Notification title
            message: Notification message
        """
        if not self.visual_enabled:
            return

        # Show notification in a separate thread to avoid blocking
        threading.Thread(
            target=self._show_notification, args=(title, message), daemon=True
        ).start()

    def _show_notification(self, title: str, message: str):
        """
        Show a desktop notification using an appropriate method.

        Args:
            title: Notification title
            message: Notification message
        """
        try:
            # Try using different notification methods based on availability
            try:
                # Try using notify-send (Linux)
                subprocess.run(
                    ["notify-send", title, message],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                return
            except FileNotFoundError:
                pass

            try:
                # Try using osascript (macOS)
                apple_script = f'display notification "{message}" with title "{title}"'
                subprocess.run(
                    ["osascript", "-e", apple_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                return
            except FileNotFoundError:
                pass

            logger.warning("No suitable notification method found")
        except Exception as e:
            logger.error(f"Error showing notification: {e}")

    def notify_recording_start(self):
        """Notify that recording has started."""
        if self.audio_enabled:
            self.play_sound("start")
        if self.visual_enabled:
            self.show_notification("UltraWhisper", "Recording started")

    def notify_recording_stop(self):
        """Notify that recording has stopped."""
        if self.audio_enabled:
            self.play_sound("stop")
        if self.visual_enabled:
            self.show_notification("UltraWhisper", "Recording stopped")
