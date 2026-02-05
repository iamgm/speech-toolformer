import json
import os
import asyncio
import edge_tts
import random

# настройки
DATA_DIR = './data'
INPUT_FILES = ['train_dataset.jsonl', 'test_dataset.jsonl']
OUTPUT_DIR = f'{DATA_DIR}/audio'
VOICES = ['ru-RU-SvetlanaNeural', 'ru-RU-DmitryNeural']

async def generate_audio_dataset():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    
    for filename in INPUT_FILES:
        input_path = os.path.join(DATA_DIR, filename)

        output_data = []
        base_name = filename.split('.')[0]
        print(f"🎙️ Обрабатываем {filename}...")

        if not os.path.exists(input_path):
            print(f"⚠️ Файл {input_path} не найден, пропускаем...")
            continue
        
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for idx, line in enumerate(lines):
            data = json.loads(line)
            
            # достаем текст пользователя
            user_text = next((m['content'] for m in data['messages'] if m['role'] == 'user'), None)
            
            if user_text:
                # выбираем голос 
                voice = random.choice(VOICES)

                audio_filename = f"{base_name}_{idx:03d}_{voice}.mp3"
                audio_path = os.path.join(OUTPUT_DIR, audio_filename)
                
                communicate = edge_tts.Communicate(user_text, voice) 
                await communicate.save(audio_path)
                
                # добавляем путь к аудио в данные
                data['audio_path'] = audio_path
                output_data.append(data)
                
                if idx % 10 == 0:
                    print(f"   Processed {idx}/{len(lines)}")

        # сохраняем новый JSONL с путями к аудио
        new_filename = f"{DATA_DIR}/{base_name}_with_audio.jsonl"
        with open(new_filename, 'w', encoding='utf-8') as f:
            for entry in output_data:
                json.dump(entry, f, ensure_ascii=False)
                f.write('\n')
        
        print(f"✅ Готово! Сохранен файл: {new_filename}")

# запуск асинхронной функции
if __name__ == "__main__":
    loop = asyncio.get_event_loop_policy().get_event_loop()
    loop.run_until_complete(generate_audio_dataset())