"""Integration tests for the enrollment flow: session → form → scan → verify."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "images"
TEST_IMAGE = FIXTURES_DIR / "test_fingerprint.png"


class TestEnrollmentSession:
    def test_create_session(self, client):
        res = client.post("/enroll/session")
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "enroll_url" in data

    def test_poll_status_pending(self, client):
        session = client.post("/enroll/session").json()
        res = client.get(f"/enroll/status/{session['session_id']}")
        assert res.status_code == 200
        assert res.json()["status"] == "pending_form"

    def test_status_404_for_unknown_session(self, client):
        res = client.get("/enroll/status/nonexistent-uuid")
        assert res.status_code == 404


class TestEnrollmentStart:
    def test_start_moves_to_pending_scan(self, client, stripe_stub):
        session = client.post("/enroll/session").json()
        res = client.post(
            "/enroll/start",
            json={
                "session_id": session["session_id"],
                "full_name": "Test User",
                "email": "enroll@test.com",
                "phone": "+1234567890",
                "stripe_payment_method_id": "pm_test_123",
            },
        )
        assert res.status_code == 200

        # Status should now be pending_scan
        status = client.get(f"/enroll/status/{session['session_id']}").json()
        assert status["status"] == "pending_scan"

    def test_start_rejects_duplicate_email(self, client, stripe_stub):
        # First enrollment
        s1 = client.post("/enroll/session").json()
        client.post(
            "/enroll/start",
            json={
                "session_id": s1["session_id"],
                "full_name": "First",
                "email": "unique@test.com",
                "stripe_payment_method_id": "pm_test_1",
            },
        )
        # Complete it with a dummy template (base64-encoded zeros)
        import base64

        dummy_template = base64.b64encode(b"\x00" * 1632).decode()
        client.post(
            f"/enroll/complete/{s1['session_id']}",
            json={"template": dummy_template},
        )

        # Second attempt with same email
        s2 = client.post("/enroll/session").json()
        res = client.post(
            "/enroll/start",
            json={
                "session_id": s2["session_id"],
                "full_name": "Second",
                "email": "unique@test.com",
                "stripe_payment_method_id": "pm_test_2",
            },
        )
        assert res.status_code == 400
        # Generic message — no email enumeration
        assert "enrolled" not in res.json()["detail"].lower()


class TestEnrollmentComplete:
    @pytest.mark.skipif(not TEST_IMAGE.exists(), reason="test_fingerprint.png not in fixtures")
    def test_complete_enrollment(self, client, stripe_stub):
        # Create session + submit form
        session = client.post("/enroll/session").json()
        client.post(
            "/enroll/start",
            json={
                "session_id": session["session_id"],
                "full_name": "Complete User",
                "email": "complete@test.com",
                "stripe_payment_method_id": "pm_test_complete",
            },
        )

        # Complete with dummy template bytes
        import base64

        dummy_template = base64.b64encode(b"\x00" * 1632).decode()
        res = client.post(
            f"/enroll/complete/{session['session_id']}",
            json={"template": dummy_template},
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert "user" in res.json()

    def test_complete_before_form_rejects(self, client):
        import base64

        session = client.post("/enroll/session").json()
        dummy_template = base64.b64encode(b"\x00" * 1632).decode()
        res = client.post(
            f"/enroll/complete/{session['session_id']}",
            json={"template": dummy_template},
        )
        assert res.status_code == 400
