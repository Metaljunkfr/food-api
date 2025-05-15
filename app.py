import io
import os
import requests
from jobs import jobs, start_job
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO

app = FastAPI()

# ==================== DOWNLOAD & LOAD YOLO MODEL ====================
MODEL_PATH = "models/yolov8_food.pt"
if not os.path.exists(MODEL_PATH):
    print("📦 Downloading YOLO model...")
    os.makedirs("models", exist_ok=True)
    url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
    response = requests.get(url, stream=True)
    with open(MODEL_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    print("✅ YOLO model downloaded!")

model = YOLO(MODEL_PATH)

# ==================== IMAGE UPLOAD ENDPOINT ====================
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        print(f"🖼️ Fichier reçu : {file.filename} ({len(contents)} octets)")

        if not contents:
            return JSONResponse(content={"error": "Fichier vide"}, status_code=400)

        try:
            image = Image.open(io.BytesIO(contents))
            image.verify()
            image = Image.open(io.BytesIO(contents))  # Recharge utilisable
        except UnidentifiedImageError:
            return JSONResponse(content={"error": "Format de l'image non reconnu"}, status_code=400)

        print(f"✅ Image décodée : {image.format}, {image.size}, {image.mode}")

        job_id = start_job(image, model, get_nutrition)
        return {"job_id": job_id}

    except Exception as e:
        print("❌ Erreur serveur :", str(e))
        return JSONResponse(content={"error": "Erreur interne du serveur"}, status_code=500)

# ==================== JOB RESULT ENDPOINT ====================
@app.get("/result/{job_id}")
async def get_result(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(content={"error": "ID inconnu"}, status_code=404)

    if job["status"] == "done":
        return job["result"]
    elif job["status"] == "processing":
        return {"status": "processing"}
    else:
        return JSONResponse(content={"error": job.get("message", "Erreur inconnue")}, status_code=500)

# ==================== NUTRITION LOOKUP FUNCTIONS ====================
def get_nutrition(food_name):
    print(f"🔍 Recherche nutrition pour : {food_name}")
    nutrition = fetch_openfoodfacts(food_name)
    if not nutrition:
        print("⚠️ OpenFoodFacts n'a rien trouvé, on tente USDA...")
        nutrition = fetch_usda(food_name)
    return nutrition if nutrition else {
        "calories": "Unknown",
        "protein": "Unknown",
        "carbs": "Unknown",
        "fat": "Unknown"
    }

def fetch_openfoodfacts(food_name):
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": food_name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 10
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        products = data.get("products", [])
        for product in products:
            nutrients = product.get("nutriments", {})
            if "energy-kcal_100g" in nutrients:
                print(f"✅ Nutriments trouvés via OFF : {product.get('product_name', 'Inconnu')}")
                return {
                    "calories": nutrients.get("energy-kcal_100g", "Unknown"),
                    "protein": nutrients.get("proteins_100g", "Unknown"),
                    "carbs": nutrients.get("carbohydrates_100g", "Unknown"),
                    "fat": nutrients.get("fat_100g", "Unknown")
                }
    except Exception as e:
        print(f"❌ Erreur OpenFoodFacts : {e}")
    return None

def fetch_usda(food_name):
    USDA_API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
    USDA_API_KEY = "cUpQEPw6MoVYHor57x8C3mX1ob1ANENgiWfkCYcZ"
    try:
        params = {"query": food_name, "api_key": USDA_API_KEY}
        response = requests.get(USDA_API_URL, params=params)
        data = response.json()
        foods = data.get("foods", [])
        if foods:
            nutrients = foods[0].get("foodNutrients", [])
            print(f"✅ Nutriments trouvés via USDA : {foods[0].get('description', 'Inconnu')}")
            return {
                "calories": find_nutrient(nutrients, 208),
                "protein": find_nutrient(nutrients, 203),
                "carbs": find_nutrient(nutrients, 205),
                "fat": find_nutrient(nutrients, 204)
            }
    except Exception as e:
        print(f"❌ Erreur USDA : {e}")
    return None

def find_nutrient(nutrients, nutrient_id):
    for nutrient in nutrients:
        if nutrient.get("nutrientId") == nutrient_id:
            return nutrient.get("value", "Unknown")
    return "Unknown"

# ==================== START SERVER ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
