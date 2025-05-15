import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
USDA_API_KEY = os.getenv('USDA_API_KEY', 'cUpQEPw6MoVYHor57x8C3mX1ob1ANENgiWfkCYcZ')

# Model Configuration
MODEL_PATH = "models/yolov8_food.pt"
MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"

# API Configuration
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp']

# External API Configuration
OPENFOODFACTS_URL = "https://world.openfoodfacts.org/cgi/search.pl"
USDA_API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# Request Configuration
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds 