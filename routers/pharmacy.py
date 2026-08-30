from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
import models

router = APIRouter(prefix="/api/pharmacy", tags=["Pharmacy"])

class CartItem(BaseModel):
    name: str
    price: float
    qty: int
    dosage: Optional[str] = None

class CheckoutRequest(BaseModel):
    items: List[CartItem]
    subsidized_wallet: float

@router.get("/inventory")
def get_pharmacy_inventory(db: Session = Depends(get_db)):
    return {
        "success": True,
        "message": "CDO Pharmacy Inventory loaded successfully",
        "items": [
            {"id": 1, "name": "Paracetamol 500mg", "price": 5.00, "stock": 150},
            {"id": 2, "name": "Amoxicillin 500mg", "price": 12.50, "stock": 80},
            {"id": 3, "name": "Biogesic", "price": 6.00, "stock": 200},
            {"id": 4, "name": "Neozep Non-Drowsy", "price": 7.50, "stock": 120}
        ]
    }

@router.post("/checkout")
def process_pharmacy_checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    total_amount = sum(item.price * item.qty for item in payload.items)
    
    if payload.subsidized_wallet >= total_amount:
        remaining_balance = payload.subsidized_wallet - total_amount
        return {
            "success": True,
            "message": "Subsidized checkout successful via LGU health wallet.",
            "total": total_amount,
            "remaining_wallet": remaining_balance
        }
    else:
        return {
            "success": False,
            "message": "Insufficient subsidy balance. Split payment required.",
            "total": total_amount,
            "shortfall": total_amount - payload.subsidized_wallet
        }