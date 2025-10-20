#!/usr/bin/env python3
"""
Pydantic models for UltraWhisper configuration.

Provides strong typing and validation for all configuration settings.
"""

from typing import Dict, Any, Optional, Union, Literal, List
from pydantic import BaseModel, Field, validator
from pathlib import Path


class NotificationsConfig(BaseModel):
    """Notification settings configuration."""
    visual_enabled: bool = Field(default=False, description="Enable visual notifications")
    audio_enabled: bool = Field(default=True, description="Enable audio notifications")


class PushToTalkConfig(BaseModel):
    """Push-to-talk settings configuration."""
    enabled: bool = Field(default=True, description="Enable push-to-talk mode")
    key: str = Field(default="Key.cmd", description="Key for push-to-talk mode (transcription)")


class QuestionModePushToTalkConfig(BaseModel):
    """Question mode push-to-talk settings configuration."""
    enabled: bool = Field(default=True, description="Enable question mode push-to-talk")
    key: str = Field(default="Key.alt", description="Key for question mode push-to-talk")


class HotkeyConfig(BaseModel):
    """Hotkey settings configuration."""
    key: str = Field(default="cmd", description="Hotkey key")
    modifier: str = Field(default="Key.cmd", description="Hotkey modifier")


class AudioConfig(BaseModel):
    """Audio recording settings configuration."""
    sample_rate: int = Field(default=16000, description="Audio sample rate", ge=8000, le=48000)
    channels: int = Field(default=1, description="Number of audio channels", ge=1, le=2)
    dtype: str = Field(default="float32", description="Audio data type")


class WhisperConfig(BaseModel):
    """Whisper transcription settings configuration."""
    model_name: Literal["tiny", "base", "small", "medium", "large"] = Field(
        default="small", description="Whisper model size"
    )
    language: str = Field(default="en", description="Language for transcription")


class MCPServerConfig(BaseModel):
    """MCP (Model Context Protocol) Server configuration."""
    name: str = Field(description="Human-readable name for the MCP server")
    command: str = Field(description="Command to execute for the MCP server")
    args: List[str] = Field(default_factory=list, description="Arguments for the MCP server command")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables for the MCP server")


class LLMConfig(BaseModel):
    """LLM (Large Language Model) settings configuration."""
    provider: Literal["openai", "openai-compatible", "anthropic"] = Field(
        default="openai", description="LLM provider"
    )
    model: str = Field(default="gpt-4o", description="LLM model name")
    api_key: str = Field(default="", description="API key for authentication")
    base_url: str = Field(default="https://api.openai.com/v1", description="Base URL for LLM API")
    base_prompt: str = Field(
        default="You are correcting speech-to-text transcription errors. Fix grammar, spelling, and misheard words while preserving the original meaning. DO not mention anything about the transcript, only respond with corrected transcript.",
        description="Base system prompt for text correction"
    )
    skip_if_unavailable: bool = Field(
        default=True, description="Continue without LLM correction if service is unavailable"
    )
    mcp_servers: List[MCPServerConfig] = Field(
        default_factory=list, description="MCP servers to connect to for agent tools"
    )


class TranscriptionModeConfig(BaseModel):
    """Transcription mode settings configuration."""
    trigger_phrases: List[str] = Field(
        default_factory=lambda: ["transcription mode", "typing mode", "dictation mode"],
        description="Phrases that switch to this mode"
    )


class QuestionModeConfig(BaseModel):
    """Question mode settings configuration."""
    trigger_phrases: List[str] = Field(
        default_factory=lambda: ["question mode", "ask mode", "chat mode"],
        description="Phrases that switch to this mode"
    )
    context_prompts: Dict[str, str] = Field(
        default_factory=lambda: {
            "default": "You are a helpful AI assistant. Provide concise, accurate answers to user questions. Keep responses brief unless more detail is specifically requested."
        },
        description="Context-aware prompts for different applications"
    )
    output_response: bool = Field(default=False, description="Whether to type/paste AI response")
    tts_enabled: bool = Field(default=False, description="Whether to speak the response")
    conversation_history: int = Field(
        default=30, description="Number of turns to remember", ge=1, le=100
    )


