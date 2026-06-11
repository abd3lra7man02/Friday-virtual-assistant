# Bug Fixes – Friday Voice Assistant

## Issues Fixed

### 1. **pygame.mixer multiple init/quit (CRITICAL)**
- **Problem**: `pygame.mixer.init()` called on every TTS, then `pygame.mixer.quit()` after playback. Mixer would be dead after first call.
- **Fix**: Initialize mixer once with global flag `pygame_initialized`, never call quit.

### 2. **Whisper model blocking startup**
- **Problem**: `whisper.load_model("base")` called at module level, blocks startup for 10+ seconds, fails if model not cached.
- **Fix**: Lazy load with `load_stt_model()` on first transcription, with user feedback.

### 3. **Audio queue contamination**
- **Problem**: Global `audio_q` never cleared between recordings, accumulates stale chunks.
- **Fix**: Reset queue at start of each recording.

### 4. **TTS file path race condition**
- **Problem**: All concurrent TTS writes to same temp file "friday_tts.mp3", overwrites in-flight audio.
- **Fix**: Use unique filename per task: `f"friday_tts_{id(asyncio.current_task())}.mp3"`.

### 5. **pyttsx3 resource leak**
- **Problem**: `engine.stop()` not guaranteed to release resources if exception occurs.
- **Fix**: Wrap in try/finally block to ensure cleanup.

### 6. **No Ollama connection validation**
- **Problem**: Script starts without checking if Ollama is reachable, fails on first query with confusing error.
- **Fix**: Add `check_ollama_connection()`, cache result, validate on startup with warning.

### 7. **Memory extraction edge cases**
- **Problem**: "remember" alone would match before "remember this", returning wrong content.
- **Fix**: Check longer phrases first, validate extracted content is not empty.

### 8. **No transcription error handling**
- **Problem**: `transcribe()` fails silently if Whisper crashes.
- **Fix**: Add try/except with user feedback.

### 9. **Tight CPU loop during audio playback**
- **Problem**: `while pygame.mixer.music.get_busy(): await asyncio.sleep(0.1)` burns CPU.
- **Fix**: Reduced sleep to 0.05s (minimal, matches audio buffer).

### 10. **Missing error context**
- **Problem**: Generic exceptions don't indicate what failed.
- **Fix**: Added specific exception types for timeout, connection errors, etc.

## Testing Checklist

- [ ] Ollama offline: shows warning, falls back gracefully
- [ ] Ollama online: first TTS works without mixer errors
- [ ] Multiple TTS calls in sequence: no stale audio playback
- [ ] Whisper model loads on first recording: shows "Loading Whisper model..."
- [ ] Memory learning: "remember this X" correctly extracts and stores X
- [ ] Recording: audio queue cleared between sessions
- [ ] Keyboard interrupt: clean shutdown, no tracebacks

## No Breaking Changes

All fixes are backwards compatible. Existing functionality preserved.
