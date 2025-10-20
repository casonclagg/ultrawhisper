# UltraWhisper

**Open-source, context-aware voice transcription for Linux**

An open-source alternative to [SuperWhisper](https://superwhisper.com/) (Mac-only), combining OpenAI's Whisper speech-to-text with LLM-powered intelligence for smart, accurate transcriptions that adapt to your workflow.

![UltraWhisper TUI](docs/ultrawhisper.png)

## What Makes UltraWhisper Different?

UltraWhisper goes beyond basic speech-to-text by understanding **what you're working on** and adapting its transcription accordingly. Whether you're coding in VS Code, browsing GitHub, or working in a terminal, it delivers transcriptions that fit seamlessly into your context.

## Key Features

**Context-Aware Transcription**
- Automatically detects your active application (VS Code, Chrome, terminal, etc.)
- Adapts transcription to preserve code syntax, technical terms, and domain-specific language

**LLM-Powered Correction**
- Cleans up Whisper transcription using GPT-4, Claude, or local models
- Applies application-specific prompts for better accuracy
- Gracefully degrades to raw Whisper output if LLM is unavailable

**Multi-Provider LLM Support**
- OpenAI, Anthropic, Local Models (OpenAI-compatible)

**Flexible Input Methods**
- Double-tap: Quickly tap a key twice to toggle recording
- Push-to-talk: Hold to record, release to transcribe

**Beautiful Terminal Interface**
- Interactive TUI built with prompt-toolkit
- Real-time status display showing LLM connection, context, and system state
- Live logs and configuration visibility

**Chat Mode (Conversational AI)**
- Voice conversations with your AI assistant
- Maintains conversation history across questions
- Context-aware responses based on your active application
- TTS support for spoken responses
- MCP (Model Context Protocol) integration for extended capabilities
- Web search enabled by default

**Privacy-First**
- Use local LLMs for complete offline operation
- No data leaves your machine when using local models

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/casonclagg/ultrawhisper.git
cd ultrawhisper

# Install dependencies
uv sync

# Run interactive setup to set API keys etc
uv run ultrawhisper setup
```

### Basic Usage

```bash
# Run it!
uv run ultrawhisper
```

### Configuration

Configuration is stored at `~/.config/ultrawhisper/config.yml`. See [config.example.yml](config.example.yml) for a complete example with all options.

## Features in Detail

### Context-Aware Prompts

UltraWhisper dynamically builds LLM prompts by combining:
- Base prompt from your configuration
- Application-specific prompts (VS Code, Chrome, terminals, etc.)
- Pattern matching against window titles (GitHub, Stack Overflow, etc.)

This ensures your transcriptions are corrected appropriately for your current context.

### Mode Switching

Switch between **Transcription Mode** and **Question Mode (soon to be called Chat Mode)**:

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
uv run ultrawhisper
```

## Architecture

UltraWhisper uses an **orchestrator pattern** where `TranscriptionApp` coordinates:
1. Audio recording via configurable backends
2. Whisper transcription (local or API)
3. Context detection from active window
4. LLM correction with context-aware prompts
5. Text output to clipboard or active window

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
