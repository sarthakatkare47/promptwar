import pytest


def test_scorecard_api_not_run_initially(client):
    res = client.get("/api/scorecard")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("not_run", "ok")
    if data["status"] == "not_run":
        assert "message" in data
