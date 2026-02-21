#-----------------------------------------------------------------------------
# отладочный блок - пытаемся отловить Seg Fault

import sys
import faulthandler

# включаем отладчик падений
# если приложение упадет, оно создаст файл crash_report.txt
# и запишет туда, на какой строке кода это случилось.
try:
    f = open("crash_report.txt", "w", encoding="utf-8")
    faulthandler.enable(file=f)
    print("✅ Faulthandler enabled. Writing crashes to crash_report.txt")
except Exception as e:
    print(f"⚠️ Could not enable faulthandler: {e}")

#-----------------------------------------------------------------------------



import sys
import threading
import time
import os
import gc 
import signal  
from pynput import keyboard
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QTimer 

# Импорты конфигурации и сервисов
from core.config import cfg
from ui.overlay import OverlayWindow
from services.clipboard import ClipboardManager
from services.recorder import AudioRecorder
from services.unified_ai import UnifiedAIService 
from services.tts import TTSFactory 
from core.state import AppState


# FIX DPI
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0" 
# os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

class MagicPasteApp(QObject):
    sig_update_status = Signal(str, str)
    sig_update_text = Signal(str)
    sig_show = Signal()
    sig_hide = Signal()

    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        
        # фикс для ctrl+c
        # позволяем Python ловить SIGINT
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        
        # таймер, который дергает event loop, чтобы сигналы проходили
        self.timer = QTimer()
        self.timer.start(500)
        self.timer.timeout.connect(lambda: None) 
        # -----------------------

        self.app.aboutToQuit.connect(self.cleanup)

        self.overlay = OverlayWindow()
        self.clipboard = ClipboardManager()
        self.recorder = AudioRecorder()
        self.state = AppState.IDLE
        
        # Загрузка хоткея из конфига
        hotkey_str = cfg.get("app", "hotkey", "f8")
        try:
            self.target_key = getattr(keyboard.Key, hotkey_str)
        except:
            self.target_key = keyboard.Key.f8
        self.HOTKEY_ACTIVATE = {self.target_key}

        self.current_context = ""
        self.stt = None
        self.llm = None
        self.tts = None
        self.unified_service = None 
        
        threading.Thread(target=self._init_ai, daemon=True).start()

        self.sig_update_status.connect(self.overlay.update_status)
        self.sig_update_text.connect(self.overlay.update_text)
        self.sig_show.connect(self.overlay.show_overlay)
        self.sig_hide.connect(self.overlay.hide_overlay)

        self.current_keys = set()
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def _init_ai(self):
        """Инициализация ИИ согласно конфигу"""
        
        # LLM. запускаем единый сервер
        self.unified_service = UnifiedAIService()
        self.llm = self.unified_service 

        # STT. выбираем модель
        provider = cfg.get("stt", "provider", "gemma")
        
        if provider == "gemma":
            print("🎤 STT Provider: Gemma Native")
            # unifiedService реализует метод transcribe, так что используем его же
            self.stt = self.unified_service
        else:
            print("🎤 STT Provider: Whisper")
            # пытаемся загрузить Whisper
            try:
                from services.stt import STTService
                self.stt = STTService() # он сам прочитает конфиг whisper
            except ImportError:
                print("❌ Whisper module not found! Fallback to Native.")
                self.stt = self.unified_service

        # TTS
        print("🗣 Initializing TTS...")
        self.tts = TTSFactory.create()



    def on_press(self, key):
        try:
            self.current_keys.add(key)
            if self.HOTKEY_ACTIVATE.issubset(self.current_keys):
                if self.state == AppState.IDLE:
                    self.start_flow()
                elif self.state == AppState.LISTENING:
                    self.stop_listening_and_process()
        except AttributeError:
            pass

    def on_release(self, key):
        try:
            if key in self.current_keys:
                self.current_keys.remove(key)
        except KeyError:
            pass

    # def start_flow(self):
    #     threading.Thread(target=self._start_logic, daemon=True).start()

    # def stop_listening_and_process(self):
    #     threading.Thread(target=self._stop_logic, daemon=True).start()

    def start_flow(self):
        # защита от дребезга - меняем состояние сразу в главном потоке
        if self.state != AppState.IDLE: return
        self.state = AppState.CAPTURING
        
        threading.Thread(target=self._start_logic, daemon=True).start()

    def stop_listening_and_process(self):
        # защита от дребезга
        if self.state != AppState.LISTENING: return
        self.state = AppState.PROCESSING
        
        threading.Thread(target=self._stop_logic, daemon=True).start()


    def _start_logic(self):
        # Проверяем, загрузились ли модели
        if not self.stt or not self.llm:
            print("⏳ AI Models loading...")
            self.state = AppState.IDLE
            return

        self.state = AppState.CAPTURING
        self.sig_update_status.emit("Listening...", "#FF0000")
        
        # захват контекста
        raw_context = self.clipboard.capture_context()
        
        # фикс пустого контекста
        if raw_context and len(raw_context.strip()) > 0:
            self.current_context = raw_context
            preview = (self.current_context) 
        else:
            self.current_context = "" # явно пустая строка
            preview = "No context (Chat Mode)"
        # ------------------------------

        self.clipboard.restore() 
        self.sig_show.emit()
        self.sig_update_text.emit(f"Context: {preview}")

        self.recorder.start_recording()
        
        # в конце переключаем в LISTENING, чтобы разрешить остановку
        self.state = AppState.LISTENING


    def _stop_logic(self):
        # self.state уже PROCESSING, проверка не нужна
        self.sig_update_status.emit("Thinking...", "#FFFF00")
        
        audio_buffer = self.recorder.stop_recording()
        if not audio_buffer:
            self.state = AppState.IDLE
            self.sig_hide.emit()
            return

        # 1. Распознавание
        try:
            command_text = self.stt.transcribe(audio_buffer)
        except Exception as e:
            command_text = ""
            print(f"STT Error: {e}")

        print(f"⚡ Cmd: {command_text}")
        self.sig_update_text.emit(f"{command_text}")
        
        # 2. Обработка
        result = self.llm.process_command(self.current_context, command_text)
        
        if result["type"] == "tool":
            self.sig_update_status.emit("Pasting...", "#00FF00")
            self.sig_hide.emit() 
            
            delay = cfg.get("app", "paste_delay", 0.8)
            time.sleep(delay)
            
            self.clipboard.inject_text(result["content"])
            
        elif result["type"] == "chat":
            self.sig_update_status.emit("Chat", "#00FFFF")
            self.sig_update_text.emit(result["content"])
            
            print(f"🗣 Speaking: {result['content'][:30]}...")
            
            if self.tts:
                try:
                    self.tts.speak(result["content"])
                except Exception as e:
                    print(f"TTS Fail: {e}")
                    time.sleep(3)
            else:
                time.sleep(4) 
            
            self.sig_hide.emit()
        else:
            self.sig_update_status.emit("Error", "#FF0000")
            time.sleep(1)
            self.sig_hide.emit()
        
        self.state = AppState.IDLE
        gc.collect()
        
         
    def _stop_logic(self):
        # if self.state != AppState.LISTENING: return
        # self.state = AppState.PROCESSING
        # self.state уже PROCESSING, проверка не нужна
        
        self.sig_update_status.emit("Thinking...", "#FFFF00")
        
        # получаем аудио из памяти
        audio_buffer = self.recorder.stop_recording()
        if not audio_buffer:
            self.state = AppState.IDLE
            self.sig_hide.emit()
            return

        # STT. Распознавание использует выбранный self.stt
        command_text = self.stt.transcribe(audio_buffer)
        print(f"⚡ Cmd: {command_text}")
        self.sig_update_text.emit(f"{command_text}")
        
        # lLM. Обработка использует self.llm - UnifiedService
        result = self.llm.process_command(self.current_context, command_text)
        
        if result["type"] == "tool":
            print("⚙️ TOOL")
            self.sig_update_status.emit("Pasting...", "#00FF00")

            # скрываем окно - это триггер для ClipboardManager начать ждать фокус
            self.sig_hide.emit() 
            
            # вставка 
            self.clipboard.inject_text(result["content"])
            
        elif result["type"] == "chat":
            
            self.sig_update_status.emit("Chat", "#00FFFF")
            self.sig_update_text.emit(result["content"])
            # тут таймер нужен, чтобы юзер успел прочитать
            print(f'🗣️ Speaking\n{result["content"]}')
            if self.tts:
                self.tts.speak(result["content"])
            else:
                time.sleep(4) # фолбэк если TTS сломался
            self.sig_hide.emit()
            
        else:
            self.sig_update_status.emit("Error", "#FF0000")
            time.sleep(1)
            self.sig_hide.emit()
        
        self.state = AppState.IDLE
        
        # принудительно чистим память после тяжелой работы
        gc.collect()


    def cleanup(self):
        print("🧹 Cleaning up resources...")
        
        # пытаемся выключить штатно
        if self.unified_service:
            self.unified_service.kill()
    
        # на всякий случай
        import subprocess
        try:
            print("💀 Force killing any remaining llama-server instances...")
            subprocess.run("taskkill /F /IM llama-server.exe", shell=True, stderr=subprocess.DEVNULL)
        except:
            pass


    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    magic_app = MagicPasteApp()
    magic_app.run()