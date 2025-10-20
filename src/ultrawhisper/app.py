#!/usr/bin/env python3
"""
Main application module for UltraWhisper.
"""

import os
import json
import argparse
from typing import Dict, Any, Optional
import yaml  # Add YAML import
from loguru import logger

# Import components
from ultrawhisper.audio.recorder import AudioRecorder
from ultrawhisper.transcription.whisper_transcriber import Transcriber
from ultrawhisper.llm.text_corrector import TextCorrector
from ultrawhisper.ui.hotkey_manager import HotkeyManager
from ultrawhisper.ui.text_outputter import TextOutputter
from ultrawhisper.ui.notifications import NotificationManager
from ultrawhisper.context import ContextDetector
from ultrawhisper.logging_config import LogHelper
from ultrawhisper.modes.mode import Mode
from ultrawhisper.modes.mode_manager import ModeManager
from ultrawhisper.modes.mode_logger import ModeLogger
from ultrawhisper.tts.tts_service import TTSService
from ultrawhisper.tts.system_tts import SystemTTSProvider

# Default configuration
DEFAULT_CONFIG = {
    "hotkey": {"key": "cmd", "modifier": "Key.cmd"},
    "use_double_tap": True,
    "push_to_talk": {"enabled": False, "key": "space"},
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "dtype": "float32",
    },
    "whisper": {
        "model_name": "tiny",
        "language": "en",
    },
    "llm": {
        "provider": "ollama",
        "model": "phi4:latest",
        "api_url": "http://localhost:11434",
        "system_prompt": "You are a helpful assistant that corrects transcription errors. Fix any grammar, punctuation, or spelling mistakes in the following text while preserving the original meaning.",
        "skip_if_unavailable": True,
    },
    "output": {
        "typing_delay": 0.01,
        "paste_mode": False,
    },
    "notifications": {"audio_enabled": True, "visual_enabled": True},
    "modes": {
        "default": "transcription",
        "question": {
            "context_prompts": {
                "default": "You are a helpful AI assistant. Provide concise, accurate answers to user questions."
            },
            "output_response": True,
            "tts_enabled": False,
            "conversation_history": 30,
        }
    },
    "tts": {
        "provider": "system",
        "system": {
            "voice": None,
            "rate": 200,
            "volume": 1.0,
        }
    },
}


