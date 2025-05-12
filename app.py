import io
import os
import requests
from fastapi import FastAPI, File, UploadFile
from ultralytics import YOLO
from PIL import Image

# Initialize FastAPI app
app = FastAPI()

# ==================== DOWNLOAD & LOAD YOLO MODEL ====================
MODEL_PATH = "models/yolov8_food.pt"
if not os.path.exists(MODEL_PATH):
    print("Downloading YOLO model...")
    os.makedirs("models", exist_ok=True)
    url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
    response = requests.get(url, stream=True)
    with open(MODEL_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    print("YOLO model downloaded!")

model = YOLO(MODEL_PATH)

# ==================== IMAGE UPLOAD ENDPOINT ====================
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    image = Image.open(io.BytesIO(await file.read()))
    results = model(image)
    detected_foods = set()

    for result in results:
        for box in result.boxes:
            detected_foods.add(result.names[int(box.cls)])

    if not detected_foods:
        return {"error": "No food detected"}

    nutrition_info = {}
    for food in detected_foods:
        nutrition_info[food] = get_nutrition(food)

    return {"foods_detected": list(detected_foods), "nutrition_info": nutrition_info}

# ==================== NUTRITION LOOKUP FUNCTIONS ====================
def get_nutrition(food_name):
    nutrition = fetch_openfoodfacts(food_name)
    if not nutrition:
        nutrition = fetch_usda(food_name)
    return nutrition if nutrition else {"calories": "Unknown", "protein": "Unknown", "carbs": "Unknown", "fat": "Unknown"}

def fetch_openfoodfacts(food_name):
    """Query OpenFoodFacts live API"""
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": food_name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 1
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "products" in data and data["products"]:
            product = data["products"][0]
            return {
                "calories": product.get("energy-kcal_100g", "Unknown"),
                "protein": product.get("proteins_100g", "Unknown"),
                "carbs": product.get("carbohydrates_100g", "Unknown"),
                "fat": product.get("fat_100g", "Unknown")
            }
    except Exception:
        pass
    return None

def fetch_usda(food_name):
    """Query USDA API with fallback"""
    USDA_API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
    USDA_API_KEY = "cUpQEPw6MoVYHor57x8C3mX1ob1ANENgiWfkCYcZ"
    try:
        params = {"query": food_name, "api_key": USDA_API_KEY}
        response = requests.get(USDA_API_URL, params=params)
        data = response.json()
        if "foods" in data and data["foods"]:
            nutrients = data["foods"][0]["foodNutrients"]
            return {
                "calories": find_nutrient(nutrients, 208),
                "protein": find_nutrient(nutrients, 203),
                "carbs": find_nutrient(nutrients, 205),
                "fat": find_nutrient(nutrients, 204)
            }
    except Exception:
        pass
    return None

def find_nutrient(nutrients, nutrient_id):
    for nutrient in nutrients:
        if nutrient["nutrientId"] == nutrient_id:
            return nutrient.get("value", "Unknown")
    return "Unknown"

# ==================== START SERVER ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
