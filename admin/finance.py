# admin/finance.py (o admin/bank_transfers.py)
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import BankTransferRequest, Payment, PaymentStatus

# Gi-set ang prefix aron malakip ang tanang admin financial ug verification operations
router = APIRouter(prefix="/api/admin", tags=["Admin Finance & Operations"])

# --- Pydantic Payloads para sa Finance ---
class TransactionOverridePayload(BaseModel):
    new_status: str = Field(..., description="The new status to override (e.g., 'completed', 'failed', 'refunded')")
    reason: Optional[str] = Field(None, description="Audit reason for overriding the transaction")

class CommissionUpdatePayload(BaseModel):
    commission_rate: float = Field(..., description="The new platform commission percentage rate")


# --- Finance & Payout Endpoints ---
@router.get("/finance/summary", summary="Get Financial Summary & Metrics")
async def get_financial_summary():
    """
    Kuhaa ang kinatibuk-ang financial overview lakip na ang GMV karong adlawa,
    komisyon sa platform, ug pending nga bayronon sa mga drivers (sa PHP).
    """
    return {
        "success": True,
        "metrics": {
            "total_gmv_today": 145250.00,
            "platform_commission_earned": 14525.00,
            "pending_driver_payouts": 8420.00,
            "currency": "PHP"
        }
    }

@router.post("/finance/payouts/batch-trigger", summary="Trigger Manual Payout Batch")
async def trigger_manual_payout_batch():
    """
    I-trigger ang manual nga pagpadala sa batch payouts ngadto sa payment gateway processor.
    """
    return {
        "success": True,
        "message": "Manual payout batch successfully dispatched to payment gateway processor."
    }

@router.patch("/finance/transactions/{tx_id}/override", summary="Override Transaction Status")
async def override_transaction_status(tx_id: str, payload: TransactionOverridePayload):
    """
    I-override manualmente ang status sa usa ka transaksiyon (Pananglitan: gi-refund o gi-force complete).
    """
    if not tx_id:
        raise HTTPException(status_code=400, detail="Transaction ID is required")
        
    return {
        "success": True,
        "message": f"Transaction {tx_id} status manually overridden to '{payload.new_status}' by Admin.",
        "reason_logged": payload.reason or "No reason provided"
    }

@router.post("/finance/commission", summary="Update Platform Commission Rate")
async def update_commission_rate(payload: CommissionUpdatePayload):
    """
    I-update ang porsyento sa komisyon sa platform (Dynamic Commission Control).
    """
    if payload.commission_rate < 0 or payload.commission_rate > 100:
        raise HTTPException(status_code=400, detail="Invalid commission rate percentage")
        
    return {
        "success": True,
        "message": f"Platform commission rate successfully updated to {payload.commission_rate}%",
        "new_rate": payload.commission_rate
    }


# --- Bank Transfer Verification Endpoints ---
@router.get("/bank-transfers/pending", summary="Get Pending Bank Transfers")
def get_pending_transfers(db: Session = Depends(get_db)):
    """Admin sees all pending bank transfers waiting for manual verification"""
    
    pending = db.query(BankTransferRequest).filter(
        BankTransferRequest.status == "awaiting_payment"
    ).all()
    
    return {
        "success": True,
        "pending_count": len(pending),
        "transfers": [
            {
                "id": t.id,
                "reference": t.reference_number,
                "user_id": t.user_id,
                "amount": t.amount,
                "account": f"{t.account_name} ({t.account_number})",
                "deadline": t.payment_deadline.isoformat(),
                "created_at": t.created_at.isoformat()
            }
            for t in pending
        ]
    }

@router.post("/bank-transfers/verify/{reference_number}", summary="Verify Bank Transfer")
def admin_verify_bank_transfer(
    reference_number: str,
    db: Session = Depends(get_db)
):
    """Admin confirms bank transfer was received"""
    
    transfer = db.query(BankTransferRequest).filter(
        BankTransferRequest.reference_number == reference_number
    ).first()
    
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    transfer.status = "payment_confirmed"
    
    # Update associated payment
    payment = db.query(Payment).filter(
        Payment.transaction_reference == reference_number
    ).first()
    
    if payment:
        payment.status = PaymentStatus.COMPLETED
        payment.payment_date = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "reference": reference_number,
        "verified_at": datetime.utcnow().isoformat()
    }