import os, smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from .. import models

TEMPLATES = {
    "order_confirmation": {
        "subject": "Order #{order_id} confirmed",
        "body": "Hi {name},\n\nThanks for your order #{order_id} (total ₹{total}). We're getting it ready.\n\nItems: {items}\n\n- WooCRM Team",
    },
    "shipped": {
        "subject": "Your order #{order_id} is on its way",
        "body": "Hi {name},\n\nGood news! Order #{order_id} has been completed and shipped.\n\n- WooCRM Team",
    },
    "cancelled": {
        "subject": "Order #{order_id} cancelled",
        "body": "Hi {name},\n\nYour order #{order_id} was cancelled. If this wasn't expected, just reply to this email.\n\n- WooCRM Team",
    },
    "winback": {
        "subject": "We miss you, {name}!",
        "body": "Hi {name},\n\nIt's been a while since your last order. Here's 10% off your next purchase with code COMEBACK10.\n\n- WooCRM Team",
    },
}

class _Safe(dict):
    def __missing__(self, key):
        return ""

def _smtp(to, subject, body):
    """Optional: set SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/SMTP_FROM to really send email."""
    host = os.getenv("SMTP_HOST")
    if not host:
        return
    try:
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = os.getenv("SMTP_FROM", "crm@example.com"), to, subject
        m.set_content(body)
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587))) as s:
            s.starttls()
            s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", ""))
            s.send_message(m)
    except Exception as e:
        print("SMTP error (message still logged):", e)

def send_custom(db, customer, kind, subject, body):
    if not customer or not customer.email:
        return None
    msg = models.Message(customer_id=customer.id, kind=kind, subject=subject, body=body)
    db.add(msg)
    db.flush()
    _smtp(customer.email, subject, body)
    return msg

def send_message(db, customer, kind, **ctx):
    if not customer:
        return None
    ctx.setdefault("name", customer.first_name or "there")
    t = TEMPLATES[kind]
    return send_custom(db, customer, kind,
                       t["subject"].format_map(_Safe(ctx)), t["body"].format_map(_Safe(ctx)))

def _order_ctx(order):
    return {"order_id": order.id, "total": f"{order.total:.0f}",
            "items": ", ".join(i.name for i in order.items)}

def on_order_created(db, order):
    send_message(db, order.customer, "order_confirmation", **_order_ctx(order))

STATUS_TRIGGERS = {"completed": "shipped", "cancelled": "cancelled"}

def on_status_change(db, order, status):
    kind = STATUS_TRIGGERS.get(status)
    if kind:
        send_message(db, order.customer, kind, **_order_ctx(order))

def winback_candidates(db, days=30):
    cutoff = datetime.utcnow() - timedelta(days=days)
    out = []
    for c in db.query(models.Customer).all():
        dates = [o.created_at for o in c.orders if o.created_at] or ([c.created_at] if c.created_at else [])
        if not dates or max(dates) >= cutoff:
            continue
        if any(m.kind == "winback" and m.sent_at > cutoff for m in c.messages):
            continue
        out.append(c)
    return out

def run_winback(db, days=30):
    cands = winback_candidates(db, days)
    for c in cands:
        send_message(db, c, "winback")
    db.commit()
    return len(cands)
