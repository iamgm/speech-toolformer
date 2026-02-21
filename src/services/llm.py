import subprocess
import os
import time
import requests
import sys
import ctypes
from ctypes import wintypes
from core.config import cfg

# WIN32 API константы для kill_on_close
JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', wintypes.LARGE_INTEGER),
        ('PerJobUserTimeLimit', wintypes.LARGE_INTEGER),
        ('LimitFlags', wintypes.DWORD),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', wintypes.DWORD),
        ('Affinity', ctypes.c_size_t),
        ('PriorityClass', wintypes.DWORD),
        ('SchedulingClass', wintypes.DWORD),
    ]

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [('ReadOperationCount', ctypes.c_ulonglong), ('WriteOperationCount', ctypes.c_ulonglong), ('OtherOperationCount', ctypes.c_ulonglong), ('ReadTransferCount', ctypes.c_ulonglong), ('WriteTransferCount', ctypes.c_ulonglong), ('OtherTransferCount', ctypes.c_ulonglong)]

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('IoInfo', IO_COUNTERS),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t),
    ]

# ---------------------------------------------

INFERENCE_SYSTEM_PROMPT = """Ты — ИИ-ассистент для редактирования текста.
Твоя задача: либо просто ответить пользователю (Чат), либо сгенерировать готовый XML для вставки в приложение (Инструмент).

### ГЛАВНЫЕ ПРАВИЛА
1. **ЯЗЫК:** Всегда отвечай на том же языке, на котором спрашивает пользователь.
2. **ФОРМАТ:** Никогда не используй Markdown (```xml или ```json). Выводи чистый текст или чистый XML в одну строку.
3. **РОЛЬ:** Ты — инструмент работы с текстом. Ты умеешь и писать с нуля (произвольный тест, стихи, код, письма), и редактировать. Если просят что-то создать — создавай. Не отказывайся.
4. **ДИСЦИПЛИНА:** ВСЕГДА следуй логике выбора режима ниже.

---

### ЛОГИКА ВЫБОРА РЕЖИМА

**РЕЖИМ 1: ИНСТРУМЕНТ (Вставка текста)**
Используй этот режим, если пользователь хочет **СОЗДАТЬ** или **ИЗМЕНИТЬ** текст/код.
Триггеры (Глаголы действия):
- **Напиши / Составь / Сгенерируй** ("Напиши письмо", "Составь список", "Составь чек-лист")
- **Придумай / Создай** ("Придумай название", "Создай 3 варианта")
- **Исправь / Перепиши / Сократи / Улучши** ("Исправь ошибки", "Сделай вежливее")
- **Переведи** ("Переведи на английский")
- **Код** ("Напиши функцию")

ФОРМАТ ОТВЕТА (Строго XML в одну строку без лишних слов):
<tool_call><name>magic_paste</name><arguments><text>ТВОЙ_ГОТОВЫЙ_ТЕКСТ</text></arguments></tool_call>

---

**РЕЖИМ 2: ЧАТ (Обычный разговор)**
Используй этот режим, если пользователь хочет **УЗНАТЬ** информацию, поблагодарить или просто поболтать.
Триггеры (Глаголы восприятия):
- **Расскажи / Объясни** ("Расскажи про...", "Объясни как работает...")
- **Вопросы** ("Что такое...", "Кто победил...", "Как переводится...")
- **Вежливость** ("Привет", "Спасибо", "Пока")
- **Посоветуй / Подскажи** ("Посоветуй фильм")
- **Как переводится** ("Как переводится на английский...")



ФОРМАТ ОТВЕТА:
Простой текст ответа. Кратко и по делу.

### ПРИМЕРЫ (Обучение)

Пользователь: "Привет, как дела?"
Ответ: Привет! Я готов к работе с текстом.
Пояснение: Вежливость -> Чат

Пользователь: "Придумай 3 идеи для стартапа."
Ответ: <tool_call><name>magic_paste</name><arguments><text>1. Умный сад\n2. AI-репетитор\n3. Доставка дронами</text></arguments></tool_call>
Пояснение: Команда "Придумай" -> Инструмент

Пользователь: "Напиши функцию сортировки на JS."
Ответ: <tool_call><name>magic_paste</name><arguments><text>const sort = (arr) => arr.sort();</text></arguments></tool_call>
Пояснение: Команда "Напиши" -> Инструмент

Пользователь: "Объясни, как работает сортировка."
Ответ: Сортировка упорядочивает элементы в массиве по определенному критерию, например, по возрастанию чисел.
Пояснение: Просьба "Объясни" -> Чат

Пользователь: "Перепиши это вежливо: Ты опоздал."
Ответ: <tool_call><name>magic_paste</name><arguments><text>К сожалению, вы задержались.</text></arguments></tool_call>
Пояснение: Команда "Перепиши" -> Инструмент

Пользователь: "Переведи на английский: Привет мир"
Ответ: <tool_call><name>magic_paste</name><arguments><text>Hello World</text></arguments></tool_call>
Пояснение: Команда "Переведи" -> Инструмент

Пользователь: "Как переводится: Привет мир"
Ответ:  "Привет мир переводится на английский как 'Hello World'."
Пояснение: Вопрос "Как переводится" -> Чат

### КОНЕЦ ПРИМЕРОВ. НАЧАЛО ДИАЛОГА:
"""


