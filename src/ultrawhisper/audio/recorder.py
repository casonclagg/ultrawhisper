import os
import time
import tempfile
import logging
import threading
from typing import Dict, Any, Optional, Callable

import numpy as np
import sounddevice as sd
import wavio

# Configure logging
logger = logging.getLogger("ultrawhisper.audio")


class AudioRecorder:
    """Records audio from the microphone."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the audio recorder.

        Args:
            config: Audio configuration dictionary
        """
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.dtype = config.get("dtype", "float32")

        self.recording = False
        self.frames = []
        self.record_thread = None

        logger.info(
            f"Initialized AudioRecorder with sample_rate={self.sample_rate}, channels={self.channels}"
        )

    def start_recording(self):
        """Start recording audio from the microphone."""
        if self.recording:
            logger.warning("Recording is already in progress")
            return

        self.recording = True
        self.frames = []

        # Start recording in a separate thread
        self.record_thread = threading.Thread(target=self._record)
        self.record_thread.daemon = True
        self.record_thread.start()

        logger.info("Started recording audio")

    def stop_recording(self) -> Optional[str]:
        """
        Stop recording audio and save to a temporary file.

        Returns:
            Path to the saved audio file, or None if no audio was recorded
        """
        if not self.recording:
            logger.warning("No recording in progress")
            return None

        self.recording = False

        # Wait for the recording thread to finish
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=1.0)

        # Check if any audio was recorded
        if not self.frames:
            # logger.warning("No audio was recorded")
            return None

        # Convert frames to numpy array
        audio_data = np.concatenate(self.frames, axis=0)

        # Create a temporary file to save the audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name

        # Save audio to the temporary file
        wavio.write(temp_path, audio_data, self.sample_rate, sampwidth=2)

        logger.info(
            f"Saved {len(audio_data) / self.sample_rate:.2f} seconds of audio to {temp_path}"
        )

        return temp_path

    def _record(self):
        """Record audio from the microphone in a loop."""
        try:
            # Open the audio stream
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback,
            ):
                # Record until stopped
                while self.recording:
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            self.recording = False

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback function for the audio stream."""
        if status:
            logger.warning(f"Audio stream status: {status}")

        # Add the audio data to the frames list
        if self.recording:
            self.frames.append(indata.copy())
