# Friday Voice Assistant – TTS Setup

## Install Required Packages

```bash
pip install edge-tts pygame
```

## Voice Options

The script uses **en-US-AriaNeural** by default (professional American female voice). 

To change voices, edit `voice.py` and modify:
```python
NEURAL_VOICE = "en-US-AriaNeural"
```

### Available Neural Voices:
- `en-US-AriaNeural` – Professional, calm (recommended)
- `en-US-JennyNeural` – Friendly, energetic
- `en-US-AmberNeural` – Natural, conversational
- `en-US-AvaNeural` – Warm, approachable

## How It Works

1. **Primary**: Uses edge-tts for high-quality neural voices (requires internet)
2. **Fallback**: Automatically uses optimized pyttsx3 if edge-tts fails or dependencies missing
3. **Playback**: Uses pygame mixer for seamless audio playback

## Offline Mode

If you need purely offline TTS, the fallback pyttsx3 is always active and requires no internet. Simply don't install edge-tts/pygame.

## Troubleshooting

If you see "⚠️ Neural TTS failed:", verify:
- Internet connection is active
- `edge-tts` and `pygame` are installed: `pip list | grep edge-tts`
- Ollama is still running separately

The assistant will automatically fall back to pyttsx3 if anything fails.
