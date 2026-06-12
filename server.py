# server.py – Friday FastAPI WebSocket backend
import asyncio
import os
import logging
import tempfile
import base64
import uuid
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
import whisper
import edge_tts

from brain import ask_friday, check_connection

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('friday_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FRIDAY_API_KEY = os.getenv("FRIDAY_API_KEY", "").strip()
if not FRIDAY_API_KEY:
    # Generate a random key if not provided
    FRIDAY_API_KEY = f"auto_{uuid.uuid4().hex[:16]}"
    logger.warning(f"No FRIDAY_API_KEY in .env – using temporary key: {FRIDAY_API_KEY}")

MAX_MESSAGE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_TRANSCRIPTION_LENGTH = 5000  # characters

# ---------------------------------------------------------------------------
# Whisper – thread-safe lazy initialisation
# ---------------------------------------------------------------------------
_stt_model = None
_whisper_lock = threading.Lock()


def _load_whisper_sync() -> None:
    """Load the Whisper model. Safe to call from multiple threads."""
    global _stt_model
    with _whisper_lock:
        if _stt_model is None:
            logger.info("Loading Whisper model…")
            try:
                _stt_model = whisper.load_model("base")
                logger.info("✓ Whisper model ready.")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise


def _transcribe_sync(file_path: str) -> str:
    """
    Run Whisper transcription synchronously.
    Always called via asyncio.to_thread() – never on the event loop.
    """
    with _whisper_lock:
        model = _stt_model
    if model is None:
        raise RuntimeError("Whisper model is not loaded.")
    
    try:
        result = model.transcribe(file_path, fp16=False)
        text = result.get("text", "").strip()
        
        # Validate result
        if not isinstance(text, str):
            logger.error(f"Unexpected transcription result type: {type(text)}")
            return ""
        
        if len(text) > MAX_TRANSCRIPTION_LENGTH:
            logger.warning(f"Transcription too long ({len(text)}), truncating")
            text = text[:MAX_TRANSCRIPTION_LENGTH]
        
        return text
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# App lifecycle (modern FastAPI lifespan – replaces deprecated @on_event)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load Whisper at startup in a thread pool
    try:
        await asyncio.to_thread(_load_whisper_sync)
    except Exception as e:
        logger.error(f"Failed to pre-load Whisper: {e}")
    
    if not check_connection():
        logger.warning("⚠️  Ollama is offline. Start Ollama before sending queries.")
    else:
        logger.info("Ollama connection verified at startup.")

    yield
    
    # Cleanup on shutdown
    logger.info("Server shutting down")


app = FastAPI(lifespan=lifespan)

# CORS configuration – restrict to localhost only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check endpoint to verify server is running."""
    ollama_ok = check_connection()
    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama": "online" if ollama_ok else "offline",
        "version": "1.0.0"
    }


# ---------------------------------------------------------------------------
# TTS helper
# ---------------------------------------------------------------------------
async def _generate_tts(text: str) -> str:
    """
    Generate speech via edge-tts and return a base64-encoded MP3 string.
    Uses a uuid filename to prevent race conditions.
    """
    if not text or not text.strip():
        logger.warning("Attempted TTS with empty text")
        return ""
    
    temp_file = os.path.join(tempfile.gettempdir(), f"friday_reply_{uuid.uuid4().hex}.mp3")
    try:
        logger.debug(f"Generating TTS for {len(text)} characters")
        communicate = edge_tts.Communicate(text, voice="en-US-AriaNeural", rate="+10%")
        await communicate.save(temp_file)
        
        with open(temp_file, "rb") as f:
            audio_data = f.read()
        
        if not audio_data:
            logger.error("TTS generated empty audio file")
            return ""
        
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        logger.debug(f"TTS generated successfully ({len(audio_b64)} bytes base64)")
        return audio_b64
    except Exception as e:
        logger.error(f"TTS generation failed: {e}", exc_info=True)
        return ""
    finally:
        # Guarantee cleanup
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError as e:
            logger.warning(f"Failed to cleanup {temp_file}: {e}")


# ---------------------------------------------------------------------------
# Authentication helper
# ---------------------------------------------------------------------------
def _validate_token(token: str | None) -> bool:
    """Validate WebSocket authentication token."""
    if not token:
        return False
    return token == FRIDAY_API_KEY


