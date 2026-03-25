"""
tools/enroll_face.py

Standalone face enrollment script — run this ONCE per student
before they can start an exam.

What it does:
    1. Opens webcam
    2. Runs detector.py to capture a live face + liveness check
    3. Generates 512-d FaceNet embedding
    4. POSTs it to POST /api/v1/auth/enroll-face
    5. Server stores embedding in User.face_embedding column
    6. Server registers it in FaceRecognizer singleton

Run:
    python tools/enroll_face.py --email student@test.com --token YOUR_JWT_TOKEN

Or run without args to be prompted interactively:
    python tools/enroll_face.py
"""

import os
import sys
import argparse
import requests
import json

# Make sure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "xcb"

from ai_engine.face_module.detector import faceDetection
from ai_engine.logger import get_logger

logger = get_logger("enroll_face")

BASE_URL = "http://localhost:8000"


def enroll(email: str, token: str):
    print(f"\n── Face Enrollment for {email} ─────────────────────")
    print("Look at the camera. Blink once to confirm liveness.\n")

    # ── Step 1: Capture face via detector.py ──────────────────────
    result = faceDetection()

    if not result:
        print("ERROR: Could not detect a live face. Try again.")
        return False

    print(f"Face captured. Embedding length: "
          f"{len(result['embedding_base64'])} chars")

    # ── Step 2: POST to enrollment endpoint ───────────────────────
    payload = {
        "embedding_base64" : result["embedding_base64"],
        "face_image_base64": result["image_base64"],
    }

    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/enroll-face",
        json    = payload,
        headers = {"Authorization": f"Bearer {token}"},
    )

    if resp.status_code == 200:
        data = resp.json()
        print(f"\nEnrollment successful!")
        print(f"  User     : {data.get('email')}")
        print(f"  Message  : {data.get('message')}")
        print("\nYou can now start exams.")
        return True
    else:
        print(f"\nEnrollment failed: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enroll face for exam proctoring")
    parser.add_argument("--email", type=str, help="Student email")
    parser.add_argument("--token", type=str, help="JWT token from /login")
    args = parser.parse_args()

    email = args.email or input("Enter your email: ").strip()
    token = args.token or input("Paste your JWT token: ").strip()

    enroll(email, token)