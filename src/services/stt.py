import os
import io # для работы с байтами
from faster_whisper import WhisperModel
from core.config import cfg

# получаем настройки из yaml конфига
conf = cfg.get("stt", "whisper")

class STTService:
    def __init__(
        self,
        model_size= conf.get("model_size", "base"),
        device=conf.get("device", "cuda"),
        compute_type="int8"):
        
        print(f"Loading Whisper ({model_size})...")
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            print("✅ Whisper loaded.")
        except Exception as e:
            print(f"❌ Whisper load failed: {e}")
            self.model = None

    def transcribe(self, audio_data) -> str:
        """
        Принимает: путь к файлу (str) ИЛИ байтовый поток (BytesIO)
        """
        if not self.model:
            return ""
        
        try:
            # beam_size=1 ускоряет в 2-3 раза. Для команд точности хватит.
            segments, info = self.model.transcribe(
                audio_data, 
                beam_size=1, 
                language="ru", # если жестко задать язык, не тратится время на детекцию
                vad_filter=True # отсекает тишину
            )
            
            text = " ".join([segment.text for segment in segments]).strip()
            return text
        except Exception as e:
            return f"Error: {str(e)}"

