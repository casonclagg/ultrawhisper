#!/usr/bin/env python3
"""
Mode-specific logging for UltraWhisper.

Handles separate log files for transcription and question modes.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from .mode import Mode


class ModeLogger:
    """Handles logging for different UltraWhisper modes."""

    def __init__(self, config_manager=None):
        """
        Initialize the mode logger.

        Args:
            config_manager: ConfigManager instance to get config directory path
        """
        self.config_manager = config_manager

        # Determine log directory - use ~/.config/ultrawhisper/
        if config_manager:
            config_path = Path(config_manager.get_config_path())
            self.log_dir = config_path.parent
        else:
            # Fallback to XDG config directory
            config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
            self.log_dir = Path(config_home).expanduser() / 'ultrawhisper'

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log file paths
        self.transcription_log = self.log_dir / 'transcriptions.log'
        self.question_log = self.log_dir / 'questions.log'

        logger.info(f"📝 ModeLogger initialized - logs in {self.log_dir}")
        logger.info(f"  Transcription log: {self.transcription_log}")
        logger.info(f"  Question log: {self.question_log}")

    def get_log_path(self, mode: Mode) -> Path:
        """
        Get the log file path for a specific mode.

        Args:
            mode: Mode to get log path for

        Returns:
            Path to the log file for the mode
        """
        if mode == Mode.QUESTION:
            return self.question_log
        else:
            return self.transcription_log

    def log_transcription(self, text: str, corrected_text: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a transcription event.

        Args:
            text: Original transcribed text
            corrected_text: LLM-corrected text (if available)
            context: Application context information
        """
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        app_name = context.get('app', 'unknown') if context else 'unknown'

        try:
            with open(self.transcription_log, 'a', encoding='utf-8') as f:
                # Log original transcription
                f.write(f"{timestamp} TRANSCRIPTION | App: {app_name} | \"{text}\"\n")

                # Log corrected text if different
                if corrected_text and corrected_text != text:
                    f.write(f"{timestamp} CORRECTED | App: {app_name} | \"{corrected_text}\"\n")

        except Exception as e:
            logger.error(f"Failed to write to transcription log: {e}")

    def log_question_answer(self, question: str, answer: str,
                           context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a question/answer interaction.

        Args:
            question: User's question
            answer: Assistant's response
            context: Application context information
        """
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        app_name = context.get('app', 'unknown') if context else 'unknown'

        try:
            with open(self.question_log, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp} QUESTION | App: {app_name} | User: \"{question}\"\n")
                f.write(f"{timestamp} ANSWER | App: {app_name} | Assistant: \"{answer}\"\n")

        except Exception as e:
            logger.error(f"Failed to write to question log: {e}")

    def log_mode_switch(self, old_mode: Mode, new_mode: Mode,
                       context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a mode switching event.

        Args:
            old_mode: Previous mode
            new_mode: New mode
            context: Application context information
        """
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        app_name = context.get('app', 'unknown') if context else 'unknown'

        # Log to both files for visibility
        switch_message = f"{timestamp} MODE_SWITCH | App: {app_name} | {old_mode.value} → {new_mode.value}\n"

        try:
            with open(self.transcription_log, 'a', encoding='utf-8') as f:
                f.write(switch_message)
        except Exception as e:
            logger.error(f"Failed to write mode switch to transcription log: {e}")

        try:
            with open(self.question_log, 'a', encoding='utf-8') as f:
                f.write(switch_message)
        except Exception as e:
            logger.error(f"Failed to write mode switch to question log: {e}")

    def log_conversation_summary(self, summary: Dict[str, Any]) -> None:
        """
        Log a conversation summary to the question log.

        Args:
            summary: Conversation summary dictionary
        """
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

        try:
            with open(self.question_log, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp} CONVERSATION_SUMMARY | ")
                f.write(f"Messages: {summary['total_messages']}, ")
                f.write(f"Turns: {summary['turns']}, ")
                f.write(f"Contexts: {', '.join(summary['active_contexts']) if summary['active_contexts'] else 'None'}\n")

        except Exception as e:
            logger.error(f"Failed to write conversation summary: {e}")

    def get_recent_transcriptions(self, limit: int = 10) -> list[str]:
        """
        Get recent transcription entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent transcription log lines
        """
        try:
            if not self.transcription_log.exists():
                return []

            with open(self.transcription_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-limit:]]

        except Exception as e:
            logger.error(f"Failed to read transcription log: {e}")
            return []

    def get_recent_questions(self, limit: int = 10) -> list[str]:
        """
        Get recent question/answer entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent question log lines
        """
        try:
            if not self.question_log.exists():
                return []

            with open(self.question_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-limit:]]

        except Exception as e:
            logger.error(f"Failed to read question log: {e}")
            return []

    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the log files.

        Returns:
            Dictionary with log statistics
        """
        stats = {
            "transcription_log_exists": self.transcription_log.exists(),
            "question_log_exists": self.question_log.exists(),
            "transcription_entries": 0,
            "question_entries": 0,
        }

        try:
            if stats["transcription_log_exists"]:
                with open(self.transcription_log, 'r', encoding='utf-8') as f:
                    stats["transcription_entries"] = sum(1 for _ in f)
        except Exception as e:
            logger.error(f"Failed to count transcription entries: {e}")

        try:
            if stats["question_log_exists"]:
                with open(self.question_log, 'r', encoding='utf-8') as f:
                    stats["question_entries"] = sum(1 for line in f if "QUESTION" in line)
        except Exception as e:
            logger.error(f"Failed to count question entries: {e}")

        return stats