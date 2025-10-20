import os
from typing import Dict, Any
from loguru import logger

# Import the LLM service
from ultrawhisper.llm.llm_service import LLMService, LLMServiceException

class TextCorrector:
    """Handles text correction using the LLM service."""

    def __init__(self, config: Any):
        """
        Initialize the text corrector.

        Args:
            config: Full application configuration (UltraWhisperConfig Pydantic model)
        """
        # Store full config for prompt construction
        self.config = config

        # Access Pydantic model attributes directly
        self.system_prompt = config.llm.base_prompt

        # Initialize the LLM service with full config
        self.llm_service = LLMService(config)

        logger.info(f"📝 TextCorrector initialized")
        logger.info(
            f"System prompt: {self.system_prompt[:100]}{'...' if len(self.system_prompt) > 100 else ''}"
        )

    def correct(self, text: str, context: Dict[str, Any] = None) -> str:
        """
        Correct the transcribed text using the LLM service with context awareness.

        Args:
            text: Text to correct
            context: Optional application context for prompt customization

        Returns:
            Corrected text
        """
        if not text:
            logger.debug("📝 Empty text provided, skipping correction")
            return ""

        logger.info(f"📝 Text correction requested:")
        logger.info(f'  Text: "{text}"')
        logger.info(f"  Length: {len(text)} characters")

        # Check if LLM service is available before attempting correction
        if not self.llm_service.is_available():
            logger.warning(f"📝 LLM service not available, returning original text")
            return text

        try:
            # Correct text using the LLM service with context
            response = self.llm_service.correct_text(text, context=context)

            # Extract the corrected text
            corrected_text = response.get("corrected_text", "").strip()

            if corrected_text:
                if corrected_text != text:
                    logger.info(f'📝 Text was corrected: "{text}" → "{corrected_text}"')
                else:
                    logger.info(f"📝 Text returned unchanged")
                return corrected_text
            else:
                logger.warning(f"📝 Empty response from {self.llm_service.provider}")
                return text

        except LLMServiceException as e:
            logger.error(
                f"📝 Text correction error with {self.llm_service.provider}: {e}"
            )
            # Return the original text if correction fails
            return text
        except Exception as e:
            logger.error(f"📝 Unexpected error during text correction: {e}")
            return text
