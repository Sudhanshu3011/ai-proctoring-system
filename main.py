from fastapi import FastAPI
from ai_engine.face_module.detector import faceDetection

app = FastAPI()

@app.get("/")
def home():
    return {"message": "AI Proctoring System Running"}

@app.get("/face_detection")
def face_detection():
    # Call faceDetection function
    response = faceDetection()

    # If faceDetection already returns a dictionary, we can directly return it
    if isinstance(response, dict):
        return response

    # If the response is not a dictionary or serializable, we can attempt to serialize
    try:
        # FastAPI automatically serializes dictionaries to JSON, no need to use json.dumps() or json.loads().
        return response
    except Exception as e:
        # In case the response cannot be serialized
        return {"error": "Failed to serialize the response", "details": str(e)}