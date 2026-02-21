from huggingface_hub import HfApi


TOKEN = "" 
REPO_ID = ""
api = HfApi(token=TOKEN)




# загрузка GGUF модели
print("⬆️ Загрузка model.gguf...")
api.upload_file(
    path_or_fileobj="./models/gemma_3n_q4_k_m.gguf", 
    path_in_repo="gemma_3n_q4_k_m.gguf",
    repo_id=REPO_ID,
    repo_type="model"
)

# загрузка проектора
print("⬆️ Загрузка mmproj...")
api.upload_file(
    path_or_fileobj="./models/mmproj_gemma_3n_f16.gguf",
    path_in_repo="mmproj_gemma_3n_f16.gguf",
    repo_id=REPO_ID,
    repo_type="model"
)

print("✅ Файлы загружены!")