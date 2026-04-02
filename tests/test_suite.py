"""
tests/test_suite.py

Complete pytest test suite for ProctorAI.

Covers:
  - AI module unit tests (no server needed)
  - API integration tests (needs running server)
  - Database tests (needs PostgreSQL)

Run all:
    pytest tests/test_suite.py -v

Run only unit tests (no server):
    pytest tests/test_suite.py -v -m unit

Run only API tests:
    pytest tests/test_suite.py -v -m api

Install:
    pip install pytest pytest-asyncio httpx
"""

import pytest
import time
import numpy as np
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════
#  UNIT TESTS — AI Modules (no server, no DB)
# ═══════════════════════════════════════════════════════════════════

class TestRiskScoring:
    """Tests for risk_engine/scoring.py"""

    @pytest.mark.unit
    def test_normalise_zero(self):
        from ai_engine.risk_engine.scoring import RiskScorer
        scorer = RiskScorer(session_id="test")
        assert scorer.current_score() == 0.0

    @pytest.mark.unit
    def test_direct_violation_raises_score(self):
        from ai_engine.risk_engine.scoring import RiskScorer
        scorer = RiskScorer(session_id="test")
        score  = scorer.add_violation_direct("TAB_SWITCH", confidence=1.0)
        assert score > 0.0

    @pytest.mark.unit
    def test_phone_detection_higher_than_tab_switch(self):
        from ai_engine.risk_engine.scoring import RiskScorer
        s1 = RiskScorer(session_id="t1")
        s2 = RiskScorer(session_id="t2")
        s1.add_violation_direct("PHONE_DETECTED", 1.0)
        s2.add_violation_direct("TAB_SWITCH",     1.0)
        assert s1.current_score() > s2.current_score()

    @pytest.mark.unit
    def test_risk_level_classification(self):
        from ai_engine.risk_engine.scoring import RiskScorer, RiskLevel
        scorer = RiskScorer(session_id="test")
        # Inject high score directly
        scorer._dynamic_score = 70.0
        assert scorer.current_level() == RiskLevel.HIGH

    @pytest.mark.unit
    def test_sigmoid_probability_at_threshold(self):
        from ai_engine.risk_engine.scoring import RiskScorer
        scorer = RiskScorer(session_id="test")
        # At score=55 (theta), probability should be ~0.5
        prob = scorer._sigmoid_probability(55.0)
        assert 0.45 < prob < 0.55

    @pytest.mark.unit
    def test_sigmoid_critical_score_high_probability(self):
        from ai_engine.risk_engine.scoring import RiskScorer
        scorer = RiskScorer(session_id="test")
        prob   = scorer._sigmoid_probability(90.0)
        assert prob > 0.90

    @pytest.mark.unit
    def test_sliding_window_dampens_spikes(self):
        from ai_engine.risk_engine.scoring import RiskScorer
        scorer = RiskScorer(session_id="test")
        # Single huge spike should not immediately hit 100
        scorer._dynamic_score = 0.0
        new_score = scorer._sliding_window(100.0)
        assert new_score < 100.0
        assert new_score > 0.0

    @pytest.mark.unit
    def test_session_summary_structure(self):
        from ai_engine.risk_engine.scoring import RiskScorer
        scorer  = RiskScorer(session_id="test_summary")
        scorer.add_violation_direct("TAB_SWITCH", 1.0)
        summary = scorer.get_session_summary()
        assert "final_score"      in summary
        assert "peak_score"       in summary
        assert "final_level"      in summary
        assert "cheat_probability" in summary
        assert "time_at_levels"   in summary


