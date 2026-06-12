# test_tts.py – quick sanity check for neural TTS pipeline
import asyncio
import tempfile
import os
import pygame

pygame.mixer.init()

# Must match NEURAL_VOICE in voice.py
NEURAL_VOICE = "en-US-AriaNeural"

def play_mp3(filepath: str) -> None:
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)

async def test_speak() -> None:
    import edge_tts
    communicate = edge_tts.Communicate("Hello Sir, Friday is online and ready.", NEURAL_VOICE)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name
    await communicate.save(tmp_path)
    play_mp3(tmp_path)
    os.unlink(tmp_path)

asyncio.run(test_speak())
print("If you heard Friday's greeting, TTS is working correctly.")
