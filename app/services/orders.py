from .. import models

def set_status(db, order, status, note=""):
    """Change order status, log a timeline event. Returns True if it changed."""
    if order.status == status:
        return False
    order.status = status
    db.add(models.OrderEvent(order_id=order.id, status=status, note=note))
    db.flush()
    return True