class TestAnomalyDetector:
    """Tests for behavior_module/anomaly_detector.py"""

    @pytest.mark.unit
    def test_empty_window_returns_zero(self):
        from ai_engine.behaviour_module.anomaly_detector import AnomalyDetector
        det    = AnomalyDetector()
        report = det.analyze()
        assert report.raw_behavior_score == 0.0
        assert report.events_in_window   == 0

    @pytest.mark.unit
    def test_single_event_registered(self):
        from ai_engine.behaviour_module.anomaly_detector import (
            AnomalyDetector, ViolationEvent
        )
        det = AnomalyDetector()
        det.add_event(ViolationEvent(
            "PHONE_DETECTED", time.time(), 40, 0.97, 0.0, "object"
        ))
        report = det.analyze()
        assert report.events_in_window       == 1
        assert report.raw_behavior_score     > 0.0
        assert report.session_total_violations == 1

    @pytest.mark.unit
    def test_frequency_anomaly_triggers(self):
        from ai_engine.behaviour_module.anomaly_detector import (
            AnomalyDetector, ViolationEvent
        )
        det = AnomalyDetector()
        # Add 12 look-aways (threshold = 10)
        for _ in range(12):
            det.add_event(ViolationEvent(
                "LOOKING_AWAY", time.time(), 15, 0.9, 2.0, "pose"
            ))
        report = det.analyze()
        assert report.has_frequency_anomaly  is True
        assert report.anomaly_multiplier     > 1.0

    @pytest.mark.unit
    def test_cooccurrence_anomaly_triggers(self):
        from ai_engine.behaviour_module.anomaly_detector import (
            AnomalyDetector, ViolationEvent
        )
        det = AnomalyDetector()
        now = time.time()
        # 3 different modules in same window = CRITICAL co-occurrence
        det.add_event(ViolationEvent("PHONE_DETECTED",  now, 40, 0.97, 0.0, "object"))
        det.add_event(ViolationEvent("SPEECH_BURST",    now, 10, 0.80, 1.5, "audio"))
        det.add_event(ViolationEvent("TAB_SWITCH",      now, 20, 1.00, 0.0, "browser"))
        report = det.analyze()
        assert report.has_cooccurrence_anomaly is True

    @pytest.mark.unit
    def test_module_stats_populated(self):
        from ai_engine.behaviour_module.anomaly_detector import (
            AnomalyDetector, ViolationEvent
        )
        det = AnomalyDetector()
        det.add_event(ViolationEvent("LOOKING_AWAY", time.time(), 15, 0.9, 2.0, "pose"))
        det.add_event(ViolationEvent("TAB_SWITCH",   time.time(), 20, 1.0, 0.0, "browser"))
        report = det.analyze()
        assert "pose"    in report.module_stats
        assert "browser" in report.module_stats

    @pytest.mark.unit
    def test_reset_clears_state(self):
        from ai_engine.behaviour_module.anomaly_detector import (
            AnomalyDetector, ViolationEvent
        )
        det = AnomalyDetector()
        det.add_event(ViolationEvent("TAB_SWITCH", time.time(), 20, 1.0, 0.0, "browser"))
        det.reset()
        report = det.analyze()
        assert report.events_in_window        == 0
        assert report.session_total_violations == 0


class TestFaceRecognizer:
    """Tests for face_module/recognizer.py"""

    @pytest.mark.unit
    def test_register_and_verify_same_person(self):
        from ai_engine.face_module.recognizer import FaceRecognizer
        rec = FaceRecognizer()
        emb = np.random.randn(512).astype(np.float32)
        rec.register("u1", "Test User", emb)
        # Same embedding — should verify
        result = rec.verify("u1", emb)
        assert result.matched         is True
        assert result.similarity      > 0.99

    @pytest.mark.unit
    def test_verify_different_person_fails(self):
        from ai_engine.face_module.recognizer import FaceRecognizer
        rec  = FaceRecognizer()
        emb1 = np.random.randn(512).astype(np.float32)
        emb2 = np.random.randn(512).astype(np.float32)
        rec.register("u1", "Test User", emb1)
        result = rec.verify("u1", emb2)
        assert result.matched is False

    @pytest.mark.unit
    def test_verify_unregistered_user(self):
        from ai_engine.face_module.recognizer import FaceRecognizer
        rec    = FaceRecognizer()
        emb    = np.random.randn(512).astype(np.float32)
        result = rec.verify("nonexistent", emb)
        assert result.matched is False
        assert result.label   == "NOT_REGISTERED"

    @pytest.mark.unit
    def test_session_reverify(self):
        from ai_engine.face_module.recognizer import FaceRecognizer
        rec  = FaceRecognizer()
        emb  = np.random.randn(512).astype(np.float32)
        # Slight variation — should still match
        emb2 = emb + np.random.randn(512).astype(np.float32) * 0.05
        rec.register("u1", "Test", emb)
        rec.start_session("sess1", "u1", emb)
        result = rec.reverify_session("sess1", emb2)
        assert result.matched is True

    @pytest.mark.unit
    def test_cosine_similarity_identical(self):
        from ai_engine.face_module.recognizer import FaceRecognizer
        a   = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        sim = FaceRecognizer.cosine_similarity(a, a)
        assert abs(sim - 1.0) < 1e-5

    @pytest.mark.unit
    def test_cosine_similarity_orthogonal(self):
        from ai_engine.face_module.recognizer import FaceRecognizer
        a   = np.array([1.0, 0.0], dtype=np.float32)
        b   = np.array([0.0, 1.0], dtype=np.float32)
        sim = FaceRecognizer.cosine_similarity(a, b)
        assert abs(sim) < 1e-5


class TestViolationWeights:
    """Verify all violation types have defined weights."""

    @pytest.mark.unit
    def test_all_violation_types_have_weights(self):
        from ai_engine.behaviour_module.anomaly_detector import VIOLATION_WEIGHTS
        from db.models import ViolationType
        for vt in ViolationType:
            assert vt.value in VIOLATION_WEIGHTS, (
                f"ViolationType.{vt.name} has no weight in VIOLATION_WEIGHTS"
            )

    @pytest.mark.unit
    def test_phone_has_highest_weight(self):
        from ai_engine.behaviour_module.anomaly_detector import VIOLATION_WEIGHTS
        assert VIOLATION_WEIGHTS["PHONE_DETECTED"] >= 40

    @pytest.mark.unit
    def test_all_weights_positive(self):
        from ai_engine.behaviour_module.anomaly_detector import VIOLATION_WEIGHTS
        for vtype, weight in VIOLATION_WEIGHTS.items():
            assert weight > 0, f"{vtype} has non-positive weight {weight}"


