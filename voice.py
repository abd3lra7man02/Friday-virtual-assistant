# voice.py – Friday Assistant (Push‑to‑Talk + Neural American Female Voice + Ollama)
import asyncio
import queue
import numpy as np
import sounddevice as sd
import whisper
import requests
import re
import pyttsx3
import keyboard
import threading
import os
import tempfile

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
NEURAL_VOICE = "en-US-AriaNeural"
TEMP_AUDIO_DIR = tempfile.gettempdir()
pygame_initialized = False

async def speak_neural(text):
    """Generate and play high-quality neural voice using edge-tts."""
    global pygame_initialized
    if not HAS_EDGE_TTS or not HAS_PYGAME:
        return False

    try:
        communicate = edge_tts.Communicate(text, voice=NEURAL_VOICE, rate="+10%")
        audio_file = os.path.join(TEMP_AUDIO_DIR, f"friday_tts_{id(asyncio.current_task())}.mp3")

        await communicate.save(audio_file)

        if not pygame_initialized:
            pygame.mixer.init()
            pygame_initialized = True

        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)

        try:
            os.remove(audio_file)
        except:
            pass

        return True
    except Exception as e:
        print(f"⚠️ Neural TTS failed: {e}")
        return False

def speak_fallback(text):
    """Fallback to optimized pyttsx3 with female voice."""
    if not text or not text.strip():
        return
    try:
        engine = pyttsx3.init()
        try:
            voices = engine.getProperty('voices')
            female_voice = None
            for voice in voices:
                if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                    female_voice = voice.id
                    break
            if female_voice:
                engine.setProperty('voice', female_voice)

            engine.setProperty('rate', 180)
            engine.setProperty('volume', 1.0)
            engine.say(text)
            engine.runAndWait()
        finally:
            engine.stop()
    except Exception as e:
        print(f"⚠️ Fallback TTS error: {e}")

async def text_to_speech(text):
    """Try neural TTS first, fall back to pyttsx3."""
    try:
        if HAS_EDGE_TTS and HAS_PYGAME:
            success = await speak_neural(text)
            if success:
                return

        await asyncio.to_thread(speak_fallback, text)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"⚠️ Text-to-speech failed: {e}")

# -------------------------------------------------------------------
# Audio settings (Push‑to‑Talk)
# -------------------------------------------------------------------
SAMPLE_RATE = 16000
BLOCKSIZE = 1000

audio_q = queue.Queue()

def audio_callback(indata, frames, time, status):
    audio_q.put(indata.copy())

def record_while_key_held_sync(key='F2'):
    """Synchronous version of recording (runs in a thread)."""
    global audio_q
    audio_q = queue.Queue()
    print(f"🎤 Hold [{key}] to speak. Release to stop.")
    keyboard.wait(key, suppress=True)
    print("🔴 RECORDING... (release the key when done)")
    chunks = []
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback, blocksize=BLOCKSIZE):
            while keyboard.is_pressed(key):
                try:
                    chunk = audio_q.get(timeout=0.05)
                    chunks.append(chunk)
                except queue.Empty:
                    pass
    except Exception as e:
        print(f"⚠️ Recording error: {e}")
    print("⏹️ Recording stopped.")
    if not chunks:
        return np.array([], dtype=np.float32)
    audio = np.concatenate(chunks, axis=0).flatten().astype(np.float32)
    return audio

async def record_while_key_held(key='F2'):
    """Asynchronous wrapper for recording (non‑blocking)."""
    return await asyncio.to_thread(record_while_key_held_sync, key)

# -------------------------------------------------------------------
# STT – Whisper (English forced)
# -------------------------------------------------------------------
stt_model = None

def load_stt_model():
    """Lazy load Whisper model with error handling."""
    global stt_model
    if stt_model is not None:
        return True
    try:
        print("Loading Whisper model...")
        stt_model = whisper.load_model("base")
        print("✓ Whisper model loaded.")
        return True
    except Exception as e:
        print(f"❌ Failed to load Whisper model: {e}")
        return False

def transcribe(audio):
    """Transcribe audio with timeout."""
    if len(audio) == 0:
        return ""
    if stt_model is None:
        if not load_stt_model():
            return ""
    try:
        result = stt_model.transcribe(audio, fp16=False, language="en")
        return result["text"].strip()
    except Exception as e:
        print(f"⚠️ Transcription error: {e}")
        return ""

# -------------------------------------------------------------------
# Brain – Ollama with advanced evaluation and memory system
# -------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3.5:0.8b"
MEMORY_FILE = "friday_memory.txt"
ollama_available = None

ADVANCED_FRIDAY_PROMPT = """You are FRIDAY, an evolving analytical AI. Your user operates in software engineering and cybersecurity. You communicate via voice TTS.

CORE DIRECTIVES:
- NO VISUAL FORMATTING: Never use markdown, asterisks, or code blocks. Output plain, spoken text only.
- RADICAL BREVITY: Keep evaluations under 3 sentences.

EVALUATION PROTOCOL:
When presented with a system state, code logic, or security scenario, execute this sequence:
1. Identify the core pattern or vulnerability.
2. State the operational risk or efficiency flaw.
3. Recommend the optimal action.

LEARNING DIRECTIVE:
If the user corrects you or tells you to remember a preference, acknowledge and apply it immediately."""