# ---------------------------------------------


class LLMService:
    def __init__(self): 
        # берем из конфига
        host = cfg.get("server", "host")
        port = cfg.get("server", "port")

        self.api_url = f"http://{host}:{port}/completion"
        self.health_url = f"http://{host}:{port}/health"
        
        self.process = None
        self.job_handle = None

        if not os.path.exists(self.model_path):
            print(f"❌ Error: Model not found at {self.model_path}")
            return
            
        self._start_server()

    def _start_server(self):
        print(f"🚀 Starting Local LLM Server ...")
        
        args = [
            os.path.abspath("exe", "exe_path"),
            "-m", os.path.abspath(cfg.get("llm", "model_path")),
            "--port", str(self.port),
            "-c", str(cfg.get("llm", "context_size", 1024)), 
            "-np", "1",
            "-ngl", str(cfg.get("llm", "gpu_layers", 99)), 
            "--threads", str(cfg.get("llm", "threads", 4))
        ]


        # запускаем процесс
        self.process = subprocess.Popen(
            args,
            stdout=sys.stdout,
            stderr=sys.stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB
        )

        # создаем Job Object и привязываем процесс
        if os.name == 'nt':
            try:
                self.job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
                
                info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                
                # настраиваем Job: Убить всех, если хендл закрыт
                ctypes.windll.kernel32.SetInformationJobObject(
                    self.job_handle,
                    JobObjectExtendedLimitInformation,
                    ctypes.pointer(info),
                    ctypes.sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION)
                )
                
                # привязываем процесс к Job
                ctypes.windll.kernel32.AssignProcessToJobObject(
                    self.job_handle,
                    ctypes.c_void_p(self.process._handle)
                )
                print("🔒 Secure Process Job created (Auto-kill enabled)")
            except Exception as e:
                print(f"⚠️ Failed to create Job Object: {e}")

        # ждем запуска
        print("⏳ Waiting for server...")
        for _ in range(30):
            try:
                requests.get(self.health_url, timeout=1)
                print("\n✅ Server is READY!")
                return
            except requests.exceptions.RequestException:
                time.sleep(1)
        
        print("\n❌ Server failed to start.")

    def process_command(self, context: str, command: str) -> dict:
        if context and len(context.strip()) > 0:
            user_content = f"Контекст:\n{context}\n\nЗадание: {command}"
        else:
            user_content = command

        full_prompt = (
            "<start_of_turn>user\n"
            f"{INFERENCE_SYSTEM_PROMPT}\n\n"
            f"Пользователь: \"{user_content}\""
            "<end_of_turn>\n"
            "<start_of_turn>model\n"
        )

        payload = {
            "prompt": full_prompt,
            "n_predict": 1024,
            "temperature": 0.1,
            "stop": ["<end_of_turn>"],
            "cache_prompt": True, # System Prompt не будет пересчитываться
            "slot_id": 0 # всегда перезаписываем 0-й слот (удаляем старый контекст, оставляя кэш префикса)
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            result_json = response.json()
            text = result_json.get("content", "")
            return self._parse_response(text)
        except Exception as e:
            return {"type": "error", "content": str(e)}

    def _parse_response(self, text: str) -> dict:
        import re
        tool_pattern = re.compile(r"<tool_call>.*?<text>(.*?)</text>.*?</tool_call>", re.DOTALL)
        match = tool_pattern.search(text)
        if match:
            content = match.group(1).strip().replace("\\n", "\n")
            return {"type": "tool", "content": content}
        else:
            clean_text = re.sub(r"<[^>]+>", "", text).strip()
            return {"type": "chat", "content": clean_text}