class ModesConfig(BaseModel):
    """Mode configuration settings."""
    default: Literal["transcription", "question"] = Field(
        default="transcription", description="Default mode on startup"
    )
    transcription: TranscriptionModeConfig = Field(
        default_factory=TranscriptionModeConfig, description="Transcription mode settings"
    )
    question: QuestionModeConfig = Field(
        default_factory=QuestionModeConfig, description="Question mode settings"
    )


class SystemTTSConfig(BaseModel):
    """System TTS settings configuration."""
    voice: Optional[str] = Field(default=None, description="System voice to use")
    rate: int = Field(default=200, description="Words per minute", ge=50, le=500)
    volume: float = Field(default=1.0, description="Volume level", ge=0.0, le=1.0)


class TTSConfig(BaseModel):
    """TTS (Text-to-Speech) configuration."""
    provider: Literal["system", "openai", "elevenlabs"] = Field(
        default="system", description="TTS provider"
    )
    system: SystemTTSConfig = Field(
        default_factory=SystemTTSConfig, description="System TTS settings"
    )


class OutputConfig(BaseModel):
    """Output settings configuration."""
    typing_delay: float = Field(default=0.01, description="Delay between typing each character", ge=0.0)
    paste_mode: bool = Field(default=False, description="Use clipboard paste instead of simulated typing")


class ContextPromptsConfig(BaseModel):
    """Context prompts configuration for transcription mode."""
    applications: Dict[str, str] = Field(
        default_factory=dict, description="Application-specific prompts"
    )
    patterns: list[Dict[str, str]] = Field(
        default_factory=list, description="Pattern-based prompts"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="info", description="Logging level")
    log_context: bool = Field(default=False, description="Enable context detection logging")
    log_prompts: bool = Field(default=False, description="Enable prompt construction logging")
    log_corrections: bool = Field(default=False, description="Enable transcription correction logging")
    redact_content: bool = Field(default=False, description="Redact sensitive content in logs")
    file: Optional[str] = Field(default=None, description="Log file path")


class UltraWhisperConfig(BaseModel):
    """Main UltraWhisper configuration model."""

    # Core settings
    notifications: NotificationsConfig = Field(
        default_factory=NotificationsConfig, description="Notification settings"
    )
    use_double_tap: bool = Field(default=False, description="Enable double tap activation")
    push_to_talk: PushToTalkConfig = Field(
        default_factory=PushToTalkConfig, description="Push-to-talk settings for transcription mode"
    )
    question_mode_push_to_talk: QuestionModePushToTalkConfig = Field(
        default_factory=QuestionModePushToTalkConfig, description="Push-to-talk settings for question mode"
    )
    hotkey: HotkeyConfig = Field(
        default_factory=HotkeyConfig, description="Hotkey settings"
    )

    # Audio and transcription
    audio: AudioConfig = Field(
        default_factory=AudioConfig, description="Audio recording settings"
    )
    whisper: WhisperConfig = Field(
        default_factory=WhisperConfig, description="Whisper transcription settings"
    )

    # LLM and modes
    llm: LLMConfig = Field(
        default_factory=LLMConfig, description="LLM settings"
    )
    modes: ModesConfig = Field(
        default_factory=ModesConfig, description="Mode configuration"
    )

    # TTS and output
    tts: TTSConfig = Field(
        default_factory=TTSConfig, description="TTS configuration"
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig, description="Output settings"
    )

    # Context and logging
    context_detection: bool = Field(default=True, description="Enable context detection")
    context_prompts: ContextPromptsConfig = Field(
        default_factory=ContextPromptsConfig, description="Context prompts for transcription mode"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig, description="Logging configuration"
    )

    @validator('llm')
    def validate_llm_config(cls, v):
        """Validate LLM configuration."""
        if v.provider in ["openai", "anthropic"] and not v.api_key:
            # Don't require API key during validation - it might be set via environment or interactively
            pass
        return v

    def model_dump_yaml_compatible(self) -> Dict[str, Any]:
        """
        Export config in a format compatible with existing YAML structure.

        Returns:
            Dictionary that can be saved as YAML
        """
        return self.model_dump(exclude_none=True, by_alias=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UltraWhisperConfig":
        """
        Create config from dictionary (loaded from YAML).

        Args:
            data: Configuration dictionary

        Returns:
            Validated UltraWhisperConfig instance
        """
        return cls(**data)