# UltraWhisper

Context-aware voice transcription that combines OpenAI's Whisper speech-to-text with LLM-powered intelligence for smart, accurate transcriptions that adapt to your workflow.

## What Makes UltraWhisper Different?

UltraWhisper goes beyond basic speech-to-text by understanding **what you're working on** and adapting its transcription accordingly. 
Whether you're coding in VS Code, browsing GitHub, or working in a terminal, it delivers transcriptions that fit seamlessly into your context.

### Key Features

#### 🎯 Context-Aware Transcription
Automatically detects your active application and adapts transcription:
- **VS Code**: Preserves code syntax, variable names, and technical terms
- **Web Browser**: Recognizes GitHub, Stack Overflow, and formats accordingly
- **Terminal**: Understands shell commands and technical language
- **Auto-detection**: Uses `xdotool` and window properties for smart context detection

#### 🧠 LLM-Powered Correction
Raw Whisper transcription gets cleaned up by AI that understands context:
- Fixes Whisper's mistakes using GPT-4, Claude, or local models
- Applies application-specific prompts for better accuracy
- Maintains technical terminology and code snippets correctly
- Gracefully degrades to raw Whisper if LLM is unavailable

#### 🔌 Multi-Provider LLM Support
Choose your AI brain:
- **OpenAI**: GPT-4o, GPT-4.1, and other official models
- **Anthropic**: Claude 3.5 Sonnet and other Claude models
- **Local/Self-hosted**: LMStudio, Ollama, or any OpenAI-compatible server
- **Auto-detection**: Setup wizard finds available providers automatically

#### ⌨️ Flexible Hotkey System
Control transcription your way:
- **Double-tap**: Tap a key twice quickly to toggle recording
- **Push-to-talk**: Hold to record, release to transcribe
- **Custom combinations**: Use any key combo that works for you
- **Conflict detection**: Warns about window manager conflicts

#### 🖥️ Sick TUI
Its in style rn.
- **TUI**: Beautiful terminal interface for interactive use

#### 💬 Question Mode (Conversational AI)
Switch to question mode for conversational AI assistance:
- **Voice conversations**: Ask questions and get spoken responses
- **Context-aware**: Adapts to your current application
- **Conversation history**: Maintains context across multiple questions
- **TTS support**: Speaks responses using system TTS or cloud providers
- **MCP Integration**: Supports Model Context Protocol for extended capabilities

#### 🔐 Privacy-First Architecture
Your data stays yours:
- **Content redaction**: Privacy mode hides sensitive content from logs
- **Local processing**: Use local LLMs for complete privacy
- **Configurable logging**: Control what gets logged and where
- **No telemetry**: Zero tracking or data collection

#### ⚙️ Smart Configuration
Easy setup, powerful options:
- **Interactive wizard**: `ultrawhisper setup` guides you through configuration
- **XDG-compliant**: Config lives in `~/.config/ultrawhisper/`
- **YAML schema**: Human-readable, version-controllable settings
- **Graceful fallbacks**: Missing config triggers setup automatically

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/casonclagg/ultrawhisper.git
cd ultrawhisper

# Install dependencies
uv sync

# Run interactive setup
ultrawhisper setup
```

### Basic Usage

```bash
# Run with saved config
ultrawhisper

# Launch beautiful TUI
ultrawhisper tui

# One-shot transcription
ultrawhisper --once

# Enable verbose logging
ultrawhisper --verbose

# Log prompts for debugging
ultrawhisper --log-prompts
```

### Configuration

Configuration is stored at `~/.config/ultrawhisper/config.yml`. See [config.example.yml](config.example.yml) for a complete example with all options.

**Minimal configuration:**

```yaml
# Whisper settings
whisper:
  model_name: tiny  # tiny, base, small, medium, large-v3
  language: en

# LLM settings (optional)
llm:
  provider: openai
  model: gpt-4o
  api_key: your-api-key-here
  skip_if_unavailable: true

# Hotkey settings
push_to_talk:
  enabled: true
  key: Key.cmd
```

## Features in Detail

### Context-Aware Prompts

UltraWhisper dynamically builds LLM prompts by combining:
- Base prompt from your configuration
- Application-specific prompts (VS Code, Chrome, terminals, etc.)
- Pattern matching against window titles (GitHub, Stack Overflow, etc.)

This ensures your transcriptions are corrected appropriately for your current context.

### Mode Switching

Switch between **Transcription Mode** and **Question Mode** by saying:
- "transcription mode" - for dictation and typing
- "question mode" - for conversational AI assistance

In question mode, you can have voice conversations with your AI assistant, complete with:
- Context-aware responses based on active application
- Conversation history (maintains context across questions)
- Text-to-speech responses
- MCP server integration for extended capabilities

### Graceful Degradation

Every component handles failure elegantly:
- No `xdotool`? Falls back to basic context detection
- LLM unavailable? Uses raw Whisper transcription
- Audio issues? Logs errors without crashing
- Missing config? Launches interactive setup

## System Requirements

- **Python**: 3.10 or higher
- **Operating System**: Linux (X11) for full context detection
- **Optional Dependencies**:
  - `xdotool` - For advanced context detection
  - `x11-utils` - For window property detection
  - `espeak` or `festival` - For system TTS (question mode)

### Installing System Dependencies

```bash
# Ubuntu/Debian
sudo apt install xdotool x11-utils espeak

# Arch Linux
sudo pacman -S xdotool xorg-xprop espeak

# Fedora
sudo dnf install xdotool xorg-x11-utils espeak
```

## Development

```bash
# Code formatting
uv run black src/

# Type checking
uv run mypy src/

# Linting
uv run flake8 src/

# Build package
uv build

# Run from source
uv run ultrawhisper tui
```

## Architecture

UltraWhisper uses an **orchestrator pattern** where `TranscriptionApp` coordinates:
1. Audio recording via configurable backends
2. Whisper transcription (local or API)
3. Context detection from active window
4. LLM correction with context-aware prompts
5. Text output to clipboard or active window

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

## License

MIT License - See [LICENSE](LICENSE) for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

Cason Clagg - [GitHub](https://github.com/casonclagg)

## Acknowledgments

- Built with [OpenAI Whisper](https://github.com/openai/whisper)
- Uses [faster-whisper](https://github.com/guillaumekln/faster-whisper) for optimized inference
- Powered by [OpenAI](https://openai.com) and [Anthropic](https://anthropic.com) LLMs
- Terminal UI built with [prompt-toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)
