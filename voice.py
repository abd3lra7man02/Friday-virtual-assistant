# voice.py – Friday Assistant (Push-to-Talk + Neural Voice)
import asyncio
import queue
import re
import os
import tempfile

import numpy as np
import sounddevice as sd
import whisper
import pyttsx3
import keyboard

from brain import ask_friday, store_memory, check_connection, morning_briefing

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

# -------------------------------------------------------------------
# TTS – edge-tts (neural) with pyttsx3 fallback
# -------------------------------------------------------------------
NEURAL_VOICE   = "en-US-AriaNeural"
TEMP_AUDIO_DIR = tempfile.gettempdir()
_pygame_initialized = False


async def _speak_neural(text: str) -> bool:
    """Generate and play high-quality neural voice via edge-tts."""
    global _pygame_initialized
    if not HAS_EDGE_TTS or not HAS_PYGAME:
        return False
    try:
        communicate = edge_tts.Communicate(text, voice=NEURAL_VOICE, rate="+10%")
        audio_file = os.path.join(
            TEMP_AUDIO_DIR,
            f"friday_tts_{id(asyncio.current_task())}.mp3",
        )
        await communicate.save(audio_file)

        if not _pygame_initialized:
            pygame.mixer.init()
            _pygame_initialized = True

        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)

        try:
            os.remove(audio_file)
        except OSError:
            pass
        return True
    except Exception as e:
        print(f"⚠️ Neural TTS failed: {e}")
        return False


def _speak_fallback(text: str) -> None:
    """Fallback: pyttsx3 with female voice selection."""
    if not text or not text.strip():
        return
    try:
        engine = pyttsx3.init()
        try:
            voices = engine.getProperty("voices")
            female = next(
                (v.id for v in voices
                 if "female" in v.name.lower() or "zira" in v.name.lower()),
                None,
            )
            if female:
                engine.setProperty("voice", female)
            engine.setProperty("rate", 180)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
        finally:
            engine.stop()
    except Exception as e:
        print(f"⚠️ Fallback TTS error: {e}")


async def text_to_speech(text: str) -> None:
    """Try neural TTS first; fall back to pyttsx3."""
    try:
        if HAS_EDGE_TTS and HAS_PYGAME:
            if await _speak_neural(text):
                return
        await asyncio.to_thread(_speak_fallback, text)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"⚠️ Text-to-speech failed: {e}")


# -------------------------------------------------------------------
# Audio – Push-to-Talk
# -------------------------------------------------------------------
SAMPLE_RATE = 16_000
BLOCKSIZE   = 1_000
_audio_q: queue.Queue = queue.Queue()


def _audio_callback(indata, frames, time, status):
    _audio_q.put(indata.copy())


def _record_sync(key: str = "F2") -> np.ndarray:
    """Blocking: record audio while key is held. Runs in a thread."""
    global _audio_q
    _audio_q = queue.Queue()        # reset stale audio between recordings
    print(f"🎤 Hold [{key}] to speak. Release to stop.")
    keyboard.wait(key, suppress=True)
    print("🔴 RECORDING… (release key when done)")
    chunks = []
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1,
            callback=_audio_callback, blocksize=BLOCKSIZE,
        ):
            while keyboard.is_pressed(key):
                try:
                    chunks.append(_audio_q.get(timeout=0.05))
                except queue.Empty:
                    pass
    except Exception as e:
        print(f"⚠️ Recording error: {e}")
    print("⏹️ Recording stopped.")
    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks, axis=0).flatten().astype(np.float32)


async def record_while_key_held(key: str = "F2") -> np.ndarray:
    """Async wrapper around the blocking recorder."""
    return await asyncio.to_thread(_record_sync, key)


# -------------------------------------------------------------------
# STT – Whisper
# -------------------------------------------------------------------
_stt_model = None


def _load_stt_model() -> bool:
    """Lazy-load Whisper on first use to avoid blocking startup."""
    global _stt_model
    if _stt_model is not None:
        return True
    try:
        print("Loading Whisper model…")
        _stt_model = whisper.load_model("base")
        print("✓ Whisper model loaded.")
        return True
    except Exception as e:
        print(f"❌ Failed to load Whisper model: {e}")
        return False


