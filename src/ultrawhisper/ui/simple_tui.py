#!/usr/bin/env python3
"""
Simplified Terminal User Interface for UltraWhisper using prompt-toolkit.

This is a minimal, stable version that focuses on displaying status and logs
without complex async dialogs that can cause crashes.
"""

import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from ultrawhisper.config.config import ConfigManager
from loguru import logger
from ultrawhisper.llm.llm_service import LLMService
from ultrawhisper.context import ContextDetector
from ultrawhisper.audio.recorder import AudioRecorder
from ultrawhisper.transcription.whisper_transcriber import Transcriber
from ultrawhisper.llm.text_corrector import TextCorrector
from ultrawhisper.ui.hotkey_manager import HotkeyManager
from ultrawhisper.ui.notifications import NotificationManager
from ultrawhisper.ui.ascii_art import get_ultrawhisper_ascii_art, get_ascii_height
from ultrawhisper.logging_config import LogHelper
from ultrawhisper.modes.mode import Mode
from ultrawhisper.modes.mode_manager import ModeManager
from ultrawhisper.modes.mode_logger import ModeLogger
from ultrawhisper.text_utils import strip_urls_for_speech


class SimpleUltraWhisperTUI:
    """Simplified TUI application for UltraWhisper."""

    def __init__(self, show_prompts: bool = False):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        self.show_prompts = show_prompts

        # ASCII art header
        self.messages: List[str] = []
        self.application = None
        self.recording = False

        # Cache connection status to avoid repeated checks
        self.llm_connected = False

        # View state management
        self.current_view = 'main'  # 'main' or 'settings'
        self.settings_component = None

        # Text areas for scrollable content (will be created in layout)
        self.status_textarea = None
        self.chat_textarea = None
        self.log_textarea = None

        # Animation state for pulse dots - single moving dot
        self.animation_frame = 0
        self.pulse_patterns = [
            "● ○ ○ ○ ○ ○ ○ ○",
            "○ ● ○ ○ ○ ○ ○ ○",
            "○ ○ ● ○ ○ ○ ○ ○",
            "○ ○ ○ ● ○ ○ ○ ○",
            "○ ○ ○ ○ ● ○ ○ ○",
            "○ ○ ○ ○ ○ ● ○ ○",
            "○ ○ ○ ○ ○ ○ ● ○",
            "○ ○ ○ ○ ○ ○ ○ ●",
        ]

        # Animation state for thinking indicator
        self.thinking_indicator_active = False
        self.thinking_animation_frame = 0
        self.thinking_spinner_patterns = [
            "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
        ]

        # Set up file logging instead of disabling logs
        from pathlib import Path
        from datetime import datetime

        # Get log directory (logs subfolder in config directory)
        config_dir = Path(self.config_manager.get_config_path()).parent
        log_dir = config_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        log_file = log_dir / f"ultrawhisper-tui-{timestamp}.log"

        # Configure loguru to write to file only
        logger.remove()  # Remove default handler
        logger.add(
            log_file,
            rotation="100 MB",
            retention="7 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        )
        logger.info(f"TUI session started - Log file: {log_file}")
        self.log_file_path = str(log_file)

        # Initialize all application components
        self.recorder = None
        self.transcriber = None
        self.corrector = None
        self.llm_service = None
        self.context_detector = None
        self.hotkey_manager = None
        self.notification_manager = None

        self._init_services()

        # Add log file info to startup
        self.add_message(
            f"■ Session log: {Path(self.log_file_path).name}", style="log.info"
        )


    def _init_services(self):
        """Initialize all application services."""

        # Initialize audio recorder
        try:
            # AudioRecorder will need to be updated to accept full config and use config.audio internally
            # For now, pass the dict until we update AudioRecorder
            audio_config = self.config.audio.model_dump() if hasattr(self.config.audio, 'model_dump') else self.config.audio
            self.recorder = AudioRecorder(audio_config)
        except Exception as e:
            pass

        # Initialize transcriber
        try:
            # Transcriber will need to be updated to accept full config and use config.whisper internally
            # For now, pass the dict until we update Transcriber
            whisper_config = self.config.whisper.model_dump() if hasattr(self.config.whisper, 'model_dump') else self.config.whisper
            self.transcriber = Transcriber(whisper_config)
        except Exception as e:
            pass

        # Initialize context detector
        try:
            self.context_detector = ContextDetector(self.config)
        except Exception as e:
            pass

        # Initialize notification manager
        try:
            # Pass full config - NotificationManager can access config.notifications internally
            self.notification_manager = NotificationManager(self.config)
        except Exception as e:
            pass

        # Initialize text corrector (with LLM)
        try:
            self.corrector = TextCorrector(self.config)
            self.llm_service = self.corrector.llm_service

            # Test LLM connectivity (once at startup)
            if self.llm_service.check_availability():
                self.llm_connected = True
            else:
                self.llm_connected = False
        except Exception as e:
            pass

        # Initialize agent service for OpenAI question mode
        self.agent_service = None
        try:
            from ultrawhisper.llm.agent_service import create_agent_service

            # Use typed config
            llm_provider = self.config.llm.provider

            if llm_provider == "openai":
                self.agent_service = create_agent_service(self.config)
                if self.agent_service.is_available():
                    self.agent_service.create_new_session()
                    logger.info("🤖 Agent service initialized and session created")
                else:
                    logger.info("🤖 Agent service not available")
            else:
                logger.info(f"🤖 Agent service disabled (provider: {llm_provider})")
        except Exception as e:
            logger.error(f"🤖 Failed to initialize agent service: {e}")
            self.agent_service = None

        # Initialize hotkey manager for transcription mode
        try:
            # HotkeyManager needs full config or we need to update it to accept typed config
            # For now, pass the dict sections until we update HotkeyManager
            push_to_talk_config = self.config.push_to_talk.model_dump() if hasattr(self.config.push_to_talk, 'model_dump') else self.config.push_to_talk

            hotkey_config = self.config.hotkey.model_dump() if hasattr(self.config.hotkey, 'model_dump') else self.config.hotkey
            if isinstance(hotkey_config, dict):
                hotkey_config = hotkey_config.copy()
            else:
                hotkey_config = hotkey_config.model_copy()
            hotkey_config["use_double_tap"] = self.config.use_double_tap

            self.hotkey_manager = HotkeyManager(
                hotkey_config, self.toggle_recording, push_to_talk_config
            )
        except Exception as e:
            pass

        # Initialize question mode hotkey manager
        try:
            question_push_to_talk_config = self.config.question_mode_push_to_talk.model_dump() if hasattr(self.config.question_mode_push_to_talk, 'model_dump') else self.config.question_mode_push_to_talk

            if question_push_to_talk_config.get('enabled', False):
                self.question_hotkey_manager = HotkeyManager(
                    {}, self.toggle_question_recording, question_push_to_talk_config
                )
            else:
                self.question_hotkey_manager = None
        except Exception as e:
            self.question_hotkey_manager = None

        # Initialize mode system
        try:
            self.mode_manager = ModeManager(self.config)
            self.mode_logger = ModeLogger(config_manager=self.config_manager)
        except Exception as e:
            # Fallback to default mode if initialization fails
            self.mode_manager = None
            self.mode_logger = None

        # Initialize TTS service
        try:
            from ultrawhisper.tts.tts_service import TTSService
            from ultrawhisper.tts.system_tts import SystemTTSProvider

            logger.info("🔊 Initializing TTS service...")
            self.tts_service = TTSService(self.config)

            # Get TTS provider from typed config
            provider_name = self.config.tts.provider
            system_config = self.config.tts.system.model_dump() if hasattr(self.config.tts.system, 'model_dump') else self.config.tts.system

            if provider_name == "system":
                # Initialize system TTS provider
                system_provider = SystemTTSProvider(system_config)

                if self.tts_service.register_provider(system_provider):
                    self.tts_service.set_provider("system")
                    logger.info(f"🔊 TTS service initialized successfully with system provider")
                else:
                    logger.warning("🔊 System TTS provider not available")
                    self.tts_service = None
            else:
                logger.warning(f"🔊 Unsupported TTS provider: {provider_name}")
                self.tts_service = None

        except Exception as e:
            logger.error(f"🔊 Failed to initialize TTS service: {e}")
            self.tts_service = None

    def toggle_recording(self):
        """Toggle recording state for transcription mode (auto-switches to transcription mode)."""
        # Switch to transcription mode if not already there
        if self.mode_manager and self.mode_manager.get_current_mode() != Mode.TRANSCRIPTION:
            self.mode_manager.switch_mode(Mode.TRANSCRIPTION)
            self.add_message("Switched to Transcription mode", style="log.info")
            # Rebuild layout to show logs panel
            if self.application:
                self.application.layout = self.create_layout()
                self.application.invalidate()

        # Now toggle recording
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def toggle_question_recording(self):
        """Toggle recording state for question mode (auto-switches to question mode)."""
        # Switch to question mode if not already there
        if self.mode_manager and self.mode_manager.get_current_mode() != Mode.QUESTION:
            self.mode_manager.switch_mode(Mode.QUESTION)
            self.add_message("Switched to Question mode", style="log.info")
            # Rebuild layout to show chat panel
            if self.application:
                self.application.layout = self.create_layout()
                self.application.invalidate()

        # Now toggle recording
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording audio."""
        if not self.recorder:
            self.add_message("❌ Audio recorder not initialized")
            return

        LogHelper.recording_start()
        self.recording = True
        self.recorder.start_recording()

        # Notify that recording has started
        if self.notification_manager:
            self.notification_manager.notify_recording_start()

    def _stop_recording(self):
        """Stop recording and process the audio."""
        if not self.recorder:
            self.add_message("❌ Audio recorder not initialized")
            return

        self.recording = False

        # Notify that recording has stopped
        if self.notification_manager:
            self.notification_manager.notify_recording_stop()

        try:
            # Stop recording and get the audio file path
            audio_path = self.recorder.stop_recording()

            if not audio_path:
                self.add_message("⚠️ No audio recorded")
                return

            # Record duration for logging
            duration = getattr(self.recorder, "last_duration", 0.0)
            LogHelper.recording_stop(duration)

            # Transcribe the audio
            import time

            transcribe_start = time.time()
            transcription = self.transcriber.transcribe(audio_path)
            transcribe_duration = time.time() - transcribe_start

            if not transcription:
                return

            LogHelper.transcription_result(transcription, transcribe_duration)
            self.add_message(f"► {transcription}", style="log.transcription")

            # Check for mode switching commands first (before any other processing)
            if self.mode_manager:
                detected_mode, should_consume = self.mode_manager.process_transcription(transcription)
                if should_consume:
                    # Mode switch command detected - provide feedback
                    if detected_mode:
                        mode_name = "Chat" if detected_mode.value == "question" else "Transcription"
                        self.add_message(f"🔄 Switched to {mode_name} Mode", style="log.info")
                        # Rebuild layout to show appropriate panel
                        if self.application:
                            self.application.layout = self.create_layout()
                            self.application.invalidate()
                    return

            # Get context for LLM correction
            context = None
            if self.context_detector:
                try:
                    context = self.context_detector.get_active_context()
                    if context and context.get("app"):
                        app_name = context.get("app", "unknown")
                        # Add context emoji mapping
                        context_style = self._get_context_style(app_name)
                        self.add_message(
                            f"  ● {app_name}", style=context_style
                        )
                except Exception:
                    pass

            # Process according to current mode
            if self.mode_manager:
                current_mode = self.mode_manager.get_current_mode()

                if current_mode.value == "transcription":
                    # Transcription mode: correct text and output
                    self._process_transcription_mode(transcription, context)
                elif current_mode.value == "question":
                    # Question mode: send to LLM as question
                    self._process_question_mode(transcription, context)
                else:
                    # Fallback to transcription mode
                    self._process_transcription_mode(transcription, context)
            else:
                # No mode manager - fallback to original behavior
                self._process_transcription_mode(transcription, context)

        except Exception as e:
            self.add_message(f"Error processing recording: {e}")
            import traceback

            self.add_message(f"Full traceback: {traceback.format_exc()}")

    def _output_text(self, text: str):
        """Output text to the system."""
        try:
            from ultrawhisper.ui.text_outputter import TextOutputter

            # TextOutputter needs dict config for now
            output_config = self.config.output.model_dump() if hasattr(self.config.output, 'model_dump') else self.config.output
            outputter = TextOutputter(output_config)

            # Make a clean copy of the text to ensure no interference
            clean_text = str(text)
            outputter.output_text(clean_text)

            # Show the corrected output
            self.add_message(f"◄ {clean_text}", style="log.output")
        except Exception as e:
            self.add_message(f"Failed to output text: {e}")
            import traceback

            self.add_message(f"Output error traceback: {traceback.format_exc()}")

    def add_message(self, message: str, style: str = None) -> None:
        """Add a message to the TUI display with optional styling."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if style:
            # Store as tuple for styled display
            formatted_msg = (style, f"{timestamp} | {message}")
        else:
            # Plain text message
            formatted_msg = f"{timestamp} | {message}"

        self.messages.append(formatted_msg)

        # Keep only last 100 messages
        if len(self.messages) > 100:
            self.messages = self.messages[-100:]

    def clear_logs(self) -> None:
        """Clear all log messages."""
        self.messages.clear()
        self.add_message("Logs cleared", style="log.info")

    def clear_chat_history(self) -> None:
        """Clear conversation history and create new agent session."""
        if self.mode_manager and hasattr(self.mode_manager, 'conversation_history'):
            self.mode_manager.clear_conversation_history()

            # Create new agent session if using OpenAI agents
            if self.agent_service and self.agent_service.is_available():
                self.agent_service.create_new_session()
                self.add_message("Chat history cleared & new agent session created", style="log.info")
            else:
                self.add_message("Chat history cleared", style="log.info")
        else:
            self.add_message("No chat history to clear", style="log.info")

    def _get_context_square(self, app_name: str) -> str:
        """Get colored ASCII square for application context."""
        app_squares = {
            "terminal": "■",  # Solid square - terminal apps
            "code": "■",
            "kitty": "■",
            "alacritty": "■",
            "iterm": "■",
            "gnome-terminal": "■",
            "konsole": "■",
            "firefox": "■",  # Solid square - browsers
            "chrome": "■",
            "chromium": "■",
            "safari": "■",
            "edge": "■",
            "slack": "■",  # Solid square - chat apps
            "discord": "■",
            "telegram": "■",
            "whatsapp": "■",
            "obsidian": "■",  # Solid square - text editors
            "notion": "■",
            "vscode": "■",  # Solid square - code editors
            "vim": "■",
            "emacs": "■",
            "libreoffice": "■",  # Solid square - documents
            "word": "■",
            "excel": "■",
            "spotify": "■",  # Solid square - media
            "music": "■",
        }

        # Check for exact match first
        if app_name.lower() in app_squares:
            return app_squares[app_name.lower()]

        # Check for partial matches
        for app, square in app_squares.items():
            if app in app_name.lower():
                return square

        return "■"  # Default solid square

    def _get_context_style(self, app_name: str) -> str:
        """Get style class for application context."""
        app_styles = {
            "terminal": "log.context.terminal",
            "code": "log.context.terminal",
            "kitty": "log.context.terminal",
            "alacritty": "log.context.terminal",
            "iterm": "log.context.terminal",
            "gnome-terminal": "log.context.terminal",
            "konsole": "log.context.terminal",
            "firefox": "log.context.browser",
            "chrome": "log.context.browser",
            "chromium": "log.context.browser",
            "safari": "log.context.browser",
            "edge": "log.context.browser",
            "slack": "log.context.chat",
            "discord": "log.context.chat",
            "telegram": "log.context.chat",
            "whatsapp": "log.context.chat",
            "obsidian": "log.context.editor",
            "notion": "log.context.editor",
            "vscode": "log.context.terminal",
            "vim": "log.context.terminal",
            "emacs": "log.context.terminal",
            "libreoffice": "log.context.editor",
            "word": "log.context.editor",
            "excel": "log.context.editor",
            "spotify": "log.context.media",
            "music": "log.context.media",
        }

        # Check for exact match first
        if app_name.lower() in app_styles:
            return app_styles[app_name.lower()]

        # Check for partial matches
        for app, style in app_styles.items():
            if app in app_name.lower():
                return style

        return "log.context.editor"  # Default style

    def _get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Get the system prompt that would be used for correction."""
        if not self.corrector:
            return "No LLM available"

        try:
            # Get the prompt that would be constructed
            base_prompt = self.config.llm.base_prompt

            if context and hasattr(self.corrector, "_build_prompt"):
                # If corrector has a prompt builder, use it
                full_prompt = self.corrector._build_prompt(base_prompt, context)
                return full_prompt

            return base_prompt
        except Exception:
            return "Error getting prompt"

    def get_status_info(self) -> Dict[str, Any]:
        """Get current status information."""
        status = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "config_file": str(self.config_manager.get_config_path()),
            "recording": self.recording,
        }

        # Mode status
        if self.mode_manager:
            mode_info = self.mode_manager.get_status_info()
            status["mode"] = {
                "current": mode_info["current_mode"],
                "display": mode_info["mode_display"],
            }
        else:
            status["mode"] = {
                "current": "transcription",
                "display": "Transcription",
            }

        # LLM status
        if self.llm_service:
            status["llm"] = {
                "provider": self.config.llm.provider,
                "model": self.config.llm.model,
                "connected": self.llm_connected,
                "base_url": self.config.llm.base_url,
            }
        else:
            status["llm"] = {
                "provider": "disabled",
                "model": "none",
                "connected": False,
                "base_url": "",
            }

        # Whisper status - use typed config
        status["whisper"] = {
            "model": self.config.whisper.model_name,
            "language": self.config.whisper.language,
        }
        push_to_talk = self.config.push_to_talk
        # Hotkey status - use typed config
        if push_to_talk.enabled:
            status["hotkey"] = f"Push-to-talk: {push_to_talk.key}"
        else:
            use_double_tap = self.config.use_double_tap
            if use_double_tap:
                status["hotkey"] = f"Double-tap: {self.config.hotkey.modifier}"
            else:
                status["hotkey"] = f"Hotkey: {self.config.hotkey.modifier}+{self.config.hotkey.key}"

        # Notifications - use typed config
        status["notifications"] = {
            "audio": self.config.notifications.audio_enabled,
            "visual": self.config.notifications.visual_enabled,
        }

        # Context detection
        if self.context_detector:
            ctx_status = self.context_detector.get_dependency_status()
            status["context"] = {
                "enabled": ctx_status["context_enabled"],
                "available": ctx_status["can_detect"],
                "methods": ctx_status["available_methods"],
            }

            # Get current active context if available
            if ctx_status["can_detect"]:
                try:
                    current_context = self.context_detector.get_active_context()
                    status["current_context"] = {
                        "app": current_context.get("app", "unknown"),
                        "title": current_context.get("title", ""),
                        "method": current_context.get("method", ""),
                    }
                except Exception:
                    status["current_context"] = None
            else:
                status["current_context"] = None
        else:
            status["context"] = {
                "enabled": False,
                "available": False,
                "methods": [],
            }
            status["current_context"] = None

        # TTS status
        if self.tts_service and self.tts_service.is_available():
            tts_status = self.tts_service.get_status_info()
            status["tts"] = {
                "available": True,
                "provider": tts_status.get("current_provider", "unknown"),
                "enabled": self.config.modes.question.tts_enabled,
            }
        else:
            status["tts"] = {
                "available": False,
                "provider": "none",
                "enabled": False,
            }

        # MCP status
        if self.agent_service and hasattr(self.agent_service, 'get_mcp_status'):
            mcp_status = self.agent_service.get_mcp_status()
            status["mcp"] = {
                "available": mcp_status["connected"] > 0,
                "servers": mcp_status["servers"],
                "total": mcp_status["total"],
                "connected": mcp_status["connected"],
            }
        else:
            status["mcp"] = {
                "available": False,
                "servers": [],
                "total": 0,
                "connected": 0,
            }

        return status

    def create_layout(self) -> Layout:
        """Create the application layout based on current view."""
        if self.current_view == 'settings':
            return self._create_settings_layout()
        else:
            return self._create_main_layout()

    def _get_left_panel(self):
        """Get the left panel based on current mode."""
        if self.mode_manager and self.mode_manager.get_current_mode().value == "question":
            # Question mode: Show Chat History only (full height)
            return Frame(
                self.chat_window,
                title="Chat History",
                width=Dimension(weight=60),
            )
        else:
            # Transcription mode: Show Logs only (full height)
            return Frame(
                self.log_textarea,
                title="Logs",
                width=Dimension(weight=60),
            )

    def _create_main_layout(self) -> Layout:
        """Create the main TUI layout."""
        # ASCII Art header
        ascii_control = FormattedTextControl(text=self._get_ascii_art, focusable=False)

        # Create FormattedTextControl for chat (to show colors)
        self.chat_control = FormattedTextControl(
            text=self._get_chat_text,
            focusable=True,
        )

        # Create TextArea widget for logs (scrollable content)
        self.log_textarea = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=True,
            wrap_lines=True,
        )

        # Create FormattedTextControl for status (to show colors)
        self.status_control = FormattedTextControl(
            text=self._get_status_text,
            focusable=True,
        )

        # Store window references for easy access
        self.chat_window = Window(
            self.chat_control,
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        self.log_window = self.log_textarea
        self.status_window = Window(
            self.status_control,
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )

        # Create the layout
        root_container = HSplit(
            [
                # ASCII Art header
                Window(
                    ascii_control,
                    height=lambda: Dimension.exact(
                        self._get_ascii_height()
                    ),  # Dynamic exact height
                    style="class:ascii",
                ),
                # Main content area - conditional left panel based on mode
                VSplit(
                    [
                        # Left side: Show Chat History in question mode, Logs in transcription mode (60% width)
                        self._get_left_panel(),
                        # Status pane (40% width) - now using Window with FormattedTextControl
                        Frame(
                            self.status_window,
                            title="Status",
                            width=Dimension(weight=40),
                        ),
                    ],
                ),
                # Footer
                Window(
                    FormattedTextControl(text=self._get_footer_text),
                    height=1,  # Single row footer
                    style="class:footer",
                ),
            ]
        )

        return Layout(root_container)

    def _create_settings_layout(self) -> Layout:
        """Create the settings layout."""
        if not self.settings_component:
            from ultrawhisper.ui.settings_screen import SettingsComponent
            self.settings_component = SettingsComponent(self.config_manager, self._on_settings_close, self.application)

        return Layout(self.settings_component.get_container())

    def _get_ascii_art(self) -> FormattedText:
        """Generate ASCII art header with responsive layout and colors."""
        return get_ultrawhisper_ascii_art(
            application=self.application,
            animation_frame=self.animation_frame
        )

    def _get_ascii_height(self) -> int:
        """Get dynamic height for ASCII art based on actual content."""
        return get_ascii_height(application=self.application)

    def _get_status_header(self, title: str) -> FormattedText:
        """Generate a full-width status section header with colored gradient blocks on left."""
        # Create gradient block pattern on left (4 chars) with individual colors
        return FormattedText([
            ("class:status.gradient1", "░"),
            ("class:status.gradient2", "▒"),
            ("class:status.gradient3", "▓"),
            ("class:status.gradient4", "█"),
            ("class:status.section_header", f" [{title}]\n"),
        ])

    def _get_status_line_count(self) -> int:
        """Count the number of lines in status text."""
        status_text = self._get_status_text()
        return len([line for style, line in status_text if '\n' in line])

    def _get_centered_mode_text(self, mode_name: str, width: int = 19) -> str:
        """Center mode name in the box."""
        padding = (width - len(mode_name)) // 2
        return f"{' ' * padding}{mode_name}{' ' * (width - len(mode_name) - padding)}"

    def _get_status_text(self) -> FormattedText:
        """Generate status panel text."""
        status = self.get_status_info()
        lines = []

        # Add padding at top
        lines.append(("", " \n"))

        # Mode display without box - aligned left with light background
        if status["mode"]["current"] == "question":
            # Add cute character first
            lines.append(("class:status.info", "           ▓▓▓▓▓▓▓▓▓▓           \n"))
            lines.append(("class:status.info", "         ▓▓▓▓▓▓▓▓▓▓▓▓▓▓         \n"))
            lines.append(("class:status.info", "       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓       \n"))
            lines.append(("class:status.info", "     ▓▓▓▓░░░░░░▓▓░░░░░░▓▓▓▓     \n"))
            lines.append(("class:status.info", " ░░░░▓▓░░░░░░░░░░░░░░░░░░▓▓░░░░ \n"))
            lines.append(("class:status.info", " ░░░░▓▓░░  ██░░░░░░  ██░░▓▓░░░░ \n"))
            lines.append(("class:status.info", "   ░░▓▓░░████░░░░░░████░░▓▓░░   \n"))
            lines.append(("class:status.info", "     ▓▓░░░░░░░░░░░░░░░░░░▓▓     \n"))
            lines.append(("class:status.info", "       ▓▓░░░░░░░░░░░░░░▓▓       \n"))
            lines.append(("class:status.info", "         ▓▓▓▓░░░░░░▓▓▓▓         \n"))
            lines.append(("class:status.info", "             ▓▓▓▓▓▓             \n"))
            lines.append(("class:status.info", "           ▓▓▓▓▓▓▓▓▓▓           \n"))

            # CHAT label centered under character
            mode_text = "CHAT"
            lines.append(("class:status.mode_question", f"              {mode_text}              \n"))

            # Recording status centered under CHAT
            if status["recording"]:
                lines.append(("class:status.led_on", "          ● Recording          \n"))
            else:
                lines.append(("class:status.led_off", "           ○ Standby           \n"))
            lines.append(("", "\n"))

            # Add conversation info if available
            if "conversation" in status["mode"]:
                conv = status["mode"]["conversation"]
                lines.append(("class:status.info", f"     {conv['turns']} turns, {conv['total_messages']} messages\n"))
                if conv["active_contexts"]:
                    contexts_str = ", ".join(conv["active_contexts"][:3])
                    lines.append(("class:status.info", f"     Active in: {contexts_str}\n"))
        else:
            mode_text = "TRANSCRIPTION"
            lines.append(("class:status.mode_transcription", f"     {mode_text}     \n"))

            # Recording status indicator under mode
            if status["recording"]:
                lines.append(("class:status.led_on", "     ● Recording\n"))
            else:
                lines.append(("class:status.led_off", "     ○ Standby\n"))
            lines.append(("", "\n"))

        # LLM Section with gradient
        lines.extend(self._get_status_header("LLM"))
        lines.append(("class:status.value", f"     » {status['llm']['provider']}\n"))
        lines.append(("class:status.value", f"     » {status['llm']['model']}\n"))

        if status["llm"]["connected"]:
            lines.append(("class:status.success", "     ◉ Connected\n"))
        else:
            lines.append(("class:status.error", "     ○ Connected\n"))

        lines.append(("", "\n"))

        # CONTEXT Section with gradient
        lines.extend(self._get_status_header("CONTEXT"))
        if status["current_context"]:
            current = status["current_context"]
            app = current["app"] if current["app"] != "unknown" else "none"
            title = current["title"][:40] + "..." if len(current["title"]) > 40 else current["title"]
            uri = current.get("uri", "none")

            lines.append(("class:status.value", f"     » Process: {app}\n"))
            lines.append(("class:status.value", f"     » Window:  {title}\n"))
            lines.append(("class:status.value", f"     » URI:     {uri}\n"))
        else:
            lines.append(("class:status.value", "     » Process: none\n"))
            lines.append(("class:status.value", "     » Window:  none\n"))
            lines.append(("class:status.value", "     » URI:     none\n"))

        lines.append(("", "\n"))

        # SYSTEM Section with gradient
        lines.extend(self._get_status_header("SYSTEM"))

        lines.append(("class:status.value", f"     whisper {status['whisper']['model']}.{status['whisper']['language']}\n"))

        if status["tts"]["available"]:
            lines.append(("class:status.value", f"     TTS {status['tts']['provider']}\n"))
        else:
            lines.append(("class:status.value", "     TTS system\n"))

        # Audio indicator with circle
        if status["notifications"]["audio"]:
            lines.append(("class:status.success", "     ◉ Audio\n"))
        else:
            lines.append(("class:status.info", "     ○ Audio\n"))

        # Visual indicator with circle
        if status["notifications"]["visual"]:
            lines.append(("class:status.success", "     ◉ Visual\n"))
        else:
            lines.append(("class:status.info", "     ○ Visual\n"))

        # MCP Section with gradient
        if status["mcp"]["total"] > 0:
            lines.append(("", "\n"))
            lines.extend(self._get_status_header("MCP"))

            # Show server details with circles
            for server in status["mcp"]["servers"]:
                server_name = server.get("name", "Unknown")
                is_connected = server.get("connected", False)

                if is_connected:
                    lines.append(("class:status.success", f"     ◉ {server_name}: Connected\n"))
                else:
                    lines.append(("class:status.error", f"     ○ {server_name}: Failed\n"))

        # Mode switching instructions at the bottom in italics (no label)
        lines.append(("", "\n"))
        lines.append(("class:status.instructions", '     Say "transcription mode" to switch to transcription\n'))
        lines.append(("class:status.instructions", '     Say "chat mode" to switch to chat mode\n'))

        return FormattedText(lines)

    def _get_log_text(self) -> FormattedText:
        """Generate styled log text for display."""
        from prompt_toolkit.formatted_text import FormattedText

        formatted_messages = []

        for msg in self.messages:
            if isinstance(msg, tuple):
                # Styled message (style, text)
                style, text = msg
                formatted_messages.append((f"class:{style}", text + "\n"))
            else:
                # Plain text message
                formatted_messages.append(("", msg + "\n"))

        return FormattedText(formatted_messages)

    def _get_chat_text(self) -> FormattedText:
        """Generate chat history text for display."""
        from prompt_toolkit.formatted_text import FormattedText

        formatted_messages = []

        # Only show chat history in question mode
        if not self.mode_manager or self.mode_manager.get_current_mode().value != "question":
            formatted_messages.append(("class:chat.info", "Chat history is only available in Question mode.\n\n"))
            formatted_messages.append(("class:chat.info", "Say 'question mode' to switch.\n"))
            return FormattedText(formatted_messages)

        # Get recent conversation messages
        if hasattr(self.mode_manager, 'conversation_history'):
            messages = self.mode_manager.conversation_history.get_recent_messages(20)

            if not messages:
                formatted_messages.append(("class:chat.info", "No conversation history yet.\n\n"))
                formatted_messages.append(("class:chat.info", "Start asking questions to see the conversation here.\n"))
            else:
                # Display messages in chronological order
                for i, msg in enumerate(messages):
                    timestamp = msg.timestamp.strftime("%H:%M:%S")
                    is_last_message = (i == len(messages) - 1)

                    if msg.role == "user":
                        # User messages
                        formatted_messages.append(("class:chat.timestamp", f"{timestamp} "))
                        formatted_messages.append(("class:chat.user_label", "You: "))
                        formatted_messages.append(("class:chat.user_text", f"{msg.content}\n\n"))
                    else:
                        # Assistant messages - animate if it's the thinking indicator
                        formatted_messages.append(("class:chat.timestamp", f"{timestamp} "))
                        formatted_messages.append(("class:chat.assistant_label", "AI: "))

                        # Check if this is the thinking indicator and should be animated
                        if is_last_message and self.thinking_indicator_active and msg.content == "⏳ Thinking...":
                            # Animate the thinking indicator
                            spinner = self.thinking_spinner_patterns[
                                self.thinking_animation_frame % len(self.thinking_spinner_patterns)
                            ]
                            formatted_messages.append(("class:chat.assistant_text", f"{spinner} Thinking...\n\n"))
                        else:
                            # Normal message display
                            formatted_messages.append(("class:chat.assistant_text", f"{msg.content}\n\n"))
        else:
            formatted_messages.append(("class:chat.error", "Chat history not available.\n"))

        return FormattedText(formatted_messages)

    def _get_footer_text(self) -> str:
        """Generate footer text with shortcuts and config path."""
        try:
            width = (
                self.application.output.get_size().columns if self.application else 80
            )
        except:
            width = 80

        shortcuts = "  [Ctrl+Q] quit   [M] mode   [X] stop tts   [R] reload   [C] clear"
        config_path = str(self.config_manager.get_config_path())

        # Calculate padding to right-align config path
        available_space = width - len(shortcuts) - len(config_path)
        padding = max(1, available_space)

        return f"{shortcuts}{' ' * padding}{config_path}\n"

    def create_key_bindings(self) -> KeyBindings:
        """Create key bindings for the application."""
        kb = KeyBindings()

        @kb.add("c-q")
        def _(event):
            """Quit the application."""
            event.app.exit()

        @kb.add("r")
        def _(event):
            """Reload configuration."""
            self.config = self.config_manager.load_config()
            self._init_services()
            self.add_message("Configuration reloaded")

        @kb.add("c")
        def _(event):
            """Clear logs or chat based on current mode."""
            if self.mode_manager:
                current_mode = self.mode_manager.get_current_mode()
                if current_mode == Mode.QUESTION:
                    self.clear_chat_history()
                else:
                    self.clear_logs()
            else:
                self.clear_logs()

        @kb.add("m")
        def _(event):
            """Toggle between transcription and question mode."""
            if self.mode_manager:
                current_mode = self.mode_manager.get_current_mode()
                if current_mode == Mode.TRANSCRIPTION:
                    self.mode_manager.switch_mode(Mode.QUESTION)
                    self.add_message("Switched to Question mode", style="log.info")
                    # Rebuild layout to show chat panel
                    if self.application:
                        self.application.layout = self.create_layout()
                        self.application.invalidate()
                else:
                    self.mode_manager.switch_mode(Mode.TRANSCRIPTION)
                    self.add_message("Switched to Transcription mode", style="log.info")
                    # Rebuild layout to show logs panel
                    if self.application:
                        self.application.layout = self.create_layout()
                        self.application.invalidate()

        @kb.add("x")
        def _(event):
            """Stop TTS playback."""
            if self.tts_service and hasattr(self, 'tts_service'):
                self.tts_service.stop_speaking()
                self.add_message("🔊 TTS stopped", style="log.info")

        # Note: PageUp/PageDown scrolling is handled automatically by enable_page_navigation_bindings=True
        # Arrow keys need custom handling for read-only TextAreas

        @kb.add("up")
        def _(event):
            """Scroll up one line or focus previous field in settings."""
            if self.current_view == 'settings':
                event.app.layout.focus_previous()
            elif self.current_view == 'main':
                # Get current buffer and move cursor up (which scrolls the view)
                buffer = event.app.current_buffer
                if buffer:
                    buffer.cursor_up(count=1)

        @kb.add("down")
        def _(event):
            """Scroll down one line or focus next field in settings."""
            if self.current_view == 'settings':
                event.app.layout.focus_next()
            elif self.current_view == 'main':
                # Get current buffer and move cursor down (which scrolls the view)
                buffer = event.app.current_buffer
                if buffer:
                    buffer.cursor_down(count=1)

        @kb.add("escape")
        def _(event):
            """Handle escape key - close settings if open, otherwise quit."""
            if self.current_view == 'settings':
                self._on_settings_close(False)  # Cancel settings
            else:
                event.app.exit()

        @kb.add("c-s")
        def _(event):
            """Handle Ctrl+S - save settings if in settings view."""
            if self.current_view == 'settings' and self.settings_component:
                self.settings_component._save_config()

        @kb.add("tab")
        def _(event):
            """Handle tab - focus next field in settings."""
            if self.current_view == 'settings':
                event.app.layout.focus_next()

        @kb.add("s-tab")
        def _(event):
            """Handle shift+tab - focus previous field in settings."""
            if self.current_view == 'settings':
                event.app.layout.focus_previous()

        return kb

    def create_style(self) -> Style:
        """Create the application style - Neon Paradise theme."""
        # Neon Paradise color palette
        bg = "#0a1400"
        text = "#d0ffe0"
        dim = "#669977"
        bright = "#ffffff"
        accent = "#00ff88"
        # Gradient colors for section headers
        gradient1 = "#00ff88"  # Mint
        gradient2 = "#00ffff"  # Cyan
        gradient3 = "#ff00ff"  # Magenta
        gradient4 = "#ffff00"  # Yellow

        base_styles = {
            # Global background
            "": f"bg:{bg} {text}",

            # Status panel styles
            "status.header": f"bg:{bg} {bright} bold",
            "status.section_header": f"bg:{bg} {bright} bold",  # Section headers
            "status.label": f"bg:{bg} {text}",
            "status.value": f"bg:{bg} {text}",
            "status.success": f"bg:{bg} {accent} bold",  # Connected indicators
            "status.error": f"bg:{bg} {dim}",  # Disconnected/off indicators
            "status.text": f"bg:{bg} {text}",
            # New status styles
            "status.warning": f"bg:{bg} {accent} bold",
            "status.info": f"bg:{bg} {dim} italic",  # Informational text under headers
            "status.instructions": f"bg:{bg} {dim} italic",  # Instructions at bottom
            "status.context_highlight": f"bg:{accent} {bg}",
            # Mode status styles - accent background with dark text
            "status.mode_transcription": f"bg:{accent} {bg}",
            "status.mode_question": f"bg:{accent} {bg}",
            # LED-style indicators for LLM status
            "status.led_on": f"bg:{bg} {accent} bold",  # Accent color for active
            "status.led_off": f"bg:{bg} {dim}",  # Dim for inactive
            # Recording status
            "status.recording": f"bg:{accent} {bg} bold",
            "status.ready": f"bg:{bg} {text} bold",
            # Boolean display styles
            "status.boolean_on": f"bg:{bg} {accent} bold",
            "status.boolean_off": f"bg:{bg} {dim}",
            # Gradient styles for section headers
            "status.gradient1": f"bg:{bg} {gradient1} bold",
            "status.gradient2": f"bg:{bg} {gradient2} bold",
            "status.gradient3": f"bg:{bg} {gradient3} bold",
            "status.gradient4": f"bg:{bg} {gradient4} bold",
            # ASCII Art styles with Neon Paradise colors - Rainbow scheme
            "ascii.ultra": f"{gradient1} bold",  # Mint for ULTRA
            "ascii.whisper": f"{gradient3} bold",  # Magenta for WHISPER
            "ascii.border": f"{gradient2}",  # Cyan for borders
            "ascii.waves": f"{gradient4}",  # Yellow for sound waves
            "ascii.accent": f"{accent} bold",  # Accent for decorative elements
            "ascii.shadow": f"{dim}",  # Dim for shadows
            # Log message styles
            "log.transcription": f"bg:{bg} {text}",
            "log.correction": f"bg:{bg} {text} bold",
            "log.output": f"bg:{bg} {bright} bold underline",
            "log.corrected": f"bg:{bg} {accent}",  # For corrected text
            "log.context.terminal": f"bg:{bg} {text}",
            "log.context.browser": f"bg:{bg} {text}",
            "log.context.chat": f"bg:{bg} {text}",
            "log.context.editor": f"bg:{bg} {text}",
            "log.context.media": f"bg:{bg} {text}",
            "log.info": f"bg:{bg} {dim} italic",
            "log.error": f"bg:{accent} {bg} bold",
            "log.warning": f"bg:{bg} {accent}",
            # Chat panel styles
            "chat.info": f"bg:{bg} {dim} italic",
            "chat.error": f"bg:{bg} {accent} bold",
            "chat.timestamp": f"bg:{bg} {dim}",
            "chat.user_label": f"bg:{bg} {bright} bold",
            "chat.user_text": f"bg:{bg} {bright}",
            "chat.assistant_label": f"bg:{bg} {accent} bold",
            "chat.assistant_text": f"bg:{bg} {accent} italic",
            # Footer style
            "footer": f"bg:{text} {bg} bold",
        }

        # Add settings styles if settings component exists
        if hasattr(self, 'settings_component') and self.settings_component:
            settings_styles = self.settings_component.get_style_dict()
            base_styles.update(settings_styles)

        return Style.from_dict(base_styles)

    def _open_settings(self) -> None:
        """Open the settings screen by switching views."""
        try:
            self.current_view = 'settings'
            self.application.layout = self.create_layout()
            self.application.invalidate()
        except Exception as e:
            self.add_message(f"Error opening settings: {e}")
            import traceback
            self.add_message(f"Settings error traceback: {traceback.format_exc()}")

    def _on_settings_close(self, saved: bool) -> None:
        """Handle settings screen closing."""
        try:
            if saved:
                # Reload configuration and reinitialize services
                self.config = self.config_manager.load_config()
                self._init_services()
                self.add_message("✓ Settings saved and configuration reloaded")
            else:
                self.add_message("Settings cancelled")

            # Switch back to main view
            self.current_view = 'main'
            self.settings_component = None  # Clear settings component
            self.application.layout = self.create_layout()
            self.application.invalidate()
        except Exception as e:
            self.add_message(f"Error closing settings: {e}")
            import traceback
            self.add_message(f"Settings close error: {traceback.format_exc()}")

    def _format_text_to_plain(self, formatted_text: FormattedText) -> str:
        """Convert FormattedText to plain text string."""
        result = []
        for item in formatted_text:
            if isinstance(item, tuple):
                # (style, text) tuple
                result.append(item[1])
            else:
                result.append(str(item))
        return ''.join(result)

    def update_logs(self) -> None:
        """Update the log display with current messages."""
        if self.application and self.current_view == 'main':
            # Status and chat panels use FormattedTextControl - no need to update, they will refresh automatically

            # Update TextArea contents for logs only
            if self.log_textarea:
                log_text = self._format_text_to_plain(self._get_log_text())
                if self.log_textarea.text != log_text:
                    cursor_pos = self.log_textarea.document.cursor_position
                    self.log_textarea.text = log_text
                    try:
                        self.log_textarea.buffer.cursor_position = min(cursor_pos, len(log_text))
                    except:
                        pass

            self.application.invalidate()

    def run(self) -> None:
        """Run the TUI application."""
        # Create the application
        self.application = Application(
            layout=self.create_layout(),
            key_bindings=self.create_key_bindings(),
            style=self.create_style(),
            full_screen=True,
            mouse_support=True,
            enable_page_navigation_bindings=True,
        )

        # Hide the blinking cursor since we don't have text input in main view
        self.application.output.show_cursor = lambda: None

        # Start update timer
        def update_timer():
            import traceback

            while not self.application.is_done:
                time.sleep(0.1)  # Update 10 times per second for smooth animation
                if not self.application.is_done:
                    try:
                        # Cycle animation frame for pulse dots
                        self.animation_frame += 1
                        # Cycle thinking animation frame if active
                        if self.thinking_indicator_active:
                            self.thinking_animation_frame += 1
                        self.update_logs()
                        self.application.invalidate()
                    except Exception as e:
                        # Log timer errors (but don't break the loop)
                        self.add_message(f"Timer update error: {e}")
                        self.add_message(f"Timer traceback: {traceback.format_exc()}")

        timer_thread = threading.Thread(target=update_timer, daemon=True)
        timer_thread.start()

        # Start hotkey manager for transcription mode
        if self.hotkey_manager:
            try:
                self.hotkey_manager.start()
                logger.info("Transcription hotkey manager started successfully")
            except Exception as e:
                logger.error(f"Failed to start transcription hotkey manager: {e}")

        # Start question mode hotkey manager
        if self.question_hotkey_manager:
            try:
                self.question_hotkey_manager.start()
                logger.info("Question mode hotkey manager started successfully")
            except Exception as e:
                logger.error(f"Failed to start question mode hotkey manager: {e}")

        # Ready to use
        logger.info("TUI application ready")

        # Initial log update to show startup messages
        self.update_logs()

        try:
            self.application.run()
        except KeyboardInterrupt:
            self.add_message("Keyboard interrupt received")
        except Exception as e:
            error_msg = f"Application error: {str(e)}"
            logger.error(error_msg)
            import traceback

            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            # Show minimal error in TUI
            from pathlib import Path

            self.add_message(
                f"Error: {str(e)[:100]}{'...' if len(str(e)) > 100 else ''}"
            )
            self.add_message(
                f"■ See log: {Path(self.log_file_path).name}", style="log.error"
            )
        finally:
            # Stop TTS if playing
            if self.tts_service:
                try:
                    self.tts_service.stop_speaking()
                    self.add_message("TTS stopped")
                except Exception as e:
                    self.add_message(f"Error stopping TTS: {e}")

            # Stop hotkey managers
            if self.hotkey_manager:
                try:
                    self.hotkey_manager.stop()
                    self.add_message("Transcription hotkey manager stopped")
                except Exception as e:
                    self.add_message(f"Error stopping transcription hotkey manager: {e}")

            if self.question_hotkey_manager:
                try:
                    self.question_hotkey_manager.stop()
                    self.add_message("Question mode hotkey manager stopped")
                except Exception as e:
                    self.add_message(f"Error stopping question mode hotkey manager: {e}")

            self.add_message("TUI stopped")

    def _process_transcription_mode(self, text: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Process text in transcription mode (existing behavior)."""
        try:
            original_text = text

            # Correct the text if LLM is available
            if self.corrector and self.llm_connected:
                try:
                    if self.show_prompts:
                        prompt = self._get_system_prompt(context)
                        self.add_message(f"🧠 {prompt[:100]}...")

                    text = self.corrector.correct(text, context=context)
                except Exception:
                    pass

            # Log the transcription
            if self.mode_logger:
                self.mode_logger.log_transcription(original_text, text if text != original_text else None, context)

            # Output the text
            output_mode = (
                "paste" if self.config.output.paste_mode else "type"
            )
            LogHelper.text_output(text, output_mode)
            self._output_text(text)

        except Exception as e:
            self.add_message(f"Error processing transcription mode: {e}")

    def _process_question_mode(self, text: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Process text in question mode."""
        try:
            if not self.corrector or not self.llm_connected:
                self.add_message("🤔 Question mode requires LLM, but LLM is not available", style="log.warning")
                # Fall back to just logging the question
                if self.mode_logger:
                    self.mode_logger.log_question_answer(text, "LLM not available", context)
                return

            # Add user message to conversation history IMMEDIATELY
            if self.mode_manager:
                try:
                    self.mode_manager.add_user_message(text, context)
                except Exception as e:
                    self.add_message(f"Failed to add user message to conversation history: {e}", style="log.warning")

            # Get question mode configuration
            question_config = self.mode_manager.get_mode_config()

            # Get context-aware prompt for question mode
            app_name = context.get('app', 'default') if context else 'default'
            context_prompts = question_config.get('context_prompts', {})
            system_prompt = context_prompts.get(app_name) or context_prompts.get('default',
                'You are a helpful AI assistant. Provide concise, accurate answers to user questions.')

            # Add a "thinking" indicator to conversation history
            if self.mode_manager:
                try:
                    # Add a temporary "thinking" message that we'll replace with the actual response
                    self.mode_manager.add_assistant_message("⏳ Thinking...", context)
                    # Enable animation
                    self.thinking_indicator_active = True
                    self.thinking_animation_frame = 0
                except Exception as e:
                    pass

            # Create a simple question/answer exchange
            self.add_message("🧠 Generating response...", style="log.info")

            # Get the response from LLM (conversation history will be handled in _get_llm_response)
            response = self._get_llm_response(text, system_prompt, context)

            # Disable animation now that we have a response
            self.thinking_indicator_active = False

            if response:
                # Replace the "thinking" message with the actual response
                # Remove the last message (thinking indicator) and add the real response
                if self.mode_manager:
                    try:
                        # Remove the thinking indicator
                        if hasattr(self.mode_manager, 'conversation_history'):
                            messages = self.mode_manager.conversation_history.messages
                            if messages and messages[-1].content == "⏳ Thinking...":
                                messages.pop()
                        # Add the actual response
                        self.mode_manager.add_assistant_message(response, context)
                    except Exception as e:
                        self.add_message(f"Failed to add assistant message to conversation history: {e}", style="log.warning")

                # Log the question and answer
                if self.mode_logger:
                    self.mode_logger.log_question_answer(text, response, context)

                # Play TTS if enabled and available
                tts_enabled = question_config.get('tts_enabled', False)
                logger.info(f"🔊 TTS enabled in config: {tts_enabled}")
                logger.info(f"🔊 TTS service exists: {hasattr(self, 'tts_service')}")
                logger.info(f"🔊 TTS service not None: {self.tts_service is not None}")
                if self.tts_service:
                    logger.info(f"🔊 TTS service available: {self.tts_service.is_available()}")

                if tts_enabled and hasattr(self, 'tts_service') and self.tts_service and self.tts_service.is_available():
                    self.add_message("🔊 Playing TTS response...", style="log.info")

                    # Strip URLs from response for TTS output (but keep them in chat log)
                    tts_text, url_count = strip_urls_for_speech(response)
                    if url_count > 0:
                        logger.info(f"🔊 Stripped {url_count} URL(s) from TTS output")

                    logger.info(f"🔊 Attempting to speak: {tts_text}")
                    try:
                        tts_success = self.tts_service.speak(tts_text)
                        logger.info(f"🔊 TTS success: {tts_success}")
                        if not tts_success:
                            self.add_message("🔊 TTS playback failed, continuing without audio", style="log.warning")
                    except Exception as e:
                        logger.error(f"🔊 TTS error: {e}")
                        self.add_message(f"🔊 TTS error: {e}, continuing without audio", style="log.warning")
                elif tts_enabled:
                    self.add_message("🔊 TTS requested but not available", style="log.info")
                    logger.warning("🔊 TTS requested but conditions not met")

                # Display the response in TUI
                self.add_message(f"◄ {response}", style="log.corrected")

                # Output response text if configured
                output_response = question_config.get('output_response', True)
                if output_response:
                    output_mode = (
                        "paste" if self.config.output.paste_mode else "type"
                    )
                    LogHelper.text_output(response, output_mode)
                    self._output_text(response)
                else:
                    self.add_message(f"🤔 Response (not output): {response}", style="log.info")
            else:
                self.add_message("🤔 Failed to get response from LLM", style="log.warning")
                if self.mode_logger:
                    self.mode_logger.log_question_answer(text, "Failed to get response", context)

        except Exception as e:
            self.add_message(f"Error processing question mode: {e}", style="log.error")
            if self.mode_logger:
                self.mode_logger.log_question_answer(text, f"Error: {e}", context)

    def _get_llm_response(self, question: str, system_prompt: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get response from LLM for question mode with conversation history."""
        try:
            # Use OpenAI agents if available and provider is OpenAI
            llm_provider = self.config.llm.provider

            if (self.agent_service and
                self.agent_service.is_available() and
                llm_provider == "openai"):

                self.add_message("🤖 Using OpenAI Agent for response", style="log.info")
                return self.agent_service.get_response(question, context)

            # Fallback to regular LLM service
            if not self.corrector or not hasattr(self.corrector, 'llm_service') or not self.corrector.llm_service:
                return None

            self.add_message("🧠 Using standard LLM for response", style="log.info")

            # Start with system prompt
            messages = [{"role": "system", "content": system_prompt}]

            # Only add conversation history for question mode
            if self.mode_manager and self.mode_manager.get_current_mode().value == "question":
                conversation_history = self.mode_manager.get_conversation_context()
                if conversation_history:
                    # Add all previous messages (current question is not in history yet)
                    messages.extend(conversation_history)
                    self.add_message(f"🗨️ Including {len(conversation_history)} messages from conversation history", style="log.info")

            # Add the current question
            messages.append({"role": "user", "content": question})

            # Use the LLM service to get response
            response = self.corrector.llm_service.complete(messages)
            return response

        except Exception as e:
            self.add_message(f"Error getting LLM response: {e}", style="log.error")
            return None


def main() -> None:
    """Main entry point for the simplified TUI."""
    try:
        tui = SimpleUltraWhisperTUI()
        tui.run()
    except KeyboardInterrupt:
        print("\nTUI interrupted")
    except Exception as e:
        print(f"TUI error: {e}")


if __name__ == "__main__":
    main()
