import json, random
from faker import Faker
fake = Faker("en_IN")
STATUSES = ["pending", "processing", "on-hold", "completed", "cancelled"]
PRODUCTS = [("Wireless Mouse", 799), ("USB-C Cable", 349), ("Laptop Stand", 1299),
            ("Keyboard", 2199), ("Headphones", 2999), ("Webcam", 1799)]

customers = []
for i in range(1, 31):
    customers.append({
        "id": i, "first_name": fake.first_name(), "last_name": fake.last_name(),
        "email": fake.unique.email(),
        "billing": {"phone": fake.phone_number(), "city": fake.city()},
        "date_created": fake.date_time_this_year().isoformat(),
    })

orders = []
for i in range(1, 81):
    c = random.choice(customers)
    items = random.sample(PRODUCTS, random.randint(1, 3))
    orders.append({
        "id": 1000 + i, "customer_id": c["id"], "status": random.choice(STATUSES),
        "total": str(sum(p for _, p in items)), "currency": "INR",
        "date_created": fake.date_time_this_year().isoformat(),
        "line_items": [{"name": n, "price": p, "quantity": 1} for n, p in items],
    })

json.dump({"customers": customers, "orders": orders}, open("data/mock_data.json", "w"), indent=2)
