from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "demo123", "tenant_slug": "demo"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_full_material_workflow() -> None:
    headers = auth_headers()
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "title": "Chiffon Floral Dress",
            "category": "fashion",
            "description": "Luxury editorial product material workflow.",
            "selling_points": ["V-neckline", "Waist tie", "Transparent sleeves"],
            "target_platforms": ["douyin", "taobao", "amazon"],
        },
    )
    assert created.status_code == 200
    product = created.json()

    upload = client.post(
        f"/api/v1/products/{product['id']}/uploads",
        headers=headers,
        files={"file": ("dress.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert upload.status_code == 200
    assert upload.json()["kind"] == "upload"

    generation = client.post(
        "/api/v1/workflows/full-pack",
        headers=headers,
        json={"product_id": product["id"], "durations": [15, 30, 60], "platforms": ["douyin"]},
    )
    assert generation.status_code == 200
    payload = generation.json()
    assert payload["workflow_id"].startswith("wf_")
    assert len(payload["assets"]) == 6
    assert {asset["kind"] for asset in payload["assets"]} >= {"main_image", "detail_page", "copy", "short_video"}

    history = client.get("/api/v1/history", headers=headers)
    assert history.status_code == 200
    assert any(event["action"] == "full_pack.generated" for event in history.json())

    stats = client.get("/api/v1/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["products"] >= 1
    assert stats.json()["videos"] >= 3


def test_auth_rejects_wrong_password() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong", "tenant_slug": "demo"},
    )
    assert response.status_code == 401
