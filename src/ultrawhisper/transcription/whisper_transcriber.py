#!/usr/bin/env python3
"""
Whisper transcription functionality for UltraWhisper.
"""

import os
import logging
from typing import Dict, Any, Optional

from faster_whisper import WhisperModel

# Configure logging
logger = logging.getLogger("ultrawhisper.transcription")


class Transcriber:
    """Transcribes audio using faster-whisper model."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the transcriber.

        Args:
            config: Whisper configuration dictionary
        """
        self.model_name = config.get("model_name", "tiny")
        self.language = config.get("language", "en")
        self.model = None

        logger.info(
            f"Initializing faster-whisper transcriber with model={self.model_name}, language={self.language}"
        )

    def load_model(self):
        """Load the faster-whisper model."""
        if self.model is None:
            logger.info(f"Loading faster-whisper model: {self.model_name}")
            try:
                self.model = WhisperModel(
                    self.model_name, device="cpu", compute_type="int8"
                )
                logger.info(
                    f"Faster-whisper model {self.model_name} loaded successfully"
                )
            except Exception as e:
                logger.error(f"Error loading faster-whisper model: {e}")
                raise

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio using faster-whisper.

        Args:
            audio_path: Path to the audio file

        Returns:
            Transcribed text
        """
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return ""

        # Load the model if not already loaded
        if self.model is None:
            self.load_model()

        logger.info(f"Transcribing audio file: {audio_path}")

        try:
            # Transcribe the audio with faster-whisper
            segments, info = self.model.transcribe(
                audio_path, language=self.language if self.language != "auto" else None
            )

            # Extract the transcribed text from segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text)

            text = " ".join(text_parts).strip()

            logger.info(f"Transcription result: {text}")

            return text
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return ""