# ---------------------------------------------------------------------------
# WebSocket endpoint with authentication
# ---------------------------------------------------------------------------
@app.websocket("/ws/friday")
async def friday_endpoint(websocket: WebSocket):
    # FIXED: Validate token BEFORE accepting connection
    token = None
    if websocket.query_params:
        token = websocket.query_params.get("token")
    
    if not _validate_token(token):
        logger.warning(f"Unauthorized WebSocket connection attempt")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return
    
    await websocket.accept()
    
    # Each connection gets a unique session ID
    session_id = f"ws_{uuid.uuid4().hex}"
    logger.info(f"[+] Authenticated client connected (session: {session_id})")

    try:
        while True:
            # ------------------------------------------------------------------
            # 1. Receive audio blob from the React frontend
            # ------------------------------------------------------------------
            try:
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket timeout for session {session_id}")
                await websocket.send_json({"status": "error", "message": "Connection timeout"})
                break

            if not data:
                await websocket.send_json({"status": "error", "message": "Empty audio received."})
                await websocket.send_json({"status": "idle"})
                continue
            
            # Validate message size
            if len(data) > MAX_MESSAGE_SIZE:
                logger.warning(f"Message size exceeded: {len(data)} > {MAX_MESSAGE_SIZE}")
                await websocket.send_json({"status": "error", "message": "Audio file too large"})
                await websocket.send_json({"status": "idle"})
                continue

            await websocket.send_json({"status": "processing", "message": "Transcribing..."})

            # ------------------------------------------------------------------
            # 2. Write audio to a temp file for Whisper
            # ------------------------------------------------------------------
            tmp_path = os.path.join(
                tempfile.gettempdir(), f"friday_input_{uuid.uuid4().hex}.webm"
            )
            try:
                with open(tmp_path, "wb") as f:
                    f.write(data)

                # 3. Transcribe – runs in thread pool
                try:
                    user_text = await asyncio.to_thread(_transcribe_sync, tmp_path)
                except Exception as e:
                    logger.error(f"Transcription failed: {e}")
                    await websocket.send_json({"status": "error", "message": "Transcription failed"})
                    await websocket.send_json({"status": "idle"})
                    continue

            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError as e:
                        logger.warning(f"Failed to cleanup {tmp_path}: {e}")

            if not user_text:
                await websocket.send_json({"status": "error", "message": "No speech detected."})
                await websocket.send_json({"status": "idle"})
                continue

            logger.info(f"[{session_id}] Transcribed: {user_text[:50]}...")
            await websocket.send_json({"status": "user_input", "text": user_text})
            await websocket.send_json({"status": "processing", "message": "Thinking..."})

            # ------------------------------------------------------------------
            # 4. LLM agent response – runs in thread pool
            # ------------------------------------------------------------------
            try:
                reply_text = await asyncio.to_thread(ask_friday, user_text, session_id)
            except Exception as e:
                logger.error(f"Agent error for session {session_id}: {e}")
                reply_text = "I encountered an error, Sir. Please try again."
            
            logger.info(f"[{session_id}] Agent response: {reply_text[:50]}...")
            await websocket.send_json({"status": "agent_reply", "text": reply_text})

            # ------------------------------------------------------------------
            # 5. TTS – async edge-tts, sends audio back to client
            # ------------------------------------------------------------------
            await websocket.send_json({"status": "processing", "message": "Synthesizing voice..."})
            try:
                audio_b64 = await _generate_tts(reply_text)
                if audio_b64:
                    await websocket.send_json({"status": "audio_ready", "audio": audio_b64})
                else:
                    logger.warning(f"TTS returned empty audio for session {session_id}")
            except Exception as tts_err:
                logger.warning(f"TTS error (non-fatal) for session {session_id}: {tts_err}")

            await websocket.send_json({"status": "idle"})

    except WebSocketDisconnect:
        logger.info(f"[-] Client disconnected (session: {session_id})")
    except Exception as exc:
        logger.error(f"WebSocket error (session: {session_id}): {exc}", exc_info=True)
        try:
            await websocket.send_json({"status": "error", "message": str(exc)})
        except Exception:
            pass  # Connection may already be dead


# ---------------------------------------------------------------------------
# Direct run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    if not check_connection():
        logger.warning("⚠️  Ollama is offline. Start Ollama before running queries.")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False, log_level="info")