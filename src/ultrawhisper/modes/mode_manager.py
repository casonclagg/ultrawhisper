#!/usr/bin/env python3
"""
Mode management for UltraWhisper.

Handles mode switching between transcription and question modes.
"""

import re
from typing import Dict, Any, Optional, Callable, Union
from loguru import logger

from .mode import Mode
from .conversation_history import ConversationHistory
from ultrawhisper.config.models import UltraWhisperConfig


class ModeManager:
    """Manages mode switching and detection for UltraWhisper."""

    def __init__(self, config: Union[UltraWhisperConfig, Dict[str, Any]] = None):
        """
        Initialize the mode manager.

        Args:
            config: Configuration object (UltraWhisperConfig) or dictionary
        """
        self.config = config or {}

        # Get default mode from config, fallback to transcription
        if hasattr(self.config, 'modes'):
            # Pydantic config
            default_mode_str = self.config.modes.default if self.config.modes else "transcription"
        else:
            # Dict config (fallback)
            default_mode_str = self.config.get("modes", {}).get("default", "transcription")
        self.current_mode = Mode.from_string(default_mode_str) or Mode.TRANSCRIPTION

        # Callback for mode changes
        self._mode_change_callback: Optional[Callable[[Mode, Mode], None]] = None

        # Initialize conversation history for question mode
        if hasattr(self.config, 'modes'):
            # Pydantic config
            conversation_limit = (self.config.modes.question.conversation_history
                                if self.config.modes and self.config.modes.question else 30)
        else:
            # Dict config (fallback)
            conversation_limit = self.config.get("modes", {}).get("question", {}).get("conversation_history", 30)
        self.conversation_history = ConversationHistory(max_turns=conversation_limit)

        logger.info(f"🔄 ModeManager initialized with default mode: {self.current_mode}")

    def set_mode_change_callback(self, callback: Callable[[Mode, Mode], None]) -> None:
        """
        Set callback function to be called when mode changes.

        Args:
            callback: Function to call with (old_mode, new_mode) when mode changes
        """
        self._mode_change_callback = callback

    def get_current_mode(self) -> Mode:
        """Get the current active mode."""
        return self.current_mode

    def switch_mode(self, new_mode: Mode) -> bool:
        """
        Switch to a new mode.

        Args:
            new_mode: Mode to switch to

        Returns:
            True if mode was changed, False if already in that mode
        """
        if new_mode == self.current_mode:
            logger.debug(f"Already in {new_mode} mode")
            return False

        old_mode = self.current_mode
        self.current_mode = new_mode

        logger.info(f"🔄 Mode switched: {old_mode} → {new_mode}")

        # Call mode change callback if set
        if self._mode_change_callback:
            try:
                self._mode_change_callback(old_mode, new_mode)
            except Exception as e:
                logger.error(f"Error in mode change callback: {e}")

        return True

    def detect_mode_command(self, text: str) -> Optional[Mode]:
        """
        Detect mode switching commands from transcribed text.

        Args:
            text: Transcribed text to analyze

        Returns:
            Mode to switch to if command detected, None otherwise
        """
        if not text:
            return None

        # Normalize text: lowercase and strip whitespace
        normalized = text.lower().strip()

        # Remove common punctuation that might interfere
        normalized = re.sub(r'[.!?,:;]', '', normalized).strip()

        logger.info(f"Detecting '{normalized}'")

        # Get trigger phrases from config
        transcription_triggers = []
        question_triggers = []

        if hasattr(self.config, 'modes'):
            # Pydantic config
            if self.config.modes:
                if hasattr(self.config.modes, 'transcription') and self.config.modes.transcription:
                    transcription_triggers = self.config.modes.transcription.trigger_phrases
                if hasattr(self.config.modes, 'question') and self.config.modes.question:
                    question_triggers = self.config.modes.question.trigger_phrases
        else:
            # Dict config (fallback)
            transcription_triggers = self.config.get("modes", {}).get("transcription", {}).get("trigger_phrases", ["transcription mode"])
            question_triggers = self.config.get("modes", {}).get("question", {}).get("trigger_phrases", ["question mode"])

        # Check for transcription mode triggers
        for trigger in transcription_triggers:
            trigger_normalized = trigger.lower().strip()
            if normalized == trigger_normalized:
                logger.info("Changing to Transcription Mode")
                return Mode.TRANSCRIPTION

        # Check for question mode triggers
        for trigger in question_triggers:
            trigger_normalized = trigger.lower().strip()
            if normalized == trigger_normalized:
                logger.info("Changing to Chat Mode")
                return Mode.QUESTION

        return None

    def is_mode_command(self, text: str) -> bool:
        """
        Check if text contains a mode switching command.

        Args:
            text: Text to check

        Returns:
            True if text is a mode command
        """
        return self.detect_mode_command(text) is not None

    def process_transcription(self, text: str) -> tuple[Optional[Mode], bool]:
        """
        Process transcribed text to check for mode commands.

        Args:
            text: Transcribed text

        Returns:
            Tuple of (detected_mode, should_consume_text)
            - detected_mode: Mode to switch to if command detected
            - should_consume_text: True if text should not be passed to LLM/output
        """
        detected_mode = self.detect_mode_command(text)

        if detected_mode:
            # Mode command detected - consume the text (don't process further)
            self.switch_mode(detected_mode)
            return detected_mode, True

        # No mode command - continue normal processing
        return None, False

    def get_mode_config(self, mode: Optional[Mode] = None) -> Dict[str, Any]:
        """
        Get configuration for the specified mode.

        Args:
            mode: Mode to get config for, defaults to current mode

        Returns:
            Configuration dictionary for the mode
        """
        if mode is None:
            mode = self.current_mode

        if mode == Mode.QUESTION:
            if hasattr(self.config, 'modes'):
                # Pydantic config - convert to dict
                if self.config.modes and self.config.modes.question:
                    return self.config.modes.question.model_dump()
                else:
                    return {}
            else:
                # Dict config (fallback)
                modes_config = self.config.get("modes", {})
                return modes_config.get("question", {})
        else:
            # Return empty dict for transcription mode (uses existing LLM config)
            return {}

    def add_user_message(self, content: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Add user message to conversation history (question mode only).

        Args:
            content: User's message content
            context: Application context when message was sent
        """
        if self.current_mode == Mode.QUESTION:
            self.conversation_history.add_user_message(content, context)

    def add_assistant_message(self, content: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Add assistant message to conversation history (question mode only).

        Args:
            content: Assistant's message content
            context: Application context when message was sent
        """
        if self.current_mode == Mode.QUESTION:
            self.conversation_history.add_assistant_message(content, context)

    def get_conversation_context(self) -> list[Dict[str, str]]:
        """
        Get conversation history for LLM context.

        Returns:
            List of messages in LLM format
        """
        if self.current_mode == Mode.QUESTION:
            return self.conversation_history.get_context_for_llm()
        return []

    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history.clear_history()

    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get conversation summary information.

        Returns:
            Dictionary with conversation statistics
        """
        return self.conversation_history.get_conversation_summary()

    def get_status_info(self) -> Dict[str, Any]:
        """
        Get status information about the current mode.

        Returns:
            Dictionary with mode status information
        """
        status = {
            "current_mode": self.current_mode.value,
            "mode_display": self.current_mode.value.title(),
        }

        # Add conversation info for question mode
        if self.current_mode == Mode.QUESTION:
            conv_summary = self.get_conversation_summary()
            status["conversation"] = {
                "total_messages": conv_summary["total_messages"],
                "turns": conv_summary["turns"],
                "active_contexts": conv_summary["active_contexts"],
            }

        return status