def check_ollama_connection():
    """Verify Ollama is running."""
    global ollama_available
    if ollama_available is not None:
        return ollama_available

    try:
        response = requests.get(OLLAMA_URL.replace("/api/chat", ""), timeout=2)
        ollama_available = True
        return True
    except:
        ollama_available = False
        return False

def read_memory():
    """Read established patterns from memory file."""
    try:
        with open(MEMORY_FILE, 'r') as f:
            content = f.read().strip()
            return content if content else ""
    except FileNotFoundError:
        return ""

def write_memory(entry):
    """Append a new pattern to memory file."""
    try:
        with open(MEMORY_FILE, 'a') as f:
            f.write(entry + "\n")
    except Exception as e:
        print(f"⚠️ Memory write error: {e}")

def ask_ollama(prompt):
    """Query Ollama with memory context."""
    if not check_ollama_connection():
        print("❌ Ollama not responding. Is it running on localhost:11434?")
        return "My brain is not available. Please ensure Ollama is running."

    try:
        memory = read_memory()
        system_prompt = ADVANCED_FRIDAY_PROMPT
        if memory:
            system_prompt += f"\n\nESTABLISHED PATTERNS & MEMORY:\n{memory}"

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "keep_alive": -1,
                "stream": False,
                "options": {"num_predict": 50, "temperature": 0.3}
            },
            timeout=30
        )
        response.raise_for_status()
        reply = response.json()["message"]["content"].strip()
        if not reply:
            return "I didn't understand. Could you rephrase?"
        return reply
    except requests.exceptions.Timeout:
        return "Response timeout. Model may be processing. Try again."
    except requests.exceptions.ConnectionError:
        global ollama_available
        ollama_available = False
        return "Connection lost. Is Ollama still running?"
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return "Sorry, my brain encountered an error."

def detect_learning_command(text):
    """Check if user is providing a memory instruction."""
    learning_phrases = ["remember this", "keep in mind", "new rule", "remember that", "note that"]
    text_lower = text.lower()
    for phrase in learning_phrases:
        if phrase in text_lower:
            return True
    if "remember" in text_lower and len(text) > 15:
        return True
    return False

def extract_memory_content(text):
    """Extract the instruction to remember from user text."""
    learning_phrases = ["remember this", "keep in mind", "new rule", "remember that", "note that", "remember"]
    text_lower = text.lower()

    for phrase in learning_phrases:
        idx = text_lower.find(phrase)
        if idx != -1:
            content = text[idx + len(phrase):].strip()
            content = re.sub(r'^[.,!?;:\s]+', '', content)
            if content:
                return content

    return text.strip()

# -------------------------------------------------------------------
# Optional wake word (disabled by default)
# -------------------------------------------------------------------
USE_WAKE_WORD = False

def contains_wake_word(text):
    text_lower = text.lower()
    return any(ww in text_lower for ww in ["friday", "hey friday", "jarvis"])

def extract_command_after_wake_word(text):
    text_lower = text.lower()
    wake_words = ["friday", "hey friday", "jarvis"]
    earliest_pos = len(text)
    ww_len = 0
    for ww in wake_words:
        pos = text_lower.find(ww)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
            ww_len = len(ww)
    if earliest_pos == len(text):
        return ""
    after = text[earliest_pos + ww_len:]
    after = re.sub(r'^[.,!?;:\s]+', '', after)
    return after.strip()

# -------------------------------------------------------------------
# Main loop with Push‑to‑Talk (non‑blocking asyncio)
# -------------------------------------------------------------------
async def main_loop():
    print("=" * 50)
    print("Friday Assistant – Push‑to‑Talk mode")
    print("Hold [F2] to speak, release to process.")

    if not load_stt_model():
        print("❌ Cannot start without Whisper model.")
        return

    if not check_ollama_connection():
        print("⚠️ Warning: Ollama not detected. Will retry on first query.")

    if USE_WAKE_WORD:
        print("Wake word 'Friday' is REQUIRED before your command.")
    else:
        print("Wake word DISABLED – everything you say will be processed.")
    print("Say 'exit' or 'goodbye' to quit.\n")
    print("=" * 50 + "\n")

    while True:
        try:
            audio = await record_while_key_held('F2')
            user_text = transcribe(audio)
            print(f"You said: {user_text}")

            if not user_text:
                print("⏩ Nothing heard or could not understand.\n")
                continue

            if user_text.lower() in ["exit", "quit", "shutdown", "goodbye"]:
                await text_to_speech("Shutting down. Goodbye, Sir.")
                break

            if detect_learning_command(user_text):
                memory_entry = extract_memory_content(user_text)
                write_memory(memory_entry)
                await text_to_speech("Pattern logged, Sir.")
                print(f"📝 Stored: {memory_entry}\n")
                continue

            if USE_WAKE_WORD:
                if contains_wake_word(user_text):
                    clean_query = extract_command_after_wake_word(user_text)
                    if not clean_query:
                        await text_to_speech("Yes, sir?")
                        continue
                    print(f"🤖 Processing: '{clean_query}'")
                    reply = ask_ollama(clean_query)
                else:
                    print("⏩ No wake word detected, ignoring.\n")
                    continue
            else:
                print(f"🤖 Processing: '{user_text}'")
                reply = ask_ollama(user_text)

            print(f"Friday: {reply}")
            await text_to_speech(reply)
            print()
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            break
        except Exception as e:
            print(f"⚠️ Error in main loop: {e}")
            print()

if __name__ == "__main__":
    asyncio.run(main_loop())