class TranscriptionApp:
    """Main application class that coordinates all components."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the transcription application.

        Args:
            config: Application configuration dictionary
        """
        self.config = config or DEFAULT_CONFIG
        self.recording = False

        # Initialize components
        self.recorder = AudioRecorder(self.config.audio.model_dump())
        self.transcriber = Transcriber(self.config.whisper.model_dump())

        # Initialize notification manager
        notification_config = self.config.notifications.model_dump() if self.config.notifications else {}
        self.notification_manager = NotificationManager(notification_config)

        # Check if the selected LLM provider is available
        self.skip_llm = self.config.llm.skip_if_unavailable if self.config.llm else False

        # Initialize the text corrector if available
        logger.info("🔧 Initializing LLM text correction...")
        try:
            # Pass the full config so TextCorrector can access context_prompts and logging settings
            self.corrector = TextCorrector(self.config)

            # Test if the LLM is actually reachable
            logger.info("🔧 Testing LLM connectivity...")
            self.llm_available = self.corrector.llm_service.check_availability()

            if not self.llm_available and self.skip_llm:
                logger.warning(
                    f"🔧 LLM provider {self.config['llm']['provider']} is not reachable. Text correction will be skipped (skip_if_unavailable=True)."
                )
                logger.warning(f"🔧 Expected URL: {self.config['llm']['base_url']}")
                logger.warning(f"🔧 Expected model: {self.config['llm']['model']}")
                self.corrector = None
            elif not self.llm_available:
                logger.error(
                    f"🔧 LLM provider {self.config['llm']['provider']} is not reachable and skip_if_unavailable=False"
                )
                self.corrector = None
            else:
                logger.info(
                    f"🔧 LLM correction enabled: {self.config['llm']['provider']} ({self.config['llm']['model']})"
                )

        except Exception as e:
            logger.error(f"🔧 Error initializing text corrector: {e}")
            self.llm_available = False
            self.corrector = None

        self.outputter = TextOutputter(self.config.output.model_dump())

        # Initialize context detector
        self.context_detector = ContextDetector(self.config)

        # Initialize mode system
        logger.info("🔄 Initializing mode system...")
        self.mode_manager = ModeManager(self.config)
        self.mode_logger = ModeLogger(config_manager=getattr(self, 'config_manager', None))

        # Set up mode change callback to log mode switches
        self.mode_manager.set_mode_change_callback(self._on_mode_change)

        logger.info(f"🔄 Mode system initialized - current mode: {self.mode_manager.get_current_mode()}")

        # Initialize TTS service
        logger.info("🔊 Initializing TTS service...")
        self.tts_service = TTSService(self.config.tts.model_dump() if self.config.tts else {})

        # Register available TTS providers
        system_tts = SystemTTSProvider(self.config.tts.system.model_dump() if self.config.tts and self.config.tts.system else {})
        if system_tts.is_available():
            self.tts_service.register_provider(system_tts)

        # Set default provider
        tts_provider = self.config.tts.provider if self.config.tts else "system"
        if self.tts_service.get_available_providers():
            self.tts_service.set_provider(tts_provider)
            logger.info(f"🔊 TTS service ready - provider: {tts_provider}")
        else:
            logger.warning("🔊 No TTS providers available")

        # Get push-to-talk configuration
        push_to_talk_config = (self.config.push_to_talk.model_dump()
                              if self.config.push_to_talk
                              else {"enabled": False, "key": "space"})

        # Pass use_double_tap at the correct level
        hotkey_config = self.config.hotkey.model_dump()
        hotkey_config["use_double_tap"] = self.config.use_double_tap

        self.hotkey_manager = HotkeyManager(
            hotkey_config, self.toggle_recording, push_to_talk_config
        )

    def _on_mode_change(self, old_mode: Mode, new_mode: Mode) -> None:
        """Handle mode change events."""
        try:
            # Get current context for logging
            context = None
            if self.context_detector:
                try:
                    context = self.context_detector.get_active_context()
                except Exception:
                    pass

            # Log the mode switch
            self.mode_logger.log_mode_switch(old_mode, new_mode, context)
            logger.info(f"🔄 Mode changed: {old_mode.value} → {new_mode.value}")
        except Exception as e:
            logger.error(f"Error handling mode change: {e}")

    def _process_transcription_mode(self, text: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Process text in transcription mode (existing behavior)."""
        try:
            original_text = text

            # Correct the text if LLM is available
            if self.corrector and self.llm_available:
                logger.info("🔧 Attempting LLM text correction...")
                text = self.corrector.correct(text, context=context)
            else:
                if not self.corrector:
                    LogHelper.service_status("LLM correction", "disabled", "no corrector")
                elif not self.llm_available:
                    LogHelper.service_status(
                        "LLM correction", "skipped", "service unavailable"
                    )

            # Log the transcription
            self.mode_logger.log_transcription(original_text, text if text != original_text else None, context)

            # Output the text
            output_mode = (
                "paste" if self.config.output.paste_mode else "type"
            )
            LogHelper.text_output(text, output_mode)
            self.outputter.output_text(text)

        except Exception as e:
            logger.error(f"Error processing transcription mode: {e}")

    def _process_question_mode(self, text: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Process text in question mode."""
        try:
            logger.info(f"🤔 Processing question: {text}")

            if not self.corrector or not self.llm_available:
                logger.warning("🤔 Question mode requires LLM, but LLM is not available")
                # Fall back to just logging the question
                self.mode_logger.log_question_answer(text, "LLM not available", context)
                return

            # Get question mode configuration
            question_config = self.mode_manager.get_mode_config(Mode.QUESTION)

            # Get context-aware prompt for question mode
            app_name = context.get('app', 'default') if context else 'default'
            context_prompts = question_config.get('context_prompts', {})
            system_prompt = context_prompts.get(app_name) or context_prompts.get('default',
                'You are a helpful AI assistant. Provide concise, accurate answers to user questions.')

            # For Phase 1, use the LLM service directly (conversation history in Phase 3)
            # Create a simple question/answer exchange
            logger.info("🧠 Generating response...")

            # Add user question to conversation history
            try:
                self.mode_manager.add_user_message(text, context)
            except Exception as e:
                logger.error(f"Failed to add user message to conversation history: {e}")

            # Use the corrector's LLM service with question mode prompt and conversation history
            response = self._get_llm_response(text, system_prompt, context)

            if response:
                # Add assistant response to conversation history
                try:
                    self.mode_manager.add_assistant_message(response, context)
                except Exception as e:
                    logger.error(f"Failed to add assistant message to conversation history: {e}")

                # Log the question and answer
                self.mode_logger.log_question_answer(text, response, context)

                # Play TTS if enabled
                tts_enabled = question_config.get('tts_enabled', False)
                if tts_enabled and self.tts_service and self.tts_service.is_available():
                    logger.info("🔊 Playing TTS response...")
                    try:
                        tts_success = self.tts_service.speak(response, async_playback=True)
                        if not tts_success:
                            logger.warning("🔊 TTS playback failed, continuing without audio")
                    except Exception as e:
                        logger.error(f"🔊 TTS error: {e}, continuing without audio")
                elif tts_enabled:
                    logger.debug("🔊 TTS requested but not available")

                # Output response text if configured
                output_response = question_config.get('output_response', True)
                if output_response:
                    output_mode = (
                        "paste" if self.config.output.paste_mode else "type"
                    )
                    LogHelper.text_output(response, output_mode)
                    self.outputter.output_text(response)
                else:
                    logger.info(f"🤔 Response (not output): {response}")
            else:
                logger.warning("🤔 Failed to get response from LLM")
                self.mode_logger.log_question_answer(text, "Failed to get response", context)

        except Exception as e:
            logger.error(f"Error processing question mode: {e}")
            self.mode_logger.log_question_answer(text, f"Error: {e}", context)

    def _get_llm_response(self, question: str, system_prompt: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get response from LLM for question mode with conversation history."""
        try:
            # Use the existing LLM service but with custom prompt
            if not self.corrector or not self.corrector.llm_service:
                return None

            # Start with system prompt
            messages = [{"role": "system", "content": system_prompt}]

            # Add conversation history if available
            conversation_history = self.mode_manager.get_conversation_context()
            if conversation_history:
                # Add all previous messages except the current question (which isn't in history yet)
                messages.extend(conversation_history)
                logger.debug(f"🗨️ Including {len(conversation_history)} messages from conversation history")

            # Add the current question
            messages.append({"role": "user", "content": question})

            # Use the LLM service to get response
            response = self.corrector.llm_service.complete(messages)
            return response

        except Exception as e:
            logger.error(f"Error getting LLM response: {e}")
            return None

    def run(self):
        """Run the application."""
        logger.info("Starting UltraWhisper application")

        # Start the hotkey listener
        self.hotkey_manager.start()

        # Print instructions
        self._print_instructions()

        try:
            # Keep the application running
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        finally:
            # Clean up
            self.hotkey_manager.stop()
            logger.info("UltraWhisper application stopped")

    def toggle_recording(self):
        """Toggle recording state."""
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording audio."""
        LogHelper.recording_start()
        self.recording = True
        self.recorder.start_recording()

        # Notify that recording has started
        self.notification_manager.notify_recording_start()

    def _stop_recording(self):
        """Stop recording and process the audio."""
        self.recording = False

        # Notify that recording has stopped
        self.notification_manager.notify_recording_stop()

        # Stop recording and get the audio file path
        audio_path = self.recorder.stop_recording()

        if not audio_path:
            logger.warning("⚠️ No audio recorded")
            return

        # Record duration for logging
        duration = getattr(self.recorder, "last_duration", 0.0)
        LogHelper.recording_stop(duration)

        # Transcribe the audio
        import time

        transcribe_start = time.time()
        text = self.transcriber.transcribe(audio_path)
        transcribe_duration = time.time() - transcribe_start

        if not text:
            logger.warning("⚠️ No text transcribed")
            return

        LogHelper.transcription_result(text, transcribe_duration)

        # Check for mode switching commands first (before any other processing)
        detected_mode, should_consume = self.mode_manager.process_transcription(text)
        if should_consume:
            # Mode switch command detected - provide feedback
            if detected_mode:
                mode_name = detected_mode.value.title()
                logger.info(f"🔄 Switched to {mode_name} Mode")

                # Play notification if available
                if self.notification_manager:
                    try:
                        # Use audio notification for mode switches
                        self.notification_manager.notify_recording_start()  # Repurpose for mode switch
                    except Exception:
                        pass

            logger.info(f"🔄 Mode switch command processed, skipping text output")
            return

        # Get current application context for LLM prompt customization
        context = None
        log_context = self.config.logging.log_context if self.config.logging else False

        if self.config.context_detection:
            try:
                context = self.context_detector.get_active_context(
                    log_context=log_context
                )
                if context:
                    LogHelper.context_detected(
                        context.get("app", "unknown"),
                        context.get("title", ""),
                        context.get("method", "unknown"),
                    )
            except Exception as e:
                logger.debug(f"Context detection failed: {e}")
                context = None

        # Process according to current mode
        current_mode = self.mode_manager.get_current_mode()

        if current_mode == Mode.TRANSCRIPTION:
            # Transcription mode: correct text and output
            self._process_transcription_mode(text, context)
        elif current_mode == Mode.QUESTION:
            # Question mode: send to LLM as question
            self._process_question_mode(text, context)
        else:
            logger.warning(f"Unknown mode: {current_mode}, falling back to transcription")
            self._process_transcription_mode(text, context)

        # Clean up the temporary audio file
        try:
            os.remove(audio_path)
            logger.debug(f"Removed temporary audio file: {audio_path}")
        except Exception as e:
            logger.error(f"Error removing temporary audio file: {e}")

    def _print_instructions(self):
        """Print usage instructions."""
        modifier = self.config.hotkey.modifier
        key = self.config.hotkey.key
        use_double_tap = self.config.use_double_tap
        push_to_talk_config = (self.config.push_to_talk.model_dump()
                              if self.config.push_to_talk
                              else {"enabled": False, "key": "space"})
        push_to_talk_enabled = push_to_talk_config.get("enabled", False)
        push_to_talk_key = push_to_talk_config.get("key", "space")

        print("\n" + "=" * 60)
        print("UltraWhisper - Voice Transcription")
        print("=" * 60)

        if push_to_talk_enabled:
            print(f"Push-to-talk mode enabled: Hold '{push_to_talk_key}' key to record")
        elif use_double_tap:
            print(f"Double-tap {modifier} to start/stop recording")
        else:
            print(f"Press {modifier}+{key} to start/stop recording")

        print("\nWhisper model: " + self.config.whisper.model_name)

        if self.corrector and self.llm_available:
            print(f"LLM provider: {self.config['llm']['provider']}")
            print(f"LLM model: {self.config['llm']['model']}")
        else:
            print("LLM correction: Disabled")

        # Print notification status
        notifications = self.config.notifications
        audio_enabled = notifications.audio_enabled if notifications else True
        visual_enabled = notifications.visual_enabled if notifications else True

        print("\nNotifications:")
        print(f"  Audio feedback: {'Enabled' if audio_enabled else 'Disabled'}")
        print(f"  Visual notifications: {'Enabled' if visual_enabled else 'Disabled'}")

        print("\nPress Ctrl+C to exit")
        print("=" * 60 + "\n")


def load_config(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Load configuration from file and command line arguments.

    Args:
        args: Command line arguments

    Returns:
        Configuration dictionary
    """
    # Start with default configuration
    config = DEFAULT_CONFIG.copy()

    # Load configuration from file if specified
    if args.config:
        config_path = args.config
        # Check if the file exists, if not try with .yml or .json extension
        if not os.path.exists(config_path):
            if os.path.exists(f"{config_path}.yml"):
                config_path = f"{config_path}.yml"
            elif os.path.exists(f"{config_path}.yaml"):
                config_path = f"{config_path}.yaml"
            elif os.path.exists(f"{config_path}.json"):
                config_path = f"{config_path}.json"

        try:
            file_config = {}
            with open(config_path, "r") as f:
                # Determine file type by extension
                if config_path.lower().endswith((".yml", ".yaml")):
                    file_config = yaml.safe_load(f)
                    logger.info(f"Loaded YAML configuration from {config_path}")
                else:  # Default to JSON
                    file_config = json.load(f)
                    logger.info(f"Loaded JSON configuration from {config_path}")

                # Update config with file values
                if file_config:
                    config.update(file_config)
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")

    # Override with command line arguments
    if args.model:
        config["whisper"]["model_name"] = args.model

    if args.language:
        config["whisper"]["language"] = args.language

    if args.llm_provider:
        config["llm"]["provider"] = args.llm_provider

    if args.llm_model:
        config["llm"]["model"] = args.llm_model

    if args.llm_api_url:
        config["llm"]["api_url"] = args.llm_api_url

    if args.llm_api_key:
        config["llm"]["api_key"] = args.llm_api_key

    if args.modifier:
        config["hotkey"]["modifier"] = args.modifier

    if args.key:
        config["hotkey"]["key"] = args.key

    if args.no_double_tap:
        config["use_double_tap"] = False

    # Handle push-to-talk options
    if args.push_to_talk:
        if not "push_to_talk" in config:
            config["push_to_talk"] = {}
        config["push_to_talk"]["enabled"] = True

    if args.push_to_talk_key:
        if not "push_to_talk" in config:
            config["push_to_talk"] = {}
        config["push_to_talk"]["key"] = args.push_to_talk_key

    # Handle output options
    if args.typing_delay is not None:
        config["output"]["typing_delay"] = args.typing_delay

    if args.paste_mode:
        config["output"]["paste_mode"] = True

    # Handle LLM options
    if args.skip_llm:
        config["llm"]["skip_if_unavailable"] = True

    # Handle notification options
    if not "notifications" in config:
        config["notifications"] = {}

    if args.disable_audio_notifications:
        config["notifications"]["audio_enabled"] = False

    if args.disable_visual_notifications:
        config["notifications"]["visual_enabled"] = False

    return config


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="UltraWhisper - Voice Transcription Application"
    )

    # Configuration file
    parser.add_argument("--config", type=str, help="Path to configuration file")

    # Whisper options
    parser.add_argument(
        "--model",
        type=str,
        help="Whisper model name (tiny, base, small, medium, large)",
    )
    parser.add_argument("--language", type=str, help="Language code for transcription")

    # LLM options
    parser.add_argument(
        "--llm-provider", type=str, help="LLM provider (ollama, openai, anthropic)"
    )
    parser.add_argument("--llm-model", type=str, help="LLM model name")
    parser.add_argument("--llm-api-url", type=str, help="LLM API URL (for Ollama)")
    parser.add_argument("--llm-api-key", type=str, help="LLM API key")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM correction if provider is unavailable",
    )

    # Hotkey options
    parser.add_argument(
        "--modifier", type=str, help="Modifier key for hotkey (e.g., Key.ctrl, Key.alt)"
    )
    parser.add_argument("--key", type=str, help="Key for hotkey combination")
    parser.add_argument(
        "--no-double-tap", action="store_true", help="Disable double-tap activation"
    )

    # Push-to-talk options
    parser.add_argument(
        "--push-to-talk", action="store_true", help="Enable push-to-talk mode"
    )
    parser.add_argument(
        "--push-to-talk-key",
        type=str,
        help="Key to use for push-to-talk (e.g., space, Key.shift)",
    )

    # Output options
    parser.add_argument(
        "--typing-delay", type=float, help="Delay between typing characters"
    )
    parser.add_argument(
        "--paste-mode",
        action="store_true",
        help="Use clipboard paste instead of typing",
    )

    # Notification options
    parser.add_argument(
        "--disable-audio-notifications",
        action="store_true",
        help="Disable audio feedback when recording starts/stops",
    )
    parser.add_argument(
        "--disable-visual-notifications",
        action="store_true",
        help="Disable visual notifications when recording starts/stops",
    )

    # Debug options
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    return parser.parse_args()


def check_hotkey_conflicts(config: Dict[str, Any]):
    """
    Check for potential hotkey conflicts with window managers.

    Args:
        config: Application configuration
    """
    modifier = config["hotkey"]["modifier"]
    key = config["hotkey"]["key"]

    # Convert Key objects to strings for comparison
    modifier_str = str(modifier)

    # Check for common window manager conflicts
    wm_conflicts = {
        "i3": ["Key.alt", "Key.super"],
        "gnome": ["Key.super"],
        "kde": ["Key.alt"],
        "xfce": ["Key.alt"],
    }

    # Try to detect the current window manager
    current_wm = None
    try:
        import os

        if "XDG_CURRENT_DESKTOP" in os.environ:
            desktop = os.environ["XDG_CURRENT_DESKTOP"].lower()
            if "gnome" in desktop:
                current_wm = "gnome"
            elif "kde" in desktop:
                current_wm = "kde"
            elif "xfce" in desktop:
                current_wm = "xfce"

        # Check for i3 specifically
        try:
            import subprocess

            result = subprocess.run(["pgrep", "i3"], capture_output=True, text=True)
            if result.returncode == 0:
                current_wm = "i3"
        except:
            pass
    except:
        pass

    # Check for conflicts with the detected window manager
    if current_wm and current_wm in wm_conflicts:
        if modifier_str in wm_conflicts[current_wm]:
            logger.warning(
                f"⚠️ Potential hotkey conflict detected: {modifier_str}+{key} may be intercepted by {current_wm}."
            )
            logger.warning(
                f"⚠️ If the hotkey doesn't work, try using a different modifier key with --modifier."
            )
            logger.warning(
                f"⚠️ Suggested alternatives: --modifier ctrl or --modifier shift"
            )

    # General warning for common modifiers
    if modifier_str in ["Key.super", "Key.alt"] and not current_wm:
        logger.warning(
            f"Note: {modifier_str}+{key} might conflict with your window manager."
        )
        logger.warning(
            "If the hotkey doesn't work, try using --modifier ctrl or --modifier shift"
        )
