import json
import re

def validate_dataset(filename):
    print(f"🔍 Проверяем файл: {filename}...")
    errors = 0
    valid_count = 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line: continue
                
                # проверка JSON структуры
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"❌ Ошибка JSON в строке {i+1}: {e}")
                    errors += 1
                    continue
                
                # проверка ролей
                if 'messages' not in entry:
                    print(f"❌ Нет поля 'messages' в строке {i+1}")
                    errors += 1
                    continue
                    
                msgs = entry['messages']
                assistant_msg = next((m for m in msgs if m['role'] == 'assistant'), None)
                
                if not assistant_msg:
                    print(f"⚠️ Нет ответа ассистента в строке {i+1}")
                    continue

                content = assistant_msg['content']
                
                # проверка XML (грубая)
                if "<tool_call>" in content:
                    if "</tool_call>" not in content:
                        print(f"❌ Не закрыт тег </tool_call> в строке {i+1}")
                        errors += 1
                    if "<name>magic_paste</name>" not in content:
                        print(f"⚠️ Странное имя тула в строке {i+1}")
                
                valid_count += 1
                
                # показать первые 2 примера для визуальной проверки
                if i < 2:
                    print(f"\n--- Пример {i+1} ---")
                    print(f"User: {msgs[0]['content']}")
                    print(f"Assistant: {content[:100]}...")

    except FileNotFoundError:
        print(f"❌ Файл {filename} не найден!")
        return

    print(f"\n✅ Итог по {filename}: Валидных строк: {valid_count}. Ошибок: {errors}")

# запускаем проверку
validate_dataset('./data/train_dataset.jsonl')
validate_dataset('./data/test_dataset.jsonl')