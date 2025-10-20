#!/usr/bin/env python3
"""
Hotkey management functionality for UltraWhisper.
"""

import time
import logging
from typing import Dict, Any, Callable

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

# Configure logging
logger = logging.getLogger("ultrawhisper.ui")


class HotkeyManager:
    """Manages global hotkeys for the application."""

    def __init__(
        self,
        config: Dict[str, Any],
        callback: Callable,
        push_to_talk_config: Dict[str, Any] = None,
    ):
        """
        Initialize the hotkey manager.

        Args:
            config: Hotkey configuration dictionary
            callback: Function to call when the hotkey is pressed
            push_to_talk_config: Push-to-talk configuration dictionary
        """
        self.key = config.get("key", "cmd")
        self.modifier_str = config.get("modifier", "Key.cmd")
        self.use_double_tap = config.get("use_double_tap", True)
        self.callback = callback

        # Push-to-talk configuration
        self.push_to_talk_enabled = False
        self.push_to_talk_key = None

        if push_to_talk_config and push_to_talk_config.get("enabled", False):
            self.push_to_talk_enabled = True
            self.push_to_talk_key_str = push_to_talk_config.get("key", "space")

            # Convert push-to-talk key string to actual Key object if needed
            if self.push_to_talk_key_str.startswith("Key."):
                key_name = self.push_to_talk_key_str[4:]  # Remove "Key." prefix
                self.push_to_talk_key = getattr(Key, key_name, None)
            else:
                self.push_to_talk_key = KeyCode.from_char(self.push_to_talk_key_str)

            logger.info(f"Push-to-talk enabled with key: {self.push_to_talk_key_str}")

        # Convert modifier string to actual Key object if needed
        if self.modifier_str.startswith("Key."):
            key_name = self.modifier_str[4:]  # Remove "Key." prefix
            self.modifier = getattr(Key, key_name, None)
        else:
            self.modifier = KeyCode.from_char(self.modifier_str)

        # For double-tap detection
        self.last_press_time = 0
        self.double_tap_threshold = 0.3  # seconds

        # Track key states
        self.modifier_pressed = False
        self.push_to_talk_active = False

        # Create keyboard listeners
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )

        logger.info(
            f"Initialized HotkeyManager with key={self.key}, modifier={self.modifier_str}, double_tap={self.use_double_tap}"
        )

    def start(self):
        """Start listening for hotkeys."""
        self.keyboard_listener.start()
        logger.info("Started hotkey listener")

    def stop(self):
        """Stop listening for hotkeys."""
        if self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
            logger.info("Stopped hotkey listener")

    def _on_press(self, key):
        """Handle key press events."""
        try:
            # Check for push-to-talk key
            if (
                self.push_to_talk_enabled
                and key == self.push_to_talk_key
                and not self.push_to_talk_active
            ):
                logger.debug(f"Push-to-talk key pressed: {self.push_to_talk_key_str}")
                self.push_to_talk_active = True
                self.callback()  # Start recording
                return

            # Check if the modifier key is pressed
            if key == self.modifier:
                self.modifier_pressed = True

                # For double-tap detection
                if self.use_double_tap:
                    current_time = time.time()
                    if current_time - self.last_press_time < self.double_tap_threshold:
                        logger.debug(f"Double-tap detected on {key}")
                        self.callback()
                    self.last_press_time = current_time

            # Check if the hotkey combination is pressed
            elif (
                self.modifier_pressed and hasattr(key, "char") and key.char == self.key
            ):
                logger.debug(
                    f"Hotkey combination detected: {self.modifier_str}+{self.key}"
                )
                self.callback()

        except AttributeError:
            # Some keys don't have a char attribute
            pass

    def _on_release(self, key):
        """Handle key release events."""
        if key == self.modifier:
            self.modifier_pressed = False

        # Handle push-to-talk key release
        if (
            self.push_to_talk_enabled
            and key == self.push_to_talk_key
            and self.push_to_talk_active
        ):
            logger.debug(f"Push-to-talk key released: {self.push_to_talk_key_str}")
            self.push_to_talk_active = False
            self.callback()  # Stop recording
