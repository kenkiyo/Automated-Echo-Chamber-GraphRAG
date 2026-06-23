import requests

url = "https://openrouter.ai/api/v1/models"
print("Mencari model gratis yang aktif di OpenRouter...\n")

response = requests.get(url)

if response.status_code == 200:
    models = response.json().get('data', [])
    
    # Memfilter model yang harga prompt dan completion-nya 0
    free_models = [
        model['id'] for model in models 
        if float(model.get('pricing', {}).get('prompt', 1)) == 0.0 
        and float(model.get('pricing', {}).get('completion', 1)) == 0.0
    ]
    
    print("=== COPY SALAH SATU ID MODEL INI ===")
    for i, model_id in enumerate(free_models[:15]): # Menampilkan 15 teratas
        print(f"{i+1}. {model_id}")
else:
    print(f"Gagal mengambil daftar model. Status: {response.status_code}")