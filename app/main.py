import os, hmac, hashlib, base64, json
from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from . import models
from .services.sync import sync

Base.metadata.create_all(engine)
app = FastAPI(title="WooCommerce CRM")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    stats = {
        "customers": db.query(models.Customer).count(),
        "orders": db.query(models.Order).count(),
        "revenue": db.query(func.coalesce(func.sum(models.Order.total), 0)).filter(models.Order.status == "completed").scalar(),
    }
    by_status = db.query(models.Order.status, func.count()).group_by(models.Order.status).all()
    recent = db.query(models.Order).order_by(models.Order.created_at.desc()).limit(5).all()
    return templates.TemplateResponse(request, "dashboard.html", {"stats": stats, "by_status": by_status, "recent": recent})

@app.post("/sync")
def do_sync(db: Session = Depends(get_db)):
    sync(db)
    return RedirectResponse("/", status_code=303)

@app.get("/customers")
def customers(request: Request, q: str = "", segment: str = "", db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    query = db.query(models.Customer)
    if q:
        like = f"%{q}%"
        query = query.filter((models.Customer.first_name.ilike(like)) |
                             (models.Customer.last_name.ilike(like)) |
                             (models.Customer.email.ilike(like)))
    rows = query.all()
    cutoff = datetime.utcnow() - timedelta(days=30)

    def spent(c):
        return sum(o.total or 0 for o in c.orders if o.status != "cancelled")

    def last_order(c):
        dates = [o.created_at for o in c.orders if o.created_at]
        return max(dates) if dates else None

    rules = {
        "vip": lambda c: spent(c) >= 5000,
        "repeat": lambda c: len(c.orders) >= 2,
        "new": lambda c: len(c.orders) == 0,
        "at_risk": lambda c: last_order(c) is not None and last_order(c) < cutoff,
    }
    counts = {k: sum(1 for c in rows if f(c)) for k, f in rules.items()}
    if segment in rules:
        rows = [c for c in rows if rules[segment](c)]
    return templates.TemplateResponse(request, "customers.html", {
        "customers": rows, "q": q, "segment": segment, "counts": counts, "total": len(rows)})

# ---------- Stage 2 ----------
from datetime import datetime
from fastapi import Form, HTTPException
from .services.orders import set_status

@app.get("/customers/{cid}")
def customer_detail(cid: int, request: Request, db: Session = Depends(get_db)):
    c = db.get(models.Customer, cid)
    if not c:
        raise HTTPException(404, "Customer not found")
    return templates.TemplateResponse(request, "customer.html", {"c": c})

@app.post("/customers/{cid}/notes")
def save_notes(cid: int, notes: str = Form(""), tags: str = Form(""), db: Session = Depends(get_db)):
    c = db.get(models.Customer, cid)
    c.notes, c.tags = notes, tags
    db.commit()
    return RedirectResponse(f"/customers/{cid}", status_code=303)

STATUSES = ["pending", "processing", "on-hold", "completed", "cancelled"]

@app.get("/orders")
def orders(request: Request, status: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Order).order_by(models.Order.created_at.desc())
    if status:
        query = query.filter(models.Order.status == status)
    return templates.TemplateResponse(request, "orders.html",
                                      {"orders": query.all(), "status": status, "statuses": STATUSES})

@app.get("/orders/{oid}")
def order_detail(oid: int, request: Request, db: Session = Depends(get_db)):
    o = db.get(models.Order, oid)
    if not o:
        raise HTTPException(404, "Order not found")
    return templates.TemplateResponse(request, "order.html", {"o": o, "statuses": STATUSES})

@app.post("/orders/{oid}/status")
def update_status(oid: int, status: str = Form(...), db: Session = Depends(get_db)):
    o = db.get(models.Order, oid)
    set_status(db, o, status, "Updated manually from CRM")
    db.commit()
    return RedirectResponse(f"/orders/{oid}", status_code=303)

@app.post("/webhooks/woocommerce")
async def woo_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    secret = os.getenv("WOO_WEBHOOK_SECRET")
    if secret:
        expected = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(expected, request.headers.get("X-WC-Webhook-Signature", "")):
            raise HTTPException(401, "Invalid webhook signature")
    try:
        p = json.loads(raw)
    except Exception:
        return {"ok": True, "ignored": "not json (webhook ping)"}
    if "id" not in p:
        return {"ok": True, "ignored": "no order id"}
    o = db.get(models.Order, p["id"])
    if not o:
        cid = p.get("customer_id") or None
        if cid and not db.get(models.Customer, cid):
            cid = None
        o = models.Order(id=p["id"], customer_id=cid, status=p.get("status", "pending"),
                         total=float(p.get("total") or 0), currency=p.get("currency", "INR"),
                         created_at=datetime.utcnow())
        o.items = [models.OrderItem(name=i["name"], price=float(i["price"]), quantity=i["quantity"])
                   for i in p.get("line_items", [])]
        db.add(o)
        db.flush()
        db.add(models.OrderEvent(order_id=o.id, status=o.status, note="Order created via webhook"))
        workflows.on_order_created(db, o)
    elif "status" in p:
        set_status(db, o, p["status"], "Updated via WooCommerce webhook")
    db.commit()
    return {"ok": True, "order_id": o.id, "status": o.status}

# ---------- Stage 3: communication workflows ----------
from .services import workflows

@app.get("/workflows")
def workflows_page(request: Request, db: Session = Depends(get_db)):
    msgs = db.query(models.Message).order_by(models.Message.sent_at.desc()).limit(30).all()
    return templates.TemplateResponse(request, "workflows.html", {
        "templates": workflows.TEMPLATES, "messages": msgs,
        "candidates": len(workflows.winback_candidates(db))})

@app.post("/workflows/winback")
def run_winback(db: Session = Depends(get_db)):
    workflows.run_winback(db)
    return RedirectResponse("/workflows", status_code=303)

@app.post("/customers/{cid}/message")
def manual_message(cid: int, subject: str = Form(...), body: str = Form(...), db: Session = Depends(get_db)):
    c = db.get(models.Customer, cid)
    workflows.send_custom(db, c, "manual", subject, body)
    db.commit()
    return RedirectResponse(f"/customers/{cid}", status_code=303)

# ---------- Stage 4: AI draft ----------
from .services import ai

@app.post("/customers/{cid}/draft")
def ai_draft(cid: int, request: Request, goal: str = Form(""), db: Session = Depends(get_db)):
    c = db.get(models.Customer, cid)
    subject, body = ai.draft_email(c, goal)
    return templates.TemplateResponse(request, "_draft.html", {"c": c, "subject": subject, "body": body})
