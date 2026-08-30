from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from typing import Literal

import models
from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/disputes", tags=["Dispute Resolution"])

class DisputeCreate(BaseModel):
    order_id: int
    reason: str
    resolution_type: Literal["full_refund", "partial_refund", "credit"]
    refund_amount: Decimal

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_dispute_ticket(
    dispute: DisputeCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Verify that the order exists
    order = db.query(models.Order).filter(models.Order.id == dispute.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 2. Check if the user is authorized (customer of the order or an admin/merchant)
    if order.customer_id != current_user.id and current_user.role not in ["admin", "merchant"]:
        raise HTTPException(status_code=403, detail="Not authorized to create a dispute for this order")

    # 3. Create and persist the dispute ticket matching models.py (SupportTicket)
    ticket_status = "resolved_automatically" if dispute.resolution_type in ["full_refund", "partial_refund"] else "open"
    
    new_ticket = models.SupportTicket(
        user_id=current_user.id,
        order_id=dispute.order_id,
        subject=f"Dispute - {dispute.resolution_type.replace('_', ' ').title()}",
        description=f"Reason: {dispute.reason} | Requested Amount: {dispute.refund_amount}",
        status=ticket_status
    )
    
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    
    return {
        "success": True,
        "ticket_id": new_ticket.id,
        "order_id": new_ticket.order_id,
        "status": new_ticket.status,
        "applied_resolution": dispute.resolution_type,
        "amount": float(dispute.refund_amount)
    }