# ═══════════════════════════════════════════════════════════════════
#  API INTEGRATION TESTS (requires running server)
# ═══════════════════════════════════════════════════════════════════

BASE_URL = "http://localhost:8000/api/v1"


@pytest.fixture(scope="session")
def client():
    """HTTP client for API tests."""
    import httpx
    with httpx.Client(base_url=BASE_URL, timeout=30) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    """Register and login as admin — returns token."""
    client.post("/auth/register", json={
        "email":     "pytest_admin@test.com",
        "full_name": "Pytest Admin",
        "password":  "Test1234",
        "role":      "admin",
    })
    from urllib.parse import urlencode
    resp = client.post("/auth/login",
        content=urlencode({"username":"pytest_admin@test.com","password":"Test1234"}),
        headers={"Content-Type":"application/x-www-form-urlencoded"},
    )
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def student_token(client):
    """Register and login as student — returns token."""
    client.post("/auth/register", json={
        "email":     "pytest_student@test.com",
        "full_name": "Pytest Student",
        "password":  "Test1234",
        "role":      "student",
    })
    from urllib.parse import urlencode
    resp = client.post("/auth/login",
        content=urlencode({"username":"pytest_student@test.com","password":"Test1234"}),
        headers={"Content-Type":"application/x-www-form-urlencoded"},
    )
    return resp.json()["access_token"]


class TestAuthAPI:

    @pytest.mark.api
    def test_health(self, client):
        import httpx
        r = httpx.get("http://localhost:8000/health", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["app"]    == "AI Proctoring System"

    @pytest.mark.api
    def test_register_duplicate_fails(self, client):
        # Register first time
        client.post("/auth/register", json={
            "email":"dup@test.com","full_name":"Dup","password":"Test1234"
        })
        # Second time — should 409
        r = client.post("/auth/register", json={
            "email":"dup@test.com","full_name":"Dup","password":"Test1234"
        })
        assert r.status_code == 409

    @pytest.mark.api
    def test_login_wrong_password(self, client):
        from urllib.parse import urlencode
        r = client.post("/auth/login",
            content=urlencode({"username":"pytest_admin@test.com","password":"WRONG"}),
            headers={"Content-Type":"application/x-www-form-urlencoded"},
        )
        assert r.status_code == 401

    @pytest.mark.api
    def test_profile_requires_auth(self, client):
        r = client.get("/auth/profile")
        assert r.status_code == 401

    @pytest.mark.api
    def test_profile_with_token(self, client, student_token):
        r = client.get("/auth/profile",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert r.status_code == 200
        assert "email" in r.json()

    @pytest.mark.api
    def test_enroll_status_not_enrolled(self, client, student_token):
        r = client.get("/auth/enroll-status",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        assert "enrolled" in data


class TestExamAPI:

    @pytest.mark.api
    def test_student_cannot_create_exam(self, client, student_token):
        r = client.post("/exams/create",
            json={"title":"Test","duration_minutes":30},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert r.status_code == 403

    @pytest.mark.api
    def test_admin_creates_exam(self, client, admin_token):
        r = client.post("/exams/create",
            json={"title":"Pytest Exam","duration_minutes":30},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.json()["title"] == "Pytest Exam"

    @pytest.mark.api
    def test_list_exams(self, client, student_token):
        r = client.get("/exams/",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.api
    def test_start_exam_without_face_fails(self, client, student_token, admin_token):
        # Create exam
        exam = client.post("/exams/create",
            json={"title":"Face Required Test","duration_minutes":10},
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        # Start without face enrollment — should fail
        r = client.post(f"/exams/{exam['id']}/start",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert r.status_code == 400
        assert "face" in r.json()["detail"].lower()


class TestAdminAPI:

    @pytest.mark.api
    def test_dashboard_requires_admin(self, client, student_token):
        r = client.get("/admin/dashboard",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert r.status_code == 403

    @pytest.mark.api
    def test_dashboard_returns_summary(self, client, admin_token):
        r = client.get("/admin/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        assert "live_summary"    in data
        assert "total_users"     in data
        assert "active_sessions" in data

    @pytest.mark.api
    def test_live_sessions_empty_initially(self, client, admin_token):
        r = client.get("/admin/live-sessions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200
        assert "sessions" in r.json()
        assert "summary"  in r.json()


# ═══════════════════════════════════════════════════════════════════
#  Run config
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([
        __file__, "-v",
        "--tb=short",
        "-m", "unit",   # run only unit tests by default
    ])