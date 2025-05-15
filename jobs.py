# jobs.py
import uuid
from threading import Thread

jobs = {}

def start_job(image, model, get_nutrition):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing", "result": None}

    def process():
        try:
            results = model(image)
            detected_foods = set()
            for result in results:
                for box in result.boxes:
                    detected_foods.add(result.names[int(box.cls)])
            nutrition_info = {}
            for food in detected_foods:
                nutrition_info[food] = get_nutrition(food)
            jobs[job_id] = {"status": "done", "result": {
                "foods_detected": list(detected_foods),
                "nutrition_info": nutrition_info
            }}
        except Exception as e:
            jobs[job_id] = {"status": "error", "message": str(e)}

    Thread(target=process).start()
    return job_id
