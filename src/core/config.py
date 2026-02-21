import yaml
import os

class Config:
    _instance = None
    _config = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        config_path = "config.yaml"
        if not os.path.exists(config_path):
            print(f"⚠️ Config not found at {config_path}, using defaults.")
            self._config = self._default_config()
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
            print("✅ Configuration loaded.")
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            self._config = self._default_config()

    def get(self, section: str, key: str, default=None):
        return self._config.get(section, {}).get(key, default)

    def _default_config(self):
        return {
            "app": {"hotkey": "f8", "paste_delay": 0.5},
            "llm": {"model_path": "models/model.gguf", "context_size": 1024},
            "stt": {"provider": "whisper", "whisper": {"model_size": "tiny"}}
        }

# глобальный экземпляр
cfg = Config()