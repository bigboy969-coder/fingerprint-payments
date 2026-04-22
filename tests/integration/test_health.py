"""Integration tests for health endpoints."""


class TestHealth:
    def test_healthz(self, client):
        res = client.get("/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_readyz(self, client):
        res = client.get("/readyz")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_request_id_header(self, client):
        res = client.get("/healthz")
        assert "x-request-id" in res.headers

    def test_security_headers(self, client):
        res = client.get("/healthz")
        assert res.headers["x-frame-options"] == "DENY"
        assert res.headers["x-content-type-options"] == "nosniff"
        assert "content-security-policy" in res.headers

    def test_config_endpoint(self, client):
        res = client.get("/config")
        assert res.status_code == 200
        assert "publishable_key" in res.json()
