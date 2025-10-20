#!/usr/bin/env python3
"""
LLM Service - A unified interface for different LLM providers using OpenAI-compatible APIs

This module provides a unified service for interacting with various LLM providers
using the OpenAI client library for consistent API access.
"""

import time
from typing import Dict, Any, Optional
from loguru import logger

# Import LLM libraries
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from ultrawhisper.logging_config import LogHelper


class LLMServiceException(Exception):
    """Exception raised for errors in the LLM Service."""

    pass


class LLMService:
    """
    A unified service for interacting with different LLM providers.

    This service uses OpenAI-compatible APIs for most providers and Anthropic's
    native client for Claude models.
    """

    def __init__(self, full_config: Any):
        """
        Initialize the LLM service with configuration.

        Args:
            full_config: Full application configuration (UltraWhisperConfig Pydantic model)
        """
        self.full_config = full_config

        # Access Pydantic model attributes directly
        self.provider = full_config.llm.provider
        self.model = full_config.llm.model
        self.api_key = full_config.llm.api_key
        self.base_url = full_config.llm.base_url
        self.system_prompt = full_config.llm.base_prompt
        self.skip_if_unavailable = full_config.llm.skip_if_unavailable

        # Initialize clients
        self.openai_client = None
        self.anthropic_client = None

        logger.info(f"🤖 LLM Service Configuration:")
        logger.info(f"  Provider: {self.provider}")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Base URL: {self.base_url}")
        logger.info(f"  API Key: {'***' if self.api_key else 'None'}")
        logger.info(f"  Skip if unavailable: {self.skip_if_unavailable}")

        # Log service configuration status
        LogHelper.service_status(
            f"LLM ({self.provider})", "configured", f"{self.model} @ {self.base_url}"
        )

        # Initialize the appropriate client
        try:
            if self.provider == "anthropic":
                if ANTHROPIC_AVAILABLE and self.api_key:
                    self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
                    logger.info("Anthropic client initialized")
                else:
                    raise LLMServiceException(
                        "Anthropic client not available or no API key"
                    )
            else:
                # Use OpenAI client for openai and openai-compatible providers
                if OPENAI_AVAILABLE:
                    client_kwargs = {"base_url": self.base_url}
                    if self.api_key:
                        client_kwargs["api_key"] = self.api_key
                    else:
                        # For local servers that don't require API keys
                        client_kwargs["api_key"] = "not-needed"

                    self.openai_client = OpenAI(**client_kwargs)
                    logger.info(
                        f"OpenAI-compatible client initialized for {self.provider}"
                    )
                else:
                    raise LLMServiceException("OpenAI client not available")

        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            if not self.skip_if_unavailable:
                raise LLMServiceException(f"Failed to initialize LLM client: {e}")

    def is_available(self) -> bool:
        """Check if the LLM service is available."""
        if self.provider == "anthropic":
            return self.anthropic_client is not None
        else:
            return self.openai_client is not None

    def check_availability(self) -> bool:
        """Test if the LLM service can actually be reached."""
        if not self.is_available():
            logger.warning(f"❌ LLM client not initialized for {self.provider}")
            return False

        try:
            logger.info(f"🔍 Testing connection to {self.provider} at {self.base_url}")

            if self.provider == "anthropic":
                # Simple test with Anthropic
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}],
                )
                logger.info(f"✅ Anthropic connection successful")
                return True
            else:
                # Test OpenAI-compatible endpoint
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=10,
                )
                logger.info(
                    f"✅ OpenAI-compatible connection successful to {self.base_url}"
                )
                return True

        except Exception as e:
            logger.warning(f"❌ Connection test failed for {self.provider}: {e}")
            return False

    def correct_text(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Correct transcribed text using the configured LLM with context awareness.

        Args:
            text: The text to correct
            context: Optional application context for prompt customization

        Returns:
            Dictionary with corrected text and metadata
        """
        if not self.is_available():
            if self.skip_if_unavailable:
                logger.warning(
                    f"⚠️ LLM service not available ({self.provider}), returning original text"
                )
                return {
                    "corrected_text": text,
                    "original_text": text,
                    "provider": self.provider,
                    "model": self.model,
                    "error": "Service not available",
                    "usage": {},
                    "context": context,
                }
            else:
                raise LLMServiceException("LLM service not available")

        # Construct context-aware prompt using full config
        from ultrawhisper.config.config import construct_layered_prompt, log_correction

        base_prompt = construct_layered_prompt(self.full_config, context)

        # Combine the layered prompt with the transcribed text in the system prompt
        effective_prompt = f"{base_prompt}\n\nTranscribed from STT:\n{text}"

        # Use LogHelper for LLM request logging
        LogHelper.llm_request(self.provider, self.model, self.base_url, len(text))

        # Log the full system prompt being used
        log_prompts = self.full_config.logging.log_prompts

        # Debug: Always show prompt logging status
        logger.debug(
            f"🔧 LLM Service: log_prompts={log_prompts}"
        )

        if log_prompts:
            logger.info(f"🎯 System Prompt Being Used:")
            logger.info(f"  Length: {len(effective_prompt)} characters")
            logger.info(f"  Content: {effective_prompt}")
        else:
            logger.debug(f"  System prompt length: {len(effective_prompt)} characters")
            logger.debug(f"  System prompt preview: {effective_prompt[:100]}...")

        # Log the messages that will be sent (for text correction mode)
        if self.provider == "anthropic":
            logger.info(f"🔄 LLM Text Correction Request (Anthropic):")
            logger.info(f"  SYSTEM: {effective_prompt[:200]}{'...' if len(effective_prompt) > 200 else ''}")
            logger.info(f"  USER: Please correct the transcribed text above.")
        else:
            logger.info(f"🔄 LLM Text Correction Request (OpenAI-compatible):")
            logger.info(f"  SYSTEM: {effective_prompt[:200]}{'...' if len(effective_prompt) > 200 else ''}")
            logger.info(f"  USER: Please correct the transcribed text above.")

        try:
            # Record timing for logging
            start_time = time.time()

            if self.provider == "anthropic":
                result = self._correct_with_anthropic_context(effective_prompt)
            else:
                result = self._correct_with_openai_compatible_context(effective_prompt)

            # Calculate duration
            duration = time.time() - start_time

            # Add context information to result
            result["context"] = context
            result["prompt_used"] = effective_prompt

            # Log successful response using LogHelper
            corrected_text = result.get("corrected_text", "")
            usage = result.get("usage", {})
            logger.info(f"🤖 LLM Text Correction Response: {corrected_text[:200]}{'...' if len(corrected_text) > 200 else ''}")
            LogHelper.llm_response(corrected_text, duration, usage)

            # Log correction if enabled
            log_correction(text, result["corrected_text"], context, self.full_config)

            return result

        except Exception as e:
            LogHelper.llm_error(self.provider, str(e))
            if self.skip_if_unavailable:
                logger.warning(
                    f"⚠️ Returning original text due to skip_if_unavailable=True"
                )
                return {
                    "corrected_text": text,
                    "original_text": text,
                    "provider": self.provider,
                    "model": self.model,
                    "error": str(e),
                    "usage": {},
                    "context": context,
                }
            else:
                raise LLMServiceException(f"Error correcting text: {e}")

    def _correct_with_anthropic_context(self, system_prompt: str) -> Dict[str, Any]:
        """Correct text using Anthropic's Claude API with custom prompt."""
        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                # max_tokens=1000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "Please correct the transcribed text above.",
                    }
                ],
            )

            corrected_text = response.content[0].text.strip()

            return {
                "corrected_text": corrected_text,
                "original_text": "",  # Original text is now embedded in system prompt
                "provider": self.provider,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens
                    + response.usage.output_tokens,
                },
            }

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def _correct_with_openai_compatible_context(
        self, system_prompt: str
    ) -> Dict[str, Any]:
        """Correct text using OpenAI-compatible API with custom prompt."""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": "Please correct the transcribed text above.",
                    },
                ],
                # max_tokens=1000,
                temperature=0.3,
            )

            corrected_text = response.choices[0].message.content.strip()

            # Handle usage info (might not be available for all providers)
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": (
                        response.usage.prompt_tokens
                        if hasattr(response.usage, "prompt_tokens")
                        else 0
                    ),
                    "completion_tokens": (
                        response.usage.completion_tokens
                        if hasattr(response.usage, "completion_tokens")
                        else 0
                    ),
                    "total_tokens": (
                        response.usage.total_tokens
                        if hasattr(response.usage, "total_tokens")
                        else 0
                    ),
                }

            return {
                "corrected_text": corrected_text,
                "original_text": "",  # Original text is now embedded in system prompt
                "provider": self.provider,
                "model": self.model,
                "usage": usage,
            }

        except Exception as e:
            logger.error(f"OpenAI-compatible API error: {e}")
            raise

    # Legacy methods for backward compatibility
    def _correct_with_anthropic(self, text: str) -> Dict[str, Any]:
        """Legacy method - use _correct_with_anthropic_context instead."""
        system_prompt = f"{self.system_prompt}\n\nTranscribed from STT:\n{text}"
        return self._correct_with_anthropic_context(system_prompt)

    def _correct_with_openai_compatible(self, text: str) -> Dict[str, Any]:
        """Legacy method - use _correct_with_openai_compatible_context instead."""
        system_prompt = f"{self.system_prompt}\n\nTranscribed from STT:\n{text}"
        return self._correct_with_openai_compatible_context(system_prompt)

    def complete(self, messages: list) -> Optional[str]:
        """
        Complete a conversation with the LLM using a list of messages.

        This method is used for question mode where we need direct conversation
        rather than text correction.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys

        Returns:
            The LLM's response as a string, or None if failed
        """
        if not self.is_available():
            if self.skip_if_unavailable:
                logger.warning(f"⚠️ LLM service not available ({self.provider}), cannot complete conversation")
                return None
            else:
                raise LLMServiceException("LLM service not available")

        # Log the request
        total_content_length = sum(len(msg.get('content', '')) for msg in messages)
        LogHelper.llm_request(self.provider, self.model, self.base_url, total_content_length)

        # Log all messages being sent to the LLM
        logger.info(f"🔄 LLM Request Messages ({len(messages)} messages):")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            logger.info(f"  [{i+1}] {role.upper()}: {content[:200]}{'...' if len(content) > 200 else ''}")

        try:
            start_time = time.time()

            if self.provider == "anthropic":
                response = self._complete_with_anthropic(messages)
            else:
                response = self._complete_with_openai_compatible(messages)

            duration = time.time() - start_time
            logger.info(f"🤖 LLM Response: {response[:200]}{'...' if len(response) > 200 else ''}")
            LogHelper.llm_response(response, duration, {})

            return response

        except Exception as e:
            LogHelper.llm_error(self.provider, str(e))
            if self.skip_if_unavailable:
                logger.warning(f"⚠️ Conversation completion failed, skip_if_unavailable=True")
                return None
            else:
                raise LLMServiceException(f"Error completing conversation: {e}")

    def _complete_with_anthropic(self, messages: list) -> str:
        """Complete conversation using Anthropic's Claude API."""
        try:
            # Separate system message from conversation messages
            system_content = ""
            conversation_messages = []

            for msg in messages:
                if msg.get('role') == 'system':
                    system_content = msg.get('content', '')
                else:
                    conversation_messages.append(msg)

            response = self.anthropic_client.messages.create(
                model=self.model,
                system=system_content,
                messages=conversation_messages,
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Anthropic conversation completion error: {e}")
            raise

    def _complete_with_openai_compatible(self, messages: list) -> str:
        """Complete conversation using OpenAI-compatible API."""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI-compatible conversation completion error: {e}")
            raise

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to the LLM service.

        Returns:
            Dictionary with test results
        """
        test_text = "Hello, this is a test."

        try:
            result = self.correct_text(test_text)
            return {
                "success": True,
                "provider": self.provider,
                "model": self.model,
                "test_input": test_text,
                "test_output": result.get("corrected_text", ""),
                "usage": result.get("usage", {}),
            }
        except Exception as e:
            return {
                "success": False,
                "provider": self.provider,
                "model": self.model,
                "error": str(e),
            }


def create_llm_service(config: Any) -> LLMService:
    """Create an LLM service instance from configuration."""
    return LLMService(config)


# CLI for testing
if __name__ == "__main__":
    import argparse

    def main():
        parser = argparse.ArgumentParser(description="Test LLM Service")
        parser.add_argument(
            "--provider",
            choices=["openai-compatible", "openai", "anthropic"],
            default="openai-compatible",
            help="LLM provider",
        )
        parser.add_argument("--model", default="gpt-4o", help="Model name")
        parser.add_argument("--api-key", help="API key")
        parser.add_argument(
            "--base-url",
            default="http://localhost:1234/v1",
            help="Base URL for OpenAI-compatible APIs",
        )
        parser.add_argument(
            "--text", default="hello wrold, this is a tets", help="Text to correct"
        )

        args = parser.parse_args()

        # Configure logging
        import logging

        logging.basicConfig(level=logging.INFO)

        # Create config
        config = {
            "provider": args.provider,
            "model": args.model,
            "api_key": args.api_key or "",
            "base_url": args.base_url,
            "system_prompt": "Correct any spelling or grammar errors in the following text:",
            "skip_if_unavailable": False,
        }

        # Test the service
        service = LLMService(config)

        print(f"Testing {args.provider} with model {args.model}")
        print(f"Base URL: {args.base_url}")
        print(f"Original text: {args.text}")

        # Test connection
        test_result = service.test_connection()
        if test_result["success"]:
            print("✓ Connection test successful")
        else:
            print(
                f"✗ Connection test failed: {test_result.get('error', 'Unknown error')}"
            )
            return

        # Correct text
        result = service.correct_text(args.text)
        print(f"Corrected text: {result['corrected_text']}")

        usage = result.get("usage", {})
        if usage:
            print(f"Token usage: {usage}")

    main()
