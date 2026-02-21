import os
import asyncio
import edge_tts
import torch
import tempfile
import time
from abc import ABC, abstractmethod
from core.config import cfg
from services.player import AudioPlayer

class ITTSProvider(ABC):
    @abstractmethod
    def speak(self, text: str):
        pass

# edge tts (online)
class EdgeTTSProvider(ITTSProvider):
    def __init__(self, player):
        self.player = player
        conf = cfg.get("tts", "edge", {})
        self.voice = conf.get("voice", "ru-RU-SvetlanaNeural")
        self.rate = conf.get("rate", "+0%")
        self.volume = conf.get("volume", "+0%")

    def speak(self, text: str):
        # создаем временный файл
        # delete=False, так как pygame нужно открыть его по имени
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd) # закрываем дескриптор, чтобы edge_tts мог писать

        try:
            # запускаем асинхронный код синхронно
            asyncio.run(self._generate(text, path))
            # играем
            self.player.play(path)
        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            # чистим за собой
            if os.path.exists(path):
                os.remove(path)

    async def _generate(self, text, path):
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, volume=self.volume)
        await communicate.save(path)

# silero tts - offline
class SileroTTSProvider(ITTSProvider):
    def __init__(self, player):
        self.player = player
        conf = cfg.get("tts", "silero", {})
        self.model_id = conf.get("model_id", "v5_ru")
        self.speaker = conf.get("speaker", "xenia")
        self.device =  torch.device(conf.get("device", "cpu"))

        print(f"🚀 self.device = {self.device}")
                
        print(f"🎧 Loading Silero TTS ({self.model_id})...")
        try:
            # загрузка через torch.hub - скачает при первом запуске
            self.model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-models',
                model='silero_tts',
                language='ru',
                speaker=self.model_id
            )
            self.model.to(self.device)
            print("✅ Silero TTS loaded.")
        except Exception as e:
            print(f"❌ Silero Load Error: {e}")
            self.model = None

    def speak(self, text: str):
        if not self.model: return

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        try:
            # генерация аудио  - tensor
            audio = self.model.save_wav(
                text=text,
                speaker=self.speaker,
                sample_rate=48000,
                audio_path=path # silero сам сохранит в файл
            )
            self.player.play(path)
        except Exception as e:
            print(f"Silero Error: {e}")
        finally:
            if os.path.exists(path):
                os.remove(path)

# factory
class TTSFactory:
    @staticmethod
    def create() -> ITTSProvider:
        player = AudioPlayer()
        provider_type = cfg.get("tts", "provider", "edge")
        
        if provider_type == "silero":
            return SileroTTSProvider(player)
        else:
            return EdgeTTSProvider(player)