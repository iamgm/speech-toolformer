import pyaudio
import wave
import io
import threading
import time

class AudioRecorder:
    def __init__(self):
        self._frames = []
        self._stream = None
        self._audio = pyaudio.PyAudio()
        self._is_recording = False
        self._stop_event = threading.Event() # событие для синхронизации
        self._record_thread = None
        
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1024

    def start_recording(self):
        if self._is_recording:
            return
            
        self._frames = []
        self._is_recording = True
        self._stop_event.clear() # сбрасываем флаг остановки
        
        try:
            self._stream = self._audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            # запускаем и сохраняем ссылку на поток
            self._record_thread = threading.Thread(target=self._loop, daemon=True)
            self._record_thread.start()
            print("🎤 Recording started...")
        except Exception as e:
            print(f"❌ Error starting record: {e}")
            self._is_recording = False

    def _loop(self):
        """Цикл записи в отдельном потоке"""
        while self._is_recording:
            try:
                # читаем данные. если поток закрыт, pyaudio выбросит исключение
                data = self._stream.read(self.CHUNK)
                self._frames.append(data)
            except Exception as e:
                # если ошибка чтения (например, поток закрылся), выходим
                print(F"❗Exception {e}")
                break
        
        # сигнализируем, что цикл реально завершился
        self._stop_event.set()

    def stop_recording(self):
        """Останавливает запись и возвращает буфер"""
        if not self._is_recording:
            return None

        print("🛑 Stopping recording...")
        
        # снимаем флаг, чтобы цикл _loop завершился
        self._is_recording = False
        
        # ждем, пока поток записи РЕАЛЬНО закончит работу
        # это предотвращает Access Violation
        if self._record_thread and self._record_thread.is_alive():
            # ждем макс 1 секунду сигнала от _stop_event
            self._stop_event.wait(timeout=1.0)
        
        # теперь безопасно закрываем поток PyAudio
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                print(f"⚠️ Stream close warning: {e}")
            self._stream = None

        if not self._frames:
            print("⚠️ No frames recorded")
            return None

        # собираем WAV в память
        try:
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self._audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self._frames))
            
            buffer.seek(0)
            return buffer
        except Exception as e:
            print(f"❌ Error saving WAV: {e}")
            return None
