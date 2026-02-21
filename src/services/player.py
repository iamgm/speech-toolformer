import os
import time
import threading

# убираем приветствие pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

class AudioPlayer:
    def __init__(self):
        # мы НЕ инициализируем микшер здесь.
        # это предотвращает зависание при старте приложения, 
        # если аудио-драйвер занят PyAudio или системой.
        self._is_ready = False

    def _ensure_init(self):
        """Ленивая инициализация только при попытке воспроизведения"""
        if self._is_ready:
            return True
            
        try:
            # инициализируем только микшер, без видео-модулей
            # frequency=48000 часто помогает с качеством на EdgeTTS
            pygame.mixer.init(frequency=48000) 
            self._is_ready = True
            print("🔊 AudioPlayer initialized successfully.")
            return True
        except Exception as e:
            print(f"❌ AudioPlayer Init Error: {e}")
            return False

    def play(self, file_path: str):
        """Воспроизводит файл"""
        if not os.path.exists(file_path):
            print(f"⚠️ Audio file not found: {file_path}")
            return

        # пытаемся инициализировать перед воспроизведением
        if not self._ensure_init():
            return

        try:
            # если что-то уже играет - остановим
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()

            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()

            # ждем окончания (блокируем поток TTS, но не GUI)
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"❌ Playback Error: {e}")
            # если произошла ошибка (например, драйвер отвалился), 
            # сбрасываем флаг, чтобы в следующий раз попробовать переинициализировать
            self._is_ready = False 
            try:
                pygame.mixer.quit()
            except: pass

    def stop(self):
        if self._is_ready:
            try:
                pygame.mixer.music.stop()
            except: pass