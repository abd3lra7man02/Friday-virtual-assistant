# test_tts.py
import asyncio
import tempfile
import os
import pygame

pygame.mixer.init()

def play_mp3(filepath):
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)

async def test_speak():
    import edge_tts
    communicate = edge_tts.Communicate("Hello, this is a test.", "en-GB-SoniaNeural")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name
        await communicate.save(tmp_path)
    play_mp3(tmp_path)
    os.unlink(tmp_path)

asyncio.run(test_speak())
print("If you heard 'Hello, this is a test.', TTS works.")