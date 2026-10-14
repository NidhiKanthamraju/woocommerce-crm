from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_sync_and_pages_load():
    assert client.post("/sync", follow_redirects=False).status_code == 303
    for path in ["/", "/customers", "/orders", "/workflows"]:
        assert client.get(path).status_code == 200

def test_webhook_updates_status():
    client.post("/sync")
    r = client.post("/webhooks/woocommerce", json={"id": 1001, "status": "completed"})
    assert r.json()["ok"] is True

def test_webhook_creates_order_and_sends_confirmation():
    client.post("/sync")
    r = client.post("/webhooks/woocommerce", json={
        "id": 9001, "customer_id": 1, "status": "processing", "total": "999",
        "line_items": [{"name": "USB-C Cable", "price": 349, "quantity": 1}]})
    assert r.json()["ok"] is True
    assert "9001" in client.get("/customers/1").text
