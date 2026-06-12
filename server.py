# server.py
import asyncio
import os
import tempfile
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import whisper
import edge_tts

# Import your core logic
from brain import ask_friday, check_connection

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stt_model = None

def load_whisper():
    global stt_model
    if stt_model is None:
        print("Loading Whisper model...")
        stt_model = whisper.load_model("base")
        print("Whisper ready.")

async def generate_tts(text: str) -> str:
    """Generates TTS and returns base64 audio string."""
    communicate = edge_tts.Communicate(text, voice="en-US-AriaNeural", rate="+10%")
    temp_file = os.path.join(tempfile.gettempdir(), f"reply_{id(text)}.mp3")
    await communicate.save(temp_file)
    
    with open(temp_file, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")
        
    os.remove(temp_file)
    return audio_data

@app.websocket("/ws/friday")
async def friday_endpoint(websocket: WebSocket):
    await websocket.accept()
    load_whisper()
    
    try:
        while True:
            # 1. Receive audio blob from React
            data = await websocket.receive_bytes()
            await websocket.send_json({"status": "processing", "message": "Transcribing..."})
            
            # 2. Save blob to temp file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_audio:
                tmp_audio.write(data)
                tmp_path = tmp_audio.name

            # 3. Transcribe
            result = stt_model.transcribe(tmp_path, fp16=False)
            user_text = result["text"].strip()
            os.remove(tmp_path)
            
            if not user_text:
                await websocket.send_json({"status": "error", "message": "No speech detected."})
                continue

            await websocket.send_json({"status": "user_input", "text": user_text})
            await websocket.send_json({"status": "processing", "message": "Thinking..."})

            # 4. Get Agent Response
            reply_text = await asyncio.to_thread(ask_friday, user_text)
            await websocket.send_json({"status": "agent_reply", "text": reply_text})

            # 5. Generate and Send Audio
            await websocket.send_json({"status": "processing", "message": "Synthesizing voice..."})
            audio_b64 = await generate_tts(reply_text)
            await websocket.send_json({"status": "audio_ready", "audio": audio_b64})
            await websocket.send_json({"status": "idle"})

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")
        await websocket.send_json({"status": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    if not check_connection():
        print("⚠️ Ollama is offline. Start Ollama before running queries.")
    uvicorn.run(app, host="0.0.0.0", port=8000)