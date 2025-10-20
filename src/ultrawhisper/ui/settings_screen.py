#!/usr/bin/env python3
"""
Settings screen for UltraWhisper TUI using prompt-toolkit.

Provides an interactive interface for editing all configuration options.
"""

from typing import Dict, Any, Optional, Callable
from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, Container
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, Button, TextArea, Checkbox, Label
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.filters import Condition

from ultrawhisper.config.config import ConfigManager, detect_llm_providers
from ultrawhisper.ui.ascii_art import get_ultrawhisper_ascii_art, get_ascii_height


class SettingsField:
    """Represents a configuration field in the settings screen."""

    def __init__(self, key: str, label: str, field_type: str, widget,
                 validation_func: Optional[Callable] = None):
        self.key = key
        self.label = label
        self.field_type = field_type
        self.widget = widget
        self.validation_func = validation_func
        self.error_message = ""

    def validate(self) -> bool:
        """Validate the field value."""
        if self.validation_func:
            try:
                self.validation_func(self.get_value())
                self.error_message = ""
                return True
            except ValueError as e:
                self.error_message = str(e)
                return False
        return True

    def get_value(self):
        """Get the current value from the widget."""
        if isinstance(self.widget, TextArea):
            return self.widget.text
        elif isinstance(self.widget, Checkbox):
            return self.widget.checked
        else:
            return getattr(self.widget, 'text', '')

    def set_value(self, value):
        """Set the value in the widget."""
        if isinstance(self.widget, TextArea):
            self.widget.text = str(value)
        elif isinstance(self.widget, Checkbox):
            self.widget.checked = bool(value)
        else:
            setattr(self.widget, 'text', str(value))


class ProviderSelector:
    """Special widget for selecting LLM provider with dynamic model list."""

    def __init__(self):
        self.providers = detect_llm_providers()
        self.current_provider = "openai"
        self.current_model = "gpt-4o"

        # Create provider dropdown (simulated with buttons)
        self.provider_buttons = {}
        for provider in self.providers.keys():
            btn = Button(
                text=provider.replace('-', ' ').title(),
                handler=self._make_provider_handler(provider)
            )
            self.provider_buttons[provider] = btn

        # Model text input (will be updated based on provider)
        self.model_input = TextArea(
            text=self.current_model,
            height=1,
            multiline=False,
            wrap_lines=False,
            focusable=True
        )

    def _make_provider_handler(self, provider: str):
        """Create handler for provider selection."""
        def handler():
            self.current_provider = provider
            # Update model with default for this provider
            provider_info = self.providers.get(provider, {})
            models = provider_info.get('models', [])
            if models:
                self.current_model = models[0]
                self.model_input.text = self.current_model
        return handler

    def get_provider(self) -> str:
        return self.current_provider

    def get_model(self) -> str:
        return self.model_input.text

    def set_provider(self, provider: str):
        if provider in self.providers:
            self.current_provider = provider

    def set_model(self, model: str):
        self.current_model = model
        self.model_input.text = model


