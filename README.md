
# Project Title

A brief description of what this project does and who it's for


# AI-Based Intelligent Online Exam Proctoring System

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.10-red)](https://pytorch.org/)

> **A production-ready AI-powered system for automated online exam monitoring that detects suspicious activities like multiple faces, phone usage, abnormal head movement, background noise, and browser violations with real-time alerts.**

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Quick Start](#-quick-start)
- [API Endpoints](#-api-endpoints)
- [AI Engine Flow](#-ai-engine-flow)
- [Database Schema](#-database-schema)
- [WebSocket Integration](#-websocket-integration)
- [Development Guide](#-development-guide)
- [Contributing](#-contributing)
- [License](#-license)
- [Support & Contact](#-support--contact)
- [Acknowledgments](#-acknowledgments)

---

## 📖 Overview

The **AI-Based Intelligent Online Exam Proctoring System** is a comprehensive solution for monitoring online exams using artificial intelligence and machine learning. It automatically detects suspicious behaviors and maintains exam integrity through:

- **Real-time monitoring** via webcam and audio
- **Multi-modal AI detection** (face, pose, objects, audio)
- **Risk scoring engine** for threat assessment
- **WebSocket live updates** to proctors
- **Session management** with auto-termination
- **Comprehensive audit logs** for review

### Use Cases

| Icon | Use Case | Description |
|------|----------|-------------|
| ✅ | **Educational Institutions** | Secure online examinations |
| ✅ | **Certification Programs** | Credential verification |
| ✅ | **Recruitment** | Fair hiring assessments |
| ✅ | **Remote Assessments** | Compliance testing |

---

## 🎯 Key Features

### 🔍 Multi-Modal Detection

| Module | Detection | Action |
|--------|-----------|--------|
| **Face Recognition** | No face, multiple faces, identity mismatch | Alert, terminate |
| **Head Pose** | Abnormal head movement, looking away | Log violation |
| **Object Detection** | Phone, secondary devices, restricted items | Alert, log |
| **Audio Analysis** | Background noise, communication attempts | Log, alert |
| **Behavior Analysis** | Pattern anomalies, coordinated violations | Risk escalation |

### ⚡ Real-Time Processing

- **10–15 FPS** frame processing
- **<100ms** latency per frame
- **WebSocket** live alert delivery
- **Background worker** thread for continuous monitoring

### 🛡️ Security & Integrity

- Face embedding verification (re-verify every 60s)
- Session identity confirmation
- Violation logging with timestamps
- Risk-based auto-termination
- Audit trail for compliance

### 📊 Admin Dashboard

- Live exam monitoring
- Risk score visualization
- Violation history review
- Session analytics
- Detailed incident reports

---

## 🏗️ Architecture

The system is organized into clean, well-separated layers — from the AI engine to the API, database, and frontend.

```
ai-proctoring-system/
├── main.py                        # FastAPI application entry point
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project configuration
│
├── core/                          # Core configuration
│   ├── config.py                  # Settings & environment variables
│   └── logging_config.py          # Logging setup
│
├── ai_engine/                     # AI Detection Modules
│   ├── logger.py
│   ├── face_module/
│   │   ├── detector.py            # Face detection (MediaPipe)
│   │   └── recognizer.py          # Face recognition (FaceNet)
│   ├── head_pose_module/
│   │   └── pose_estimator.py
│   ├── object_detector/
│   │   └── yolo_detector.py
│   ├── behaviour_module/
│   │   └── anomaly_detector.py
│   ├── audio_module/
│   │   └── vad.py
│   └── risk_engine/
│       └── scoring.py
│
├── api/
│   └── v1/
│       ├── auth.py
│       ├── exam.py
│       ├── monitoring.py
│       └── reports.py
│
├── db/
│   ├── session.py
│   ├── models.py
│ 
│
├── services/
│   ├── report_services.py
│   
├── workers/
│   └── video_worker.py
│
├── schemas/
│   ├── auth_schema.py
│   
│
├── tools/
│   └── enroll_facepy
│
├── frontend/                      # React Dashboard
├── storage/                       # Runtime Storage
├── logs/                          # Application logs
└── models/                        # Downloaded AI model weights
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11+> <3.12 , FastAPI, SQLAlchemy |
| **AI / ML** | PyTorch, MediaPipe, YOLO, FaceNet |
| **Database** | PostgreSQL 12+ |
| **Frontend** | React.js, WebSockets |

---

## 🚀 Installation

### Prerequisites

- Python 3.11 or later
- PostgreSQL 12 or later
- CUDA 12 (optional, for GPU acceleration)
- Webcam & Microphone

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Sudhanshu3011/ai-proctoring-system.git
cd ai-proctoring-system

# 2. Create and activate a virtual environment
python3.11 -m venv venv
source venv/bin/activate          # On Windows: venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Set up PostgreSQL database
createdb ai_proctoring
psql -d ai_proctoring -c "SELECT 1;"

# 5. Initialize database tables
python -m db.session
```

---

## ⚙️ Configuration

Create a `.env` file in the root of the project with the following variables:

```env
# ─── Database ────────────────────────────────────────────
DATABASE_URL=postgresql://username:password@localhost:5432/ai_proctoring

# ─── FastAPI ─────────────────────────────────────────────
APP_NAME=AI Proctoring System
APP_ENV=development
APP_DEBUG=True
APP_HOST=0.0.0.0
APP_PORT=8000

# ─── Security ────────────────────────────────────────────
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ─── AI Engine Thresholds ────────────────────────────────
FACE_DETECTION_CONFIDENCE=0.7
POSE_THRESHOLD=30
OBJECT_DETECTION_CONFIDENCE=0.5
RISK_AUTO_TERMINATE_THRESHOLD=85

# ─── Storage Paths ───────────────────────────────────────
STORAGE_PATH=./storage
LOG_PATH=./storage/logs
MODEL_PATH=./storage/models
```

> Core configuration is handled in `core/config.py` using **Pydantic Settings**.

---

## 🎬 Quick Start

```bash
# Start PostgreSQL (macOS/Linux)
brew services start postgresql

# Or with Docker
docker run -d \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:15

# Start the application server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Once running, access the following:

| Interface | URL |
|-----------|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **Health Check** | http://localhost:8000/health |

---

## 📡 API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register a new user |
| `POST` | `/api/v1/auth/login` | User login |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Get current user info |

### Exam Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/exam/start` | Start an exam session |
| `GET` | `/api/v1/exam/{session_id}` | Get session information |
| `POST` | `/api/v1/exam/{session_id}/end` | End an exam session |
| `GET` | `/api/v1/exam/{session_id}/violations` | Get list of violations |

### Real-Time Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/monitoring/frame` | Submit a video frame |
| `GET` | `/api/v1/monitoring/{session_id}/status` | Get monitoring status |
| `WS` | `/ws/monitor/{session_id}` | WebSocket live updates |

---

## 🧠 AI Engine Flow

### Visual AI Pipeline

```
       ┌───────────────────┐
       │    Video Frame     │
       └────────┬──────────┘
                │
     ┌──────────▼──────────┐
     │    Face Detection    │
     │  (MediaPipe/FaceNet) │
     └───┬──────────────┬───┘
         │              │
    No Face           Multiple Faces
    [ALERT]           [ALERT]
         │              │
         └──────┬───────┘
                │
     ┌──────────▼──────────┐
     │  Head Pose Estimator │
     │    (Gaze / Look)     │
     └──────────┬──────────┘
                │
           Looking Away
            [LOG]
                │
     ┌──────────▼──────────┐
     │   Object Detection   │
     │   (Phones / Items)   │
     └──────────┬──────────┘
                │
           Object Found
            [ALERT]
                │
     ┌──────────▼──────────┐
     │    Audio Analysis    │
     │    (VAD / Noise)     │
     └──────────┬──────────┘
                │
          Noise Detected
            [ALERT]
                │
     ┌──────────▼──────────┐
     │  Behavior / Anomaly  │
     │       Detection      │
     └──────────┬──────────┘
                │
     ┌──────────▼──────────┐
     │     Risk Scoring     │
     │     Aggregation      │
     └──────────┬──────────┘
                │
         Threshold ≥ 85
                │
     ┌──────────▼──────────┐
     │    Auto-Terminate    │
     │       Session        │
     └─────────────────────┘
```

### Detection Pipeline 

```python
def _process_frame(frame):
    violations = []

    # Step 1: Face Detection
    faces = detect_faces(frame)
    if len(faces) == 0:
        violations.append("FACE_ABSENT")
    elif len(faces) > 1:
        violations.append("MULTI_FACE")

    # Step 2: Head Pose Estimation
    pose = estimate_pose(frame)
    if pose.abnormal:
        violations.append("LOOKING_AWAY")

    # Step 3: Object Detection (every 3rd frame for performance)
    if frame_count % 3 == 0:
        objects = detect_objects(frame)
        for obj in objects:
            violations.append(f"{obj.type}_DETECTED")

    # Step 4: Behavior Anomaly Detection
    anomalies = detect_anomalies(violations, history)

    # Step 5: Risk Score Calculation
    risk_score = calculate_risk(violations, anomalies)

    # Step 6: Auto-terminate if threshold exceeded
    if risk_score >= THRESHOLD:
        terminate_session()

    return risk_score, violations
```

---

## 📊 Database Schema

### Users Table

```sql
CREATE TABLE users (
    id           UUID         PRIMARY KEY,
    email        VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name    VARCHAR(255),
    created_at   TIMESTAMP    DEFAULT NOW(),
    updated_at   TIMESTAMP    DEFAULT NOW()
);
```

### Exam Sessions Table

```sql
CREATE TABLE exam_sessions (
    id               UUID      PRIMARY KEY,
    user_id          UUID      REFERENCES users(id),
    exam_name        VARCHAR(255) NOT NULL,
    status           ENUM('ACTIVE', 'COMPLETED', 'TERMINATED', 'PAUSED'),
    start_time       TIMESTAMP NOT NULL,
    end_time         TIMESTAMP,
    duration_minutes INTEGER,
    created_at       TIMESTAMP DEFAULT NOW()
);
```

### Violations Table

```sql
CREATE TABLE violations (
    id             UUID         PRIMARY KEY,
    session_id     UUID         REFERENCES exam_sessions(id),
    violation_type VARCHAR(50)  NOT NULL,
    weight         INTEGER,
    confidence     FLOAT,
    timestamp      TIMESTAMP    DEFAULT NOW(),
    description    TEXT
);
```

### Risk Scores Table

```sql
CREATE TABLE risk_scores (
    id            UUID  PRIMARY KEY,
    session_id    UUID  REFERENCES exam_sessions(id),
    current_score FLOAT NOT NULL,
    risk_level    ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'),
    updated_at    TIMESTAMP DEFAULT NOW()
);
```

---

## 🔌 WebSocket Integration

### Client Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/monitor/session-id');

ws.onopen  = () => console.log('Connected to proctoring stream');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Violation detected:', data.violation_type);
    console.log('Risk Score:', data.risk_score);
};

ws.onerror = (error) => console.error('WebSocket error:', error);
ws.onclose = ()      => console.log('Disconnected from stream');
```

### Message Format

```json
{
    "session_id":       "uuid",
    "timestamp":        "2024-03-27T10:30:45Z",
    "event_type":       "violation",
    "violation_type":   "MULTI_FACE",
    "confidence":       0.95,
    "risk_score":       42.5,
    "risk_level":       "MEDIUM",
    "should_terminate": false,
    "details": {
        "frame_count":    1250,
        "processing_ms":  45
    }
}
```