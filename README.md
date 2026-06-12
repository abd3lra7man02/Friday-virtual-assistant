# Friday – Voice AI Assistant

A voice-activated personal assistant inspired by Tony Stark's FRIDAY. Combines push-to-talk voice input, Whisper STT, neural TTS, a LangGraph agent, and persistent vector memory — all running locally via Ollama.

## Architecture

```
voice.py ──► brain.py ──► Ollama (LLM: llama3 recommended)
  │  push-to-talk    │         │
  │  Whisper STT     │         └── nomic-embed-text (embeddings)
  │  edge-tts /      │
  │  pyttsx3 TTS     ├──► Chroma DB (long-term vector memory)
  │                  ├──► Tools: time, weather, calendar, Gmail, HA
  └──────────────────┘
```

`voice.py` handles all audio I/O. `brain.py` owns the agent, memory, and tools. `voice.py` imports from `brain.py` — they are integrated, not separate scripts.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally

## Quick Start

### 1. Pull required Ollama models

```bash
ollama pull llama3             # language model (recommended)
ollama pull nomic-embed-text   # embeddings for long-term memory
```

> **Low-resource alternative**: `ollama pull qwen3.5:0.8b` uses ~1 GB RAM but is less
> reliable with tool use. Set `MODEL_NAME=qwen3.5:0.8b` in your `.env` to use it.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your city, timezone, etc.
```

### 4. Run

**Voice mode (push-to-talk):**
```bash
python voice.py
```
Hold `F2` to speak, release to process. Friday gives a morning briefing on startup.

**Text mode:**
```bash
python brain.py
```

## Optional Features

### Neural TTS (high-quality voice, requires internet)

```bash
pip install edge-tts pygame
```
Falls back to offline `pyttsx3` automatically if unavailable or if there is no internet.
Run `python test_tts.py` to verify TTS is working before running the full assistant.

### Google Calendar & Gmail

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **Calendar API** and **Gmail API**
3. Create OAuth 2.0 credentials → download as `credentials.json` → place it in the project root
4. Run either script — it will open a browser for OAuth on first use

> `credentials.json` and `token.pickle` are in `.gitignore`. Never commit them.

### Home Assistant

Set `HA_URL` and `HA_TOKEN` in `.env`. The token is a Long-Lived Access Token from your HA profile page. Friday can then turn lights on/off and set thermostats by voice.

## Voice Commands

| What you say | What happens |
|---|---|
| Any question or request | Sent to the Friday agent |
| "Remember that X" / "Keep in mind X" | Stores X in Chroma long-term memory |
| "Exit" / "Goodbye" | Shuts down cleanly |

## Wake Word (optional)

Wake word is **disabled by default** — every utterance is processed. To enable it, set `USE_WAKE_WORD = True` in `voice.py`. Friday then only responds when you say "Friday" or "Hey Friday" first.

## Project Structure

```
├── voice.py          # Push-to-talk interface (STT + TTS + audio)
├── brain.py          # LangGraph agent (LLM + tools + Chroma memory)
├── requirements.txt  # All Python dependencies
├── .env.example      # Config template — copy to .env and fill in
├── test_tts.py       # Standalone TTS sanity check
├── .gitignore
└── friday_chroma_db/ # Auto-created on first run: persistent memory
```

## Security

- Never commit `.env` — it is in `.gitignore`
- `credentials.json` and `token.pickle` are also gitignored
- If you accidentally committed a secret, revoke it immediately and use
  [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) to purge the history
