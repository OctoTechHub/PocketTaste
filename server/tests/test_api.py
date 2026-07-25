"""API contract tests.

These run against the real app with no MongoDB configured, which pins two things:
the service starts and stays honest when its storage dependency is missing, and the
routes that need storage fail with a clear 503 instead of a stack trace.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture(scope="module")
def client(monkeypatch_session=None):
    import app.core.config as config

    offline = Settings(_env_file=None, DB_URL="", OPENAI_KEY="", OPENAI_API_KEY="", SARVAM_API_KEY="")
    config.get_settings.cache_clear()
    original = config.get_settings
    config.get_settings = lambda: offline  # type: ignore[assignment]

    import app.main as main_module

    main_module.get_settings = lambda: offline  # type: ignore[assignment]
    with TestClient(create_app()) as test_client:
        yield test_client

    config.get_settings = original  # type: ignore[assignment]
    main_module.get_settings = original  # type: ignore[assignment]
    config.get_settings.cache_clear()


def test_health_reports_degraded_without_storage(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["mongodb"]["connected"] is False


def test_health_discloses_the_active_embedding_backend(client):
    body = client.get("/health").json()
    assert body["dependencies"]["embeddings"]["backend"] == "hash-fallback"
    assert body["dependencies"]["llm"]["available"] is False


def test_architecture_endpoint_states_what_is_excluded_by_design(client):
    body = client.get("/system/architecture").json()
    assert "does not replace" in body["positioning"]
    assert any("fine-tuning" in item for item in body["excluded_by_design"])
    assert round(sum(body["ranking_weights"].values()), 6) == 1.0


def test_storage_backed_routes_return_503_not_500(client):
    for method, path, payload in [
        ("get", "/catalog", None),
        ("post", "/recommendations", {"user_id": "u1"}),
        ("get", "/insights/demand", None),
        ("post", "/pipeline/run", {}),
        ("get", "/analytics/user/u1", None),
    ]:
        response = getattr(client, method)(path, **({"json": payload} if payload else {}))
        assert response.status_code == 503, f"{method} {path} -> {response.status_code}"
        assert response.json()["error"]["code"] == "dependency_unavailable"


def test_authenticated_routes_are_declared_as_such_in_the_schema(client):
    """Every route that writes on someone's behalf must require a bearer token."""
    schema = client.get("/openapi.json").json()
    for path, method in [
        ("/activity", "post"),
        ("/activity/batch", "post"),
        ("/me/recommendations", "post"),
        ("/me/profile", "get"),
        ("/me/history", "get"),
        ("/catalog", "post"),
        ("/copilot/outline", "post"),
    ]:
        operation = schema["paths"][path][method]
        assert operation.get("security"), f"{method.upper()} {path} is not guarded"


def test_public_read_routes_stay_open(client):
    schema = client.get("/openapi.json").json()
    for path, method in [("/health", "get"), ("/catalog", "get"), ("/discovery/search", "post")]:
        assert not schema["paths"][path][method].get("security")


def test_auth_scheme_endpoint_discloses_the_setup(client):
    body = client.get("/auth/scheme").json()
    assert body["scheme"] == "bearer"
    assert body["algorithm"] == "HS256"
    assert "scrypt" in body["password_hashing"]
    # No JWT_SECRET in the offline test settings, so it must warn rather than stay quiet.
    assert body["secret_configured"] is False
    assert "JWT_SECRET" in body["warning"]


def test_login_without_storage_degrades_cleanly(client):
    response = client.post("/auth/login", json={"email": "a@b.com", "password": "whatever1"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_event_schema_publishes_the_interaction_weights(client):
    body = client.get("/activity/schema").json()
    assert "drop_off" in body["event_types"]
    assert body["interaction_weights"]["complete"] == 1.0
    assert body["interaction_weights"]["drop_off"] < 0


def test_evaluation_method_is_documented(client):
    body = client.get("/evaluation/method").json()
    assert "temporal holdout" in body["protocol"]
    assert "leak" in body["why_not_random_leave_one_out"]
    assert set(body["baselines"]) == {"popularity", "random"}


def test_databricks_spec_is_generated_without_credentials(client):
    body = client.get("/pipeline/databricks").json()
    assert body["configured"] is False
    assert body["job_spec"]["name"] == "pockettaste-nightly-intelligence"
    assert len(body["job_spec"]["tasks"]) == 5
    assert "rather than a live integration" in body["status_note"]


def test_pipeline_describe_lists_three_agents_in_dependency_order(client):
    body = client.get("/pipeline/describe").json()
    stages = [stage["agent"] for stage in body["stages"]]
    assert stages == ["content_intelligence_agent", "ingestion_agent", "insight_agent"]
    assert "embeddings that ingestion needs" in body["stage_order_reason"]


def test_copilot_guardrails_are_explicit(client):
    body = client.get("/copilot/guardrails").json()
    assert body["pre_write_screening"] is True
    assert "exact_duplicate" in body["blocks_on"]
    assert any("not a legal clearance" in limit for limit in body["limits"])


def test_openapi_schema_builds(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"]
    assert "/recommendations" in schema["paths"]
    assert "/similarity/check" in schema["paths"]


def test_unknown_route_is_a_clean_404(client):
    assert client.get("/nope").status_code == 404


def test_request_schemas_reject_bad_payloads():
    """Validated at the schema level: FastAPI resolves dependencies before the body,
    so with storage absent these would surface as 503 over HTTP."""
    import pydantic

    from app.domain.schemas import RecommendationRequest

    RecommendationRequest(user_id="u1", limit=10)  # valid

    for payload in (
        {"limit": 5},                          # missing user_id
        {"user_id": "u", "limit": 999},        # above the cap
        {"user_id": "u", "limit": 0},          # below the floor
        {"user_id": "u", "bogus": 1},          # extra="forbid"
        {"user_id": "u", "diversity": 2.0},    # MMR lambda out of range
    ):
        with pytest.raises(pydantic.ValidationError):
            RecommendationRequest(**payload)
