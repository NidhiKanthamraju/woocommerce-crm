import os
import httpx

def draft_email(c, goal):
    goal = goal or "a friendly check-in"
    fallback = (f"Hello {c.first_name}", f"Hi {c.first_name},\n\n{goal.capitalize()}.\n\n- WooCRM Team")
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return fallback
    orders = ", ".join(f"#{o.id} ({o.status}, Rs {o.total:.0f})" for o in c.orders[:5]) or "no orders yet"
    prompt = (f"Write a short, warm customer email (max 120 words) for an online store. "
              f"Customer: {c.first_name} {c.last_name}, city: {c.city}. Orders: {orders}. Goal: {goal}. "
              f"Format: first line is ONLY the subject, then a blank line, then the body. "
              f"Sign off as 'WooCRM Team'. No placeholders.")
    try:
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                "content-type": "application/json"},
                       json={"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 400,
                             "messages": [{"role": "user", "content": prompt}]}, timeout=30)
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        subject, _, body = text.partition("\n")
        return subject.replace("Subject:", "").strip(), body.strip()
    except Exception as e:
        print("AI draft error:", e)
        return fallback
