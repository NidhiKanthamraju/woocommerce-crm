from datetime import datetime
from .. import models
from .woo_client import fetch_all

def _dt(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.utcnow()

def sync(db):
    data = fetch_all()
    for c in data["customers"]:
        obj = db.get(models.Customer, c["id"]) or models.Customer(id=c["id"])
        obj.first_name = c.get("first_name")
        obj.last_name = c.get("last_name")
        obj.email = c.get("email")
        b = c.get("billing") or {}
        obj.phone = b.get("phone")
        obj.city = b.get("city")
        obj.created_at = _dt(c.get("date_created", ""))
        db.add(obj)
    db.flush()
    for o in data["orders"]:
        obj = db.get(models.Order, o["id"]) or models.Order(id=o["id"])
        obj.customer_id = o.get("customer_id") or None
        obj.status = o.get("status")
        obj.total = float(o.get("total") or 0)
        obj.currency = o.get("currency")
        obj.created_at = _dt(o.get("date_created", ""))
        obj.items = [models.OrderItem(name=i["name"], price=float(i["price"]), quantity=i["quantity"])
                     for i in o.get("line_items", [])]
        db.add(obj)
    db.commit()
    return len(data["customers"]), len(data["orders"])
