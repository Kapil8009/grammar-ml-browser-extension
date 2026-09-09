import asyncio

import httpx

from backend.app.config import Settings
from backend.app.main import create_app
from tests.fakes import FakeCorrectionModel


def make_app(*, api_key: str | None = None, max_chars: int = 1000):
    settings = Settings(api_key=api_key, max_text_chars=max_chars)
    model = FakeCorrectionModel({"They is ready.": "They are ready."})
    return create_app(settings=settings, model=model)


def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_does_not_force_model_download() -> None:
    app = make_app()

    assert request(app, "GET", "/health").json() == {"status": "ok"}
    assert request(app, "GET", "/ready").json() == {"status": "ready", "model_loaded": False}


def test_correction_contract() -> None:
    response = request(make_app(), "POST", "/v1/correct", json={"text": "They is ready."})

    assert response.status_code == 200
    body = response.json()
    assert body["corrected"] == "They are ready."
    assert body["changed"] is True
    assert body["suggestions"][0]["start"] == 5
    assert body["suggestions"][0]["replacement"] == "are"


def test_api_key_and_size_limits() -> None:
    app = make_app(api_key="secret", max_chars=5)

    assert request(app, "POST", "/v1/correct", json={"text": "hello"}).status_code == 401
    assert request(
        app,
        "POST",
        "/v1/correct",
        json={"text": "hello"},
        headers={"X-API-Key": "secret"},
    ).status_code == 200
    assert request(
        app,
        "POST",
        "/v1/correct",
        json={"text": "too long"},
        headers={"X-API-Key": "secret"},
    ).status_code == 413


def test_blank_input_is_rejected() -> None:
    response = request(make_app(), "POST", "/v1/correct", json={"text": "   "})

    assert response.status_code == 422
