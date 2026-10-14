from .. import models
from . import workflows

def set_status(db, order, status, note=""):
    """Change order status, log a timeline event, fire email workflow."""
    if order.status == status:
        return False
    order.status = status
    db.add(models.OrderEvent(order_id=order.id, status=status, note=note))
    db.flush()
    workflows.on_status_change(db, order, status)
    return True
