import os, json
import httpx

def _mock():
    with open("data/mock_data.json") as f:
        return json.load(f)

def fetch_all():
    url, key, secret = os.getenv("WOO_URL"), os.getenv("WOO_KEY"), os.getenv("WOO_SECRET")
    if not (url and key and secret):
        return _mock()  # fallback: mock data shaped like the WooCommerce API

    def get(path):
        out, page = [], 1
        while True:
            r = httpx.get(f"{url}/wp-json/wc/v3/{path}", auth=(key, secret),
                          params={"per_page": 100, "page": page}, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not data:
                break
            out += data
            page += 1
        return out

    return {"customers": get("customers"), "orders": get("orders")}
