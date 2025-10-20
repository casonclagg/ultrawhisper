#!/usr/bin/env python3
"""
Conversation history management for UltraWhisper question mode.

Maintains conversation context for enhanced LLM responses.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger


@dataclass
class Message:
    """A single message in the conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None  # Application context when message was sent

    def to_llm_format(self) -> Dict[str, str]:
        """Convert message to LLM API format."""
        return {
            "role": self.role,
            "content": self.content
        }

    def to_log_format(self) -> str:
        """Convert message to log format."""
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        app_name = self.context.get('app', 'unknown') if self.context else 'unknown'
        return f"[{timestamp_str}] {self.role.upper()} | App: {app_name} | \"{self.content}\""


class ConversationHistory:
    """Manages conversation history for question mode."""

    def __init__(self, max_turns: int = 30):
        """
        Initialize conversation history.

        Args:
            max_turns: Maximum number of turns to keep (60 messages total)
        """
        self.max_turns = max_turns
        self.messages: List[Message] = []

        logger.info(f"🗨️ Conversation history initialized - max turns: {max_turns}")

    def add_user_message(self, content: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a user message to the conversation history.

        Args:
            content: User's message content
            context: Application context when message was sent
        """
        message = Message(
            role="user",
            content=content,
            timestamp=datetime.now(),
            context=context
        )

        self.messages.append(message)
        self._trim_to_limit()

        logger.debug(f"🗨️ Added user message: {content[:50]}...")

    def add_assistant_message(self, content: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Add an assistant message to the conversation history.

        Args:
            content: Assistant's message content
            context: Application context when message was sent
        """
        message = Message(
            role="assistant",
            content=content,
            timestamp=datetime.now(),
            context=context
        )

        self.messages.append(message)
        self._trim_to_limit()

        logger.debug(f"🗨️ Added assistant message: {content[:50]}...")

    def _trim_to_limit(self) -> None:
        """Trim conversation history to stay within message limits."""
        # Keep only the last (max_turns * 2) messages
        max_messages = self.max_turns * 2

        if len(self.messages) > max_messages:
            old_count = len(self.messages)
            self.messages = self.messages[-max_messages:]
            logger.debug(f"🗨️ Trimmed conversation history: {old_count} → {len(self.messages)} messages")

    def get_context_for_llm(self) -> List[Dict[str, str]]:
        """
        Convert conversation history to LLM message format.

        Returns:
            List of messages in LLM API format
        """
        return [message.to_llm_format() for message in self.messages]

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """
        Get recent messages from conversation history.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of recent messages
        """
        return self.messages[-limit:]

    def clear_history(self) -> None:
        """Clear all conversation history."""
        old_count = len(self.messages)
        self.messages.clear()
        logger.info(f"🗨️ Cleared conversation history ({old_count} messages)")

    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get summary information about the conversation.

        Returns:
            Dictionary with conversation statistics
        """
        if not self.messages:
            return {
                "total_messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "turns": 0,
                "first_message": None,
                "last_message": None,
                "active_contexts": [],
            }

        user_messages = sum(1 for msg in self.messages if msg.role == "user")
        assistant_messages = sum(1 for msg in self.messages if msg.role == "assistant")

        # Get unique contexts from recent messages
        contexts = set()
        for msg in self.messages[-10:]:  # Last 10 messages
            if msg.context and msg.context.get('app'):
                contexts.add(msg.context['app'])

        return {
            "total_messages": len(self.messages),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "turns": min(user_messages, assistant_messages),  # Complete turns
            "first_message": self.messages[0].timestamp if self.messages else None,
            "last_message": self.messages[-1].timestamp if self.messages else None,
            "active_contexts": list(contexts),
        }

    def export_to_log_format(self) -> List[str]:
        """
        Export conversation history in log format.

        Returns:
            List of log-formatted message strings
        """
        return [message.to_log_format() for message in self.messages]

    def get_context_transitions(self) -> List[Dict[str, Any]]:
        """
        Analyze context transitions in the conversation.

        Returns:
            List of context transition events
        """
        if len(self.messages) < 2:
            return []

        transitions = []
        current_context = None

        for message in self.messages:
            msg_context = message.context.get('app', 'unknown') if message.context else 'unknown'

            if current_context and msg_context != current_context:
                transitions.append({
                    "timestamp": message.timestamp,
                    "from_context": current_context,
                    "to_context": msg_context,
                    "message_role": message.role,
                })

            current_context = msg_context

        return transitions

    def has_recent_context(self, context_app: str, within_messages: int = 5) -> bool:
        """
        Check if a specific context appears in recent messages.

        Args:
            context_app: Application name to look for
            within_messages: Number of recent messages to check

        Returns:
            True if context appears in recent messages
        """
        recent_messages = self.messages[-within_messages:]

        for message in recent_messages:
            if message.context and message.context.get('app') == context_app:
                return True

        return False

    def get_messages_in_context(self, context_app: str, limit: int = 10) -> List[Message]:
        """
        Get messages that occurred in a specific application context.

        Args:
            context_app: Application name to filter by
            limit: Maximum number of messages to return

        Returns:
            List of messages in the specified context
        """
        context_messages = []

        for message in reversed(self.messages):
            if len(context_messages) >= limit:
                break

            if message.context and message.context.get('app') == context_app:
                context_messages.append(message)

        return list(reversed(context_messages))

    def __len__(self) -> int:
        """Return the number of messages in history."""
        return len(self.messages)

    def __bool__(self) -> bool:
        """Return True if history has messages."""
        return len(self.messages) > 0