from enum import Enum, auto

class AppState(Enum):
    IDLE = auto()        # ожидание - окно скрыто
    CAPTURING = auto()   # захват контекста - Ctrl+C
    LISTENING = auto()   # запись голоса
    PROCESSING = auto()  # обработка LLM
    EXECUTING = auto()   # вставка текста или озвучка