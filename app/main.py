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
    return templates.TemplateResponse(request, "dashboard.html", {"stats": stats})

@app.post("/sync")
def do_sync(db: Session = Depends(get_db)):
    sync(db)
    return RedirectResponse("/", status_code=303)

@app.get("/customers")
def customers(request: Request, q: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Customer)
    if q:
        like = f"%{q}%"
        query = query.filter((models.Customer.first_name.ilike(like)) |
                             (models.Customer.last_name.ilike(like)) |
                             (models.Customer.email.ilike(like)))
    return templates.TemplateResponse(request, "customers.html", {"customers": query.all(), "q": q})
