from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional

# Gi-set ang prefix aron mahimong /api/admin/finance ang dagan sa URLs
router = APIRouter(prefix="/api/admin/finance", tags=["Admin Finance & Payouts"])

class TransactionOverridePayload(BaseModel):
    new_status: str = Field(..., description="The new status to override (e.g., 'completed', 'failed', 'refunded')")
    reason: Optional[str] = Field(None, description="Audit reason for overriding the transaction")

class CommissionUpdatePayload(BaseModel):
    commission_rate: float = Field(..., description="The new platform commission percentage rate")

@router.get("/summary", summary="Get Financial Summary & Metrics")
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

@router.post("/payouts/batch-trigger", summary="Trigger Manual Payout Batch")
async def trigger_manual_payout_batch():
    """
    I-trigger ang manual nga pagpadala sa batch payouts ngadto sa payment gateway processor.
    """
    return {
        "success": True,
        "message": "Manual payout batch successfully dispatched to payment gateway processor."
    }

@router.patch("/transactions/{tx_id}/override", summary="Override Transaction Status")
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

@router.post("/commission", summary="Update Platform Commission Rate")
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