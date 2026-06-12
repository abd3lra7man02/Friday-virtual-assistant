# Bug Fixes – Friday Voice Assistant

---

## Session 1 Fixes

### 1. pygame.mixer multiple init/quit (CRITICAL)
- **Problem**: `pygame.mixer.init()` called on every TTS, then `pygame.mixer.quit()` after playback. Mixer would be dead after first call.
- **Fix**: Initialize mixer once with global flag `_pygame_initialized`, never call quit.

### 2. Whisper model blocking startup
- **Problem**: `whisper.load_model("base")` called at module level, blocks startup for 10+ seconds.
- **Fix**: Lazy-load with `_load_stt_model()` on first transcription, with user feedback.

### 3. Audio queue contamination
- **Problem**: Global `_audio_q` never cleared between recordings, accumulates stale chunks.
- **Fix**: Reset queue at the start of each `_record_sync` call.

### 4. TTS file path race condition
- **Problem**: All concurrent TTS calls wrote to the same temp file `friday_tts.mp3`.
- **Fix**: Unique filename per asyncio task: `friday_tts_{id(asyncio.current_task())}.mp3`.

### 5. pyttsx3 resource leak
- **Problem**: `engine.stop()` not guaranteed to run if an exception occurred.
- **Fix**: Wrap in `try/finally` to ensure cleanup.

### 6. No Ollama connection validation
- **Problem**: Script started without checking if Ollama was reachable, failed on first query.
- **Fix**: `check_connection()` with cached result; warning shown on startup.

### 7. Memory extraction edge cases
- **Problem**: Short phrase "remember" matched before longer "remember this", returning wrong content.
- **Fix**: Longer phrases checked first; extracted content validated non-empty.

### 8. No transcription error handling
- **Problem**: `transcribe()` failed silently if Whisper crashed.
- **Fix**: `try/except` with specific `RuntimeError` catch for PyTorch/hardware faults.

### 9. Tight CPU loop during audio playback
- **Problem**: `while pygame.mixer.music.get_busy(): await asyncio.sleep(0.1)` burned CPU.
- **Fix**: Reduced sleep to `0.05s`.

### 10. Missing error context
- **Problem**: Generic exceptions didn't indicate what failed.
- **Fix**: Specific `RequestException` catches for network errors throughout.

---

## Session 2 Fixes

### 11. Wrong agent constructor (CRITICAL)
- **Problem**: `from langchain.agents import create_agent` does not exist in modern LangChain. Import crashed at startup.
- **Fix**: Replaced with `from langgraph.prebuilt import create_react_agent`. Updated constructor call to use `state_modifier=SYSTEM_PROMPT` (correct parameter name for langgraph ≥0.2.0).

### 12. Missing public API surface in brain.py (CRITICAL)
- **Problem**: `voice.py` imported `ask_friday`, `store_memory`, `check_connection` from `brain.py`, but none of these functions were defined there. Resulted in `ImportError` on every startup.
- **Fix**: Added all three as proper top-level functions in `brain.py` with full docstrings and error handling.

### 13. Duplicate / incomplete `extract_and_store_facts`
- **Problem**: A second, incomplete definition of `extract_and_store_facts` shadowed the correct one inside the `if __name__ == "__main__"` block (ended with `...`).
- **Fix**: Removed the duplicate. The single module-level `_extract_and_store_facts` is the canonical version.

### 14. `OllamaEmbeddings` imported from deprecated path
- **Problem**: `from langchain_community.embeddings import OllamaEmbeddings` triggers a deprecation warning in langchain ≥0.3.x and will be removed in a future release.
- **Fix**: Updated to `from langchain_ollama import ChatOllama, OllamaEmbeddings`. Removed `langchain-community` from requirements.txt as it is no longer needed.

### 15. Unused `threading` import in voice.py
- **Problem**: `import threading` was present in voice.py but never called (threading is used internally by `brain.ask_friday`).
- **Fix**: Removed the unused import.

### 16. Model default mismatch across files
- **Problem**: `brain.py` defaulted to `llama3` (better tool-use), but `README.md` and `.env.example` still referenced `qwen3.5:0.8b`.
- **Fix**: Updated `.env.example` and `README.md` to recommend `llama3` as the default, with `qwen3.5:0.8b` noted as a low-resource alternative.

### 17. `test_tts.py` voice mismatch
- **Problem**: `test_tts.py` used `en-GB-SoniaNeural` while `voice.py` used `en-US-AriaNeural`. TTS test passed but tested the wrong voice.
- **Fix**: Updated `test_tts.py` to reference the same `NEURAL_VOICE` constant used in `voice.py`.

---

## Testing Checklist

- [ ] `python voice.py` starts without ImportError
- [ ] Whisper loads on first recording attempt
- [ ] Morning briefing speaks on startup
- [ ] Push-to-talk records and transcribes correctly
- [ ] Queries reach the LangGraph agent and return spoken responses
- [ ] "Remember that X" stores X in Chroma, replies "Pattern logged"
- [ ] Ollama offline: shows warning, first query returns graceful error message
- [ ] Multiple TTS calls in sequence: no stale audio, no mixer crash
- [ ] `python brain.py` (text mode) works independently
- [ ] `python test_tts.py` plays greeting in AriaNeural voice
- [ ] Keyboard interrupt in voice.py: clean shutdown, no traceback
