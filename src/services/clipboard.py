import time
import pyperclip
import ctypes
from ctypes import wintypes

# WINAPI structures - правильная реализация через Union
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

VK_CONTROL = 0x11
VK_C = 0x43
VK_F8 = 0x77 
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_ulonglong)]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_ulonglong)]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT),
                ("mi", MOUSEINPUT),
                ("hi", HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD),
                ("u", INPUT_UNION)]

class ClipboardManager:
    def __init__(self):
        self.target_window = None
        self._backup = None

    def _send_input(self, vk, flags=0):
        """Низкоуровневая эмуляция нажатия"""
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        inp.u.ki.wScan = 0
        inp.u.ki.dwFlags = flags
        inp.u.ki.time = 0
        inp.u.ki.dwExtraInfo = 0
        user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(INPUT))

    def _wait_for_key_release(self, vk_code):
        """Ждет, пока физическая клавиша не будет отпущена"""
        print(f"⏳ Waiting for key {vk_code} release...")
        for _ in range(50): # ждем макс 5 секунд
            # getAsyncKeyState возвращает бит 0x8000 если клавиша нажата
            if not (user32.GetAsyncKeyState(vk_code) & 0x8000):
                print("✅ Key released.")
                return
            time.sleep(0.1)
        print("⚠️ Key release timeout (proceeding anyway).")

    def capture_context(self) -> str:
        # проверяем фокус (для отладки)
        hwnd = user32.GetForegroundWindow()
        self.target_window = hwnd
        
        # ждем отпускания гор. клавишы f8
        # если этого не сделать, система увидит Ctrl + F8 + C
        self._wait_for_key_release(VK_F8)

        # чистим буфер
        try:
            self._backup = pyperclip.paste()
        except: self._backup = ""
        pyperclip.copy("") 

        # жмем Ctrl+C - чистая эмуляция
        print("⌨️ Sending Ctrl+C...")
        self._send_input(VK_CONTROL, 0) # ctrl Down
        time.sleep(0.05)
        self._send_input(VK_C, 0)       # c Down
        time.sleep(0.05)
        self._send_input(VK_C, KEYEVENTF_KEYUP) # c Up
        time.sleep(0.05)
        self._send_input(VK_CONTROL, KEYEVENTF_KEYUP) # ctrl Up

        # ждем данные в буфере
        captured = ""
        for i in range(15): # ждем до 1.5 сек
            time.sleep(0.1)
            captured = pyperclip.paste()
            if captured and captured.strip():
                print(f"✅ Context captured! Length: {len(captured)}")
                break
        
        if not captured:
            print("❌ Context capture FAILED (Clipboard still empty)")

        return captured

    def restore(self):
        if self._backup:
            pyperclip.copy(self._backup)

    def inject_text(self, text: str):
        if not self.target_window:
            print("⚠️ No target window to paste into!")
            return

        print(f"📋 Injecting {len(text)} chars...")
        
        # кладем текст в буфер
        pyperclip.copy(text)
        
        # если окно свернуто - развернем
        if user32.IsIconic(self.target_window):
            user32.ShowWindow(self.target_window, 9) # sW_RESTORE
            
        # жестко ставим фокус
        user32.SetForegroundWindow(self.target_window)
        
        # ждем, пока фокус реально перейдет
        for _ in range(20): # макс 2 сек
            if user32.GetForegroundWindow() == self.target_window:
                break
            time.sleep(0.1)
            
        # небольшая пауза перед вставкой
        time.sleep(0.1)
        
        # низкоуровневое Ctrl+V
        print("⌨️ Sending Ctrl+V...")
        self._send_input(VK_CONTROL, 0) # ctrl Down
        time.sleep(0.05)
        self._send_input(VK_V, 0)       # v Down
        time.sleep(0.05)
        self._send_input(VK_V, KEYEVENTF_KEYUP) # v Up
        time.sleep(0.05)
        self._send_input(VK_CONTROL, KEYEVENTF_KEYUP) # ctrl Up
        
        print("✅ Paste command sent")