class SettingsComponent:
    """Interactive settings component for UltraWhisper configuration."""

    def __init__(self, config_manager: ConfigManager, on_close: Callable[[bool], None], application: Optional[Application] = None):
        self.config_manager = config_manager
        self.on_close = on_close  # Callback when closing (True if saved, False if cancelled)
        self.application = application  # For terminal width detection
        self.current_config = config_manager.load_config().copy()
        self.original_config = self.current_config.copy()

        # Track if there are unsaved changes
        self.has_changes = False

        # Fields for each configuration section
        self.fields: Dict[str, SettingsField] = {}
        self.provider_selector = ProviderSelector()

        # Status message
        self.status_message = ""
        self.status_style = "info"

        self._init_fields()

    def _init_fields(self):
        """Initialize all configuration fields."""

        # LLM Provider and Model (handled by provider_selector)
        self.provider_selector.set_provider(self.current_config.get("llm", {}).get("provider", "openai"))
        self.provider_selector.set_model(self.current_config.get("llm", {}).get("model", "gpt-4o"))

        # LLM API Key
        api_key = self.current_config.get("llm", {}).get("api_key", "")
        masked_key = self._mask_api_key(api_key)
        self.fields["llm.api_key"] = SettingsField(
            "llm.api_key", "API Key", "password",
            TextArea(text=masked_key, height=1, multiline=False, password=True, focusable=True),
            self._validate_api_key
        )

        # LLM Base URL
        self.fields["llm.base_url"] = SettingsField(
            "llm.base_url", "Base URL", "text",
            TextArea(
                text=self.current_config.get("llm", {}).get("base_url", ""),
                height=1, multiline=False, focusable=True
            )
        )

        # LLM System Prompt
        self.fields["llm.base_prompt"] = SettingsField(
            "llm.base_prompt", "System Prompt", "textarea",
            TextArea(
                text=self.current_config.get("llm", {}).get("base_prompt", ""),
                height=3, multiline=True, wrap_lines=True, focusable=True
            )
        )

        # Whisper Model
        whisper_models = ["tiny", "base", "small", "medium", "large"]
        current_whisper = self.current_config.get("whisper", {}).get("model_name", "small")
        self.fields["whisper.model_name"] = SettingsField(
            "whisper.model_name", "Whisper Model", "select",
            TextArea(text=current_whisper, height=1, multiline=False, focusable=True)
        )

        # Whisper Language
        self.fields["whisper.language"] = SettingsField(
            "whisper.language", "Language", "text",
            TextArea(
                text=self.current_config.get("whisper", {}).get("language", "en"),
                height=1, multiline=False, focusable=True
            )
        )

        # Double Tap
        self.fields["use_double_tap"] = SettingsField(
            "use_double_tap", "Use Double Tap", "checkbox",
            Checkbox(text="Enable double-tap activation",
                    checked=self.current_config.get("use_double_tap", False))
        )

        # Push to Talk
        push_to_talk = self.current_config.get("push_to_talk", {})
        self.fields["push_to_talk.enabled"] = SettingsField(
            "push_to_talk.enabled", "Push to Talk", "checkbox",
            Checkbox(text="Enable push-to-talk mode",
                    checked=push_to_talk.get("enabled", False))
        )

        # Push to Talk Key
        self.fields["push_to_talk.key"] = SettingsField(
            "push_to_talk.key", "Push to Talk Key", "text",
            TextArea(
                text=push_to_talk.get("key", "Key.cmd"),
                height=1, multiline=False, focusable=True
            )
        )

        # Output Paste Mode
        output_config = self.current_config.get("output", {})
        self.fields["output.paste_mode"] = SettingsField(
            "output.paste_mode", "Paste Mode", "checkbox",
            Checkbox(text="Use clipboard paste instead of typing",
                    checked=output_config.get("paste_mode", False))
        )

        # Typing Delay
        self.fields["output.typing_delay"] = SettingsField(
            "output.typing_delay", "Typing Delay (seconds)", "number",
            TextArea(
                text=str(output_config.get("typing_delay", 0.02)),
                height=1, multiline=False, focusable=True
            ),
            self._validate_float
        )

        # Audio notifications
        notifications = self.current_config.get("notifications", {})
        self.fields["notifications.audio_enabled"] = SettingsField(
            "notifications.audio_enabled", "Audio Notifications", "checkbox",
            Checkbox(text="Enable audio notifications",
                    checked=notifications.get("audio_enabled", True))
        )

        # Visual notifications
        self.fields["notifications.visual_enabled"] = SettingsField(
            "notifications.visual_enabled", "Visual Notifications", "checkbox",
            Checkbox(text="Enable visual notifications",
                    checked=notifications.get("visual_enabled", False))
        )

        # Context Detection
        self.fields["context_detection"] = SettingsField(
            "context_detection", "Context Detection", "checkbox",
            Checkbox(text="Enable context-aware prompts",
                    checked=self.current_config.get("context_detection", True))
        )

    def _mask_api_key(self, api_key: str) -> str:
        """Mask API key for display."""
        if not api_key:
            return ""
        if len(api_key) <= 8:
            return "*" * len(api_key)
        return "*" * (len(api_key) - 4) + api_key[-4:]

    def _validate_api_key(self, value: str) -> None:
        """Validate API key format."""
        if not value or value.startswith("*"):
            # Empty or masked key is allowed
            return
        if len(value) < 10:
            raise ValueError("API key appears too short")

    def _validate_float(self, value: str) -> None:
        """Validate float value."""
        try:
            float_val = float(value)
            if float_val < 0:
                raise ValueError("Value must be positive")
        except ValueError:
            raise ValueError("Must be a valid number")

    def create_layout(self) -> Layout:
        """Create the settings screen layout."""

        # ASCII Art header
        ascii_control = FormattedTextControl(
            text=self._get_ascii_art,
            focusable=False
        )

        # Create sections
        sections = []

        # Helper function to create section header
        def create_section_header(title: str) -> Window:
            return Window(
                FormattedTextControl(text=f"═══ {title} ═══"),
                height=1,
                style="class:section.header"
            )

        # LLM Configuration Section
        sections.append(create_section_header("🧠 LLM Configuration"))
        sections.extend([
            self._create_field_row("Provider", self._create_provider_selector()),
            self._create_field_row("Model", self.provider_selector.model_input),
            self._create_field_row("API Key", self.fields["llm.api_key"].widget),
            self._create_field_row("Base URL", self.fields["llm.base_url"].widget),
            self._create_field_row("System Prompt", self.fields["llm.base_prompt"].widget),
        ])

        # Whisper Configuration Section
        sections.append(create_section_header("🎤 Whisper Configuration"))
        sections.extend([
            self._create_field_row("Model", self.fields["whisper.model_name"].widget),
            self._create_field_row("Language", self.fields["whisper.language"].widget),
        ])

        # Hotkey Configuration Section
        sections.append(create_section_header("⌨️  Hotkey Configuration"))
        sections.extend([
            self._create_field_row("", self.fields["use_double_tap"].widget),
            self._create_field_row("", self.fields["push_to_talk.enabled"].widget),
            self._create_field_row("PTT Key", self.fields["push_to_talk.key"].widget),
        ])

        # Output Configuration Section
        sections.append(create_section_header("📤 Output Configuration"))
        sections.extend([
            self._create_field_row("", self.fields["output.paste_mode"].widget),
            self._create_field_row("Typing Delay", self.fields["output.typing_delay"].widget),
        ])

        # Notifications Section
        sections.append(create_section_header("🔔 Notifications & Features"))
        sections.extend([
            self._create_field_row("", self.fields["notifications.audio_enabled"].widget),
            self._create_field_row("", self.fields["notifications.visual_enabled"].widget),
            self._create_field_row("", self.fields["context_detection"].widget),
        ])

        # Buttons
        button_row = VSplit([
            Button(text="Save", handler=self._save_config),
            Button(text="Cancel", handler=self._cancel),
            Button(text="Test Connection", handler=self._test_connection),
        ], padding=2)

        # Status message
        status_control = FormattedTextControl(
            text=self._get_status_text,
            focusable=False
        )

        # Main layout
        root_container = HSplit([
            # ASCII Art header
            Window(
                ascii_control,
                height=lambda: self._get_ascii_height(),
                style="class:ascii",
            ),
            Window(height=1),  # Spacer after header
            *sections,  # Unpack sections directly
            Window(height=1),  # Spacer
            button_row,
            Window(height=1),  # Spacer
            Window(status_control, height=1, style="class:status"),
            Window(
                FormattedTextControl(text="Tab=next field | Shift+Tab=previous | Enter=activate | Escape=cancel"),
                height=1,
                style="class:help"
            ),
        ])

        return Layout(root_container)

    def get_container(self) -> Container:
        """Get the root container for embedding in another layout."""
        layout = self.create_layout()
        return layout.container

    def _get_ascii_art(self) -> FormattedText:
        """Generate ASCII art header with responsive layout and colors."""
        return get_ultrawhisper_ascii_art(
            application=self.application,
            animation_frame=0,  # No animation in settings
            subtitle="Settings"
        )

    def _get_ascii_height(self) -> int:
        """Get dynamic height for ASCII art based on actual content."""
        return get_ascii_height(application=self.application, subtitle="Settings")

    def _create_provider_selector(self) -> Container:
        """Create a provider selector widget."""
        provider_buttons = []
        for provider_name, btn in self.provider_selector.provider_buttons.items():
            provider_buttons.append(btn)

        return VSplit(provider_buttons, padding=1)

    def _create_field_row(self, label: str, widget) -> Container:
        """Create a row with label and widget."""
        if not label:
            # For checkboxes that include their own label
            return HSplit([
                widget,
                Window(height=1)  # Add spacing
            ])

        return HSplit([
            VSplit([
                Window(
                    FormattedTextControl(text=f"{label}:"),
                    width=20,
                    style="class:label"
                ),
                widget
            ]),
            Window(height=1)  # Add spacing between rows
        ])

    def _get_status_text(self) -> FormattedText:
        """Get status text with styling."""
        if not self.status_message:
            if self.has_changes:
                return FormattedText([("class:warning", "● Unsaved changes")])
            else:
                return FormattedText([("class:info", "Ready")])

        style_class = f"class:{self.status_style}"
        return FormattedText([(style_class, self.status_message)])

    def _save_config(self):
        """Save the current configuration."""
        try:
            # Validate all fields
            all_valid = True
            for field in self.fields.values():
                if not field.validate():
                    all_valid = False

            if not all_valid:
                self.status_message = "Please fix validation errors"
                self.status_style = "error"
                return

            # Build new config
            new_config = self.current_config.copy()

            # Update LLM settings
            if "llm" not in new_config:
                new_config["llm"] = {}

            new_config["llm"]["provider"] = self.provider_selector.get_provider()
            new_config["llm"]["model"] = self.provider_selector.get_model()

            # Handle API key (only update if not masked)
            api_key_value = self.fields["llm.api_key"].get_value()
            if api_key_value and not api_key_value.startswith("*"):
                new_config["llm"]["api_key"] = api_key_value

            new_config["llm"]["base_url"] = self.fields["llm.base_url"].get_value()
            new_config["llm"]["base_prompt"] = self.fields["llm.base_prompt"].get_value()

            # Update other sections
            if "whisper" not in new_config:
                new_config["whisper"] = {}
            new_config["whisper"]["model_name"] = self.fields["whisper.model_name"].get_value()
            new_config["whisper"]["language"] = self.fields["whisper.language"].get_value()

            new_config["use_double_tap"] = self.fields["use_double_tap"].get_value()

            if "push_to_talk" not in new_config:
                new_config["push_to_talk"] = {}
            new_config["push_to_talk"]["enabled"] = self.fields["push_to_talk.enabled"].get_value()
            new_config["push_to_talk"]["key"] = self.fields["push_to_talk.key"].get_value()

            if "output" not in new_config:
                new_config["output"] = {}
            new_config["output"]["paste_mode"] = self.fields["output.paste_mode"].get_value()
            new_config["output"]["typing_delay"] = float(self.fields["output.typing_delay"].get_value())

            if "notifications" not in new_config:
                new_config["notifications"] = {}
            new_config["notifications"]["audio_enabled"] = self.fields["notifications.audio_enabled"].get_value()
            new_config["notifications"]["visual_enabled"] = self.fields["notifications.visual_enabled"].get_value()

            new_config["context_detection"] = self.fields["context_detection"].get_value()

            # Save to file
            self.config_manager.save_config(new_config)

            self.status_message = "✓ Configuration saved successfully"
            self.status_style = "success"
            self.has_changes = False

            # Call the close callback with success
            if self.on_close:
                self.on_close(True)

        except Exception as e:
            self.status_message = f"Error saving config: {str(e)}"
            self.status_style = "error"

    def _cancel(self):
        """Cancel and close without saving."""
        if self.on_close:
            self.on_close(False)

    def _test_connection(self):
        """Test LLM connection with current settings."""
        try:
            from ultrawhisper.llm.llm_service import LLMService

            # Create temporary config for testing
            test_config = {
                "llm": {
                    "provider": self.provider_selector.get_provider(),
                    "model": self.provider_selector.get_model(),
                    "api_key": self.fields["llm.api_key"].get_value(),
                    "base_url": self.fields["llm.base_url"].get_value(),
                }
            }

            # Only test if API key is provided and not masked
            api_key = test_config["llm"]["api_key"]
            if not api_key or api_key.startswith("*"):
                self.status_message = "Enter API key to test connection"
                self.status_style = "warning"
                return

            llm_service = LLMService(test_config)
            if llm_service.check_availability():
                self.status_message = "✓ Connection successful"
                self.status_style = "success"
            else:
                self.status_message = "✗ Connection failed"
                self.status_style = "error"

        except Exception as e:
            self.status_message = f"Connection error: {str(e)}"
            self.status_style = "error"

    def get_key_bindings(self) -> KeyBindings:
        """Get key bindings for the settings component."""
        kb = KeyBindings()

        @kb.add("c-s")
        def _(event):
            """Save configuration."""
            self._save_config()

        return kb

    def get_style_dict(self) -> dict:
        """Get style dictionary for the settings component."""
        return {
            # ASCII Art styles (matching main screen)
            "ascii.primary": "#FFD700 bold",  # Bright gold for main text
            "ascii.secondary": "#FFA500 bold",  # Orange-gold for secondary text
            "ascii.border": "#FFAA00 bold",  # Amber-gold for borders
            "ascii.accent": "#FF8C00 bold",  # Dark orange for decorative elements
            "ascii.shadow": "#B8860B",  # Dark golden rod for shadows
            # Settings-specific styles
            "title": "#FFD700 bold",
            "label": "#888888",
            "info": "#00aa88",
            "success": "#00aa00 bold",
            "warning": "#ffaa00 bold",
            "error": "#ff4444 bold",
            "help": "#666666",
            "status": "#cccccc",
            "section.header": "#FFD700 bold",  # Golden section headers
            # Frame styling to match main screen
            "frame.border": "#FFAA00",  # Golden border like main screen
            "frame.title": "#FFD700 bold",  # Golden title like main screen
        }


# Keep the old interface for backward compatibility, but redirect to component
SettingsScreen = SettingsComponent

def show_settings_screen(config_manager: ConfigManager, on_close: Callable[[bool], None] = None):
    """Show the settings screen (deprecated - use SettingsComponent instead)."""
    screen = SettingsComponent(config_manager, on_close)
    # This function is now deprecated since we embed the component