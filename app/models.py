from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from .database import Base

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)  # WooCommerce customer id
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, index=True)
    phone = Column(String)
    city = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, default="")
    tags = Column(String, default="")
    orders = relationship("Order", back_populates="customer", order_by="Order.created_at.desc()")
    messages = relationship("Message", back_populates="customer", order_by="Message.sent_at.desc()")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)  # WooCommerce order id
    customer_id = Column(Integer, ForeignKey("customers.id"))
    status = Column(String, index=True)
    total = Column(Float)
    currency = Column(String)
    created_at = Column(DateTime)
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer)
    order = relationship("Order", back_populates="items")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    kind = Column(String)  # order_confirmation, shipped, winback, manual
    subject = Column(String)
    body = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    customer = relationship("Customer", back_populates="messages")

class OrderEvent(Base):
    __tablename__ = "order_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    status = Column(String)
    note = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    order = relationship("Order", back_populates="events")

Order.events = relationship("OrderEvent", back_populates="order",
                            order_by=OrderEvent.created_at, cascade="all, delete-orphan")
