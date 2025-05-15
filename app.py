import io
import os
import requests
from jobs import jobs, start_job
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO
from config import *
from logger import logger
from tenacity import retry, stop_after_attempt, wait_exponential

app = FastAPI(title="Food API", version="1.0.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== DOWNLOAD & LOAD YOLO MODEL ====================
if not os.path.exists(MODEL_PATH):
    logger.info("📦 Téléchargement du modèle YOLO...")
    os.makedirs("models", exist_ok=True)
    response = requests.get(MODEL_URL, stream=True)
    with open(MODEL_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    logger.info("✅ Modèle YOLO téléchargé!")

model = YOLO(MODEL_PATH)

# ==================== IMAGE UPLOAD ENDPOINT ====================
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    try:
        # Vérification de la taille du fichier
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux")

        logger.info(f"🖼️ Fichier reçu : {file.filename} ({len(contents)} octets)")

        if not contents:
            raise HTTPException(status_code=400, detail="Fichier vide")

        # Vérification du type MIME
        content_type = file.content_type
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=415, detail="Format de fichier non supporté")

        try:
            image = Image.open(io.BytesIO(contents))
            image.verify()
            image = Image.open(io.BytesIO(contents))
        except UnidentifiedImageError:
            raise HTTPException(status_code=400, detail="Format de l'image non reconnu")

        logger.info(f"✅ Image décodée : {image.format}, {image.size}, {image.mode}")

        job_id = start_job(image, model, get_nutrition)
        return {"job_id": job_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ Erreur serveur : {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")

# ==================== JOB RESULT ENDPOINT ====================
@app.get("/result/{job_id}")
async def get_result(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ID inconnu")

    if job["status"] == "done":
        return job["result"]
    elif job["status"] == "processing":
        return {"status": "processing"}
    else:
        raise HTTPException(status_code=500, detail=job.get("message", "Erreur inconnue"))

# ==================== NUTRITION LOOKUP FUNCTIONS ====================
def get_nutrition(food_name):
    logger.info(f"🔍 Recherche nutrition pour : {food_name}")
    nutrition = fetch_openfoodfacts(food_name)
    if not nutrition:
        logger.warning("⚠️ OpenFoodFacts n'a rien trouvé, on tente USDA...")
        nutrition = fetch_usda(food_name)
    return nutrition if nutrition else {
        "calories": "Unknown",
        "protein": "Unknown",
        "carbs": "Unknown",
        "fat": "Unknown"
    }

@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(multiplier=RETRY_DELAY))
def fetch_openfoodfacts(food_name):
    try:
        params = {
            "search_terms": food_name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 10
        }
        response = requests.get(
            OPENFOODFACTS_URL,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        products = data.get("products", [])
        for product in products:
            nutrients = product.get("nutriments", {})
            if "energy-kcal_100g" in nutrients:
                logger.info(f"✅ Nutriments trouvés via OFF : {product.get('product_name', 'Inconnu')}")
                return {
                    "calories": nutrients.get("energy-kcal_100g", "Unknown"),
                    "protein": nutrients.get("proteins_100g", "Unknown"),
                    "carbs": nutrients.get("carbohydrates_100g", "Unknown"),
                    "fat": nutrients.get("fat_100g", "Unknown")
                }
    except Exception as e:
        logger.error(f"❌ Erreur OpenFoodFacts : {e}")
    return None

@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(multiplier=RETRY_DELAY))
def fetch_usda(food_name):
    try:
        params = {
            "query": food_name,
            "api_key": USDA_API_KEY
        }
        response = requests.get(
            USDA_API_URL,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        foods = data.get("foods", [])
        if foods:
            nutrients = foods[0].get("foodNutrients", [])
            logger.info(f"✅ Nutriments trouvés via USDA : {foods[0].get('description', 'Inconnu')}")
            return {
                "calories": find_nutrient(nutrients, 208),
                "protein": find_nutrient(nutrients, 203),
                "carbs": find_nutrient(nutrients, 205),
                "fat": find_nutrient(nutrients, 204)
            }
    except Exception as e:
        logger.error(f"❌ Erreur USDA : {e}")
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
