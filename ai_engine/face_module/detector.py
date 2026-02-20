import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python import BaseOptions
import os
import numpy as np
import base64
from io import BytesIO
from PIL import Image as PILImage
from facenet_pytorch import MTCNN, InceptionResnetV1
import torch

# Setting up paths and options
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.abspath(os.path.join(BASE_DIR, "..", "face_module/models", "blaze_face_short_range.tflite"))

print("MODEL PATH:", model_path)
print("FILE EXISTS:", os.path.exists(model_path))

# Load model
options = vision.FaceDetectorOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=vision.RunningMode.IMAGE
)

detector = vision.FaceDetector.create_from_options(options)

# Initialize MTCNN and InceptionResnetV1 for FaceNet embeddings
mtcnn = MTCNN(keep_all=True)  # Multi-face detection
inception_resnet = InceptionResnetV1(pretrained='vggface2').eval()

cap = cv2.VideoCapture(0)

def faceDetection():
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = detector.detect(mp_image)

        count = len(result.detections)
        present = count > 0

        if present:
            print("Face Detected, Count:", count)
            for detection in result.detections:
                bbox = detection.location_data.relative_bounding_box
                h, w, _ = frame.shape
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                width = int(bbox.width * w)
                height = int(bbox.height * h)

                # Crop the detected face region
                face_image = frame[y:y+height, x:x+width]

                # Convert the face image to PIL format for further processing or saving
                pil_img = PILImage.fromarray(face_image)

                # Save the cropped face image
                face_image_path = "detected_face.jpg"
                pil_img.save(face_image_path)

                # Generate FaceNet embedding for the detected face
                # Convert to RGB for FaceNet
                face_tensor = torch.from_numpy(np.moveaxis(face_image, -1, 0)).float()  # CHW format
                face_tensor /= 255.0  # Normalize

                # Detect face and get embeddings
                faces, probs = mtcnn.detect(face_image)  # Detect faces in the cropped face image
                if faces is not None and len(faces) > 0:
                    # Extract embeddings
                    embedding = inception_resnet(faces)  # Get the embedding of the detected face
                    embedding = embedding.detach().cpu().numpy().flatten()  # Convert to numpy array

                    # Optionally, send the embedding (you can use it for face recognition)
                    print("Face Embedding:", embedding)

                    # Convert embedding to base64 to send via an API
                    embedding_base64 = base64.b64encode(embedding.tobytes()).decode('utf-8')

                    # Create a response with the embedding and image base64
                    buffered = BytesIO()
                    pil_img.save(buffered, format="JPEG")
                    face_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

                    # Return the response with both embedding and image
                    return {
                        "message": "Face Detected",
                        "image_base64": face_base64,
                        "embedding_base64": embedding_base64
                    }

        # Show the video stream
        cv2.imshow("frame", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # Press Esc to exit
            break

    cap.release()
    cv2.destroyAllWindows()

# Example call to faceDetection function
face_detection_result = faceDetection()
print(face_detection_result)