def transcribe(audio: np.ndarray) -> str:
    if len(audio) == 0:
        return ""
    if _stt_model is None and not _load_stt_model():
        return ""
    try:
        result = _stt_model.transcribe(audio, fp16=False, language="en")
        return result["text"].strip()
    except RuntimeError as e:
        print(f"❌ Hardware/Memory error during transcription: {e}")
        return ""
    except Exception as e:
        print(f"⚠️ Unexpected transcription error: {e}")
        return ""


# -------------------------------------------------------------------
# Memory learning detection
# -------------------------------------------------------------------
_LEARNING_PHRASES = [
    "always remember",
    "remember this",
    "remember that",
    "keep in mind",
    "new rule",
    "note that",
]


def _is_learning_command(text: str) -> bool:
    lower = text.lower()
    if any(p in lower for p in _LEARNING_PHRASES):
        return True
    if "remember" in lower and len(text) > 15:
        return True
    return False


def _extract_memory_content(text: str) -> str:
    lower = text.lower()
    # Longer phrases are checked first to avoid partial matches on "remember"
    all_phrases = _LEARNING_PHRASES + ["remember"]
    for phrase in all_phrases:
        idx = lower.find(phrase)
        if idx != -1:
            content = text[idx + len(phrase):].strip()
            content = re.sub(r"^[.,!?;:\s]+", "", content)
            if content:
                return content
    return text.strip()


# -------------------------------------------------------------------
# Optional wake word (disabled by default)
# -------------------------------------------------------------------
USE_WAKE_WORD = False
# Longer strings first so "hey friday" matches before "friday"
_WAKE_WORDS   = ["hey friday", "friday", "jarvis"]


def _has_wake_word(text: str) -> bool:
    lower = text.lower()
    return any(ww in lower for ww in _WAKE_WORDS)


def _strip_wake_word(text: str) -> str:
    lower = text.lower()
    for ww in _WAKE_WORDS:
        pos = lower.find(ww)
        if pos != -1:
            return re.sub(r"^[.,!?;:\s]+", "", text[pos + len(ww):]).strip()
    return ""


# -------------------------------------------------------------------
# Main loop
# -------------------------------------------------------------------
async def main_loop():
    print("=" * 50)
    print("Friday Assistant – Push-to-Talk mode")
    print("Hold [F2] to speak, release to process.")

    if not _load_stt_model():
        print("❌ Cannot start without Whisper model.")
        return

    if not check_connection():
        print("⚠️  Ollama not detected — will retry on first query.")

    print("Wake word:", "REQUIRED ('Friday')" if USE_WAKE_WORD else "DISABLED")
    print("Say 'exit' or 'goodbye' to quit.")

    briefing = morning_briefing()
    print(f"\nFriday: {briefing}")
    await text_to_speech(briefing)

    print("=" * 50 + "\n")

    while True:
        try:
            audio     = await record_while_key_held("F2")
            user_text = transcribe(audio)
            print(f"You said: {user_text}")

            if not user_text:
                print("⏩ Nothing heard.\n")
                continue

            if user_text.lower().strip() in {"exit", "quit", "shutdown", "goodbye"}:
                await text_to_speech("Shutting down. Goodbye, Sir.")
                break

            if _is_learning_command(user_text):
                entry = _extract_memory_content(user_text)
                store_memory(entry)
                await text_to_speech("Pattern logged, Sir.")
                print(f"📝 Stored: {entry}\n")
                continue

            if USE_WAKE_WORD:
                if _has_wake_word(user_text):
                    query = _strip_wake_word(user_text)
                    if not query:
                        await text_to_speech("Yes, sir?")
                        continue
                else:
                    print("⏩ No wake word detected, ignoring.\n")
                    continue
            else:
                query = user_text

            print(f"🤖 Processing: '{query}'")
            reply = await asyncio.to_thread(ask_friday, query)
            print(f"Friday: {reply}")
            await text_to_speech(reply)
            print()

        except KeyboardInterrupt:
            print("\n\nShutting down…")
            break
        except Exception as e:
            print(f"⚠️ Error in main loop: {e}\n")


if __name__ == "__main__":
    asyncio.run(main_loop())
