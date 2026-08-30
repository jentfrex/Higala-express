from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import models
from database import get_db

router = APIRouter(prefix="/partner-portal", tags=["Partner & Merchant Portal"])

# --- Pydantic Schemas for Partner Input/Output ---
class PartnerInventoryUpdate(BaseModel):
    item_name: str
    price: float
    is_available: bool = True

class DailyStockSetup(BaseModel):
    item_name: str
    price: float
    max_daily_stock: int
    is_available: Optional[bool] = True

class StockDeductRequest(BaseModel):
    quantity_sold: int = 1

class OrderStatusUpdate(BaseModel):
    status: str  # e.g., "accepted", "preparing", "ready_for_pickup"

class OrderCancelRequest(BaseModel):
    reason: str  # e.g., "Item out of stock", "Kitchen closed early", "Too busy"


@router.get("/branch/{branch_id}/analytics")
def get_branch_analytics(branch_id: int, db: Session = Depends(get_db)):
    """View local branch analytics (Total orders, revenue, active inventory count)."""
    branch = db.query(models.MerchantBranch).filter(models.MerchantBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Micro-hub / Branch not found")
    
    # Calculate orders tied specifically to this branch
    branch_orders = db.query(models.Order).filter(models.Order.branch_id == branch_id).all()
    total_orders = len(branch_orders)
    total_revenue = sum(o.price for o in branch_orders if o.status == "completed")
    
    # Inventory items count
    inventory_items = db.query(models.BranchInventory).filter(models.BranchInventory.branch_id == branch_id).all()
    
    return {
        "success": True,
        "branch_id": branch.id,
        "branch_name": branch.branch_name,
        "address": branch.address,
        "analytics": {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "active_inventory_count": len(inventory_items)
        }
    }


@router.get("/branch/{branch_id}/orders")
def get_branch_pending_orders(
    branch_id: int, 
    skip: int = Query(0, ge=0, description="Number of orders to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Max number of orders to return"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter orders by status (e.g., pending, preparing)"),
    db: Session = Depends(get_db)
):
    """View pending and active orders assigned specifically to this branch with pagination and status filtering."""
    branch = db.query(models.MerchantBranch).filter(models.MerchantBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Micro-hub / Branch not found")
        
    query = db.query(models.Order).filter(models.Order.branch_id == branch_id)
    
    # Apply optional status filter
    if status_filter:
        query = query.filter(models.Order.status == status_filter)
        
    # Apply pagination metadata and slices
    total_count = query.count()
    orders = query.offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "branch_id": branch_id,
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "orders": orders
    }


@router.patch("/branch/{branch_id}/orders/{order_id}/status")
def update_branch_order_status(branch_id: int, order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)):
    """Allow the partner to accept or update the status of an incoming order."""
    order = db.query(models.Order).filter(models.Order.id == order_id, models.Order.branch_id == branch_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this specific branch")
        
    order.status = payload.status
    db.commit()
    db.refresh(order)
    
    return {
        "success": True,
        "message": f"Order #{order.id} status updated to '{payload.status}'",
        "order_id": order.id,
        "status": order.status
    }


@router.post("/branch/{branch_id}/orders/{order_id}/cancel")
def cancel_or_reject_branch_order(
    branch_id: int, 
    order_id: int, 
    payload: OrderCancelRequest, 
    db: Session = Depends(get_db)
):
    """Allow the partner to reject or cancel an incoming order with a specified reason."""
    order = db.query(models.Order).filter(
        models.Order.id == order_id, 
        models.Order.branch_id == branch_id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this specific branch")
        
    # Prevent modifying already completed or cancelled orders
    if order.status in ["completed", "cancelled", "rejected"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel order because its current status is already '{order.status}'"
        )
        
    order.status = "rejected"
    db.commit()
    db.refresh(order)
    
    return {
        "success": True,
        "message": f"Order #{order.id} has been rejected/cancelled.",
        "order_id": order.id,
        "status": order.status,
        "reason": payload.reason
    }


@router.get("/branch/{branch_id}/inventory")
def get_branch_live_stock(branch_id: int, db: Session = Depends(get_db)):
    """Fetch live stock updates for the partner's local store."""
    inventory = db.query(models.BranchInventory).filter(models.BranchInventory.branch_id == branch_id).all()
    return {
        "success": True,
        "branch_id": branch_id,
        "inventory": inventory
    }


@router.post("/branch/{branch_id}/inventory")
def update_branch_live_stock(branch_id: int, item_data: PartnerInventoryUpdate, db: Session = Depends(get_db)):
    """Add or modify live stock items/prices for the partner's store account."""
    branch = db.query(models.MerchantBranch).filter(models.MerchantBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Micro-hub / Branch not found")
        
    item = db.query(models.BranchInventory).filter(
        models.BranchInventory.branch_id == branch_id,
        models.BranchInventory.item_name == item_data.item_name
    ).first()
    
    if item:
        item.price = item_data.price
        item.is_available = item_data.is_available
    else:
        item = models.BranchInventory(
            branch_id=branch_id,
            item_name=item_data.item_name,
            price=item_data.price,
            is_available=item_data.is_available
        )
        db.add(item)
        
    db.commit()
    return {
        "success": True,
        "message": f"Successfully updated stock for '{item_data.item_name}'",
        "item_name": item_data.item_name,
        "is_available": item_data.is_available
    }


@router.post("/branch/{branch_id}/daily-menu")
def set_carinderia_daily_menu(branch_id: int, item_data: DailyStockSetup, db: Session = Depends(get_db)):
    """Set or update a dish with a specific number of daily servings/portions for a carinderia."""
    branch = db.query(models.MerchantBranch).filter(models.MerchantBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Micro-hub / Branch not found")
        
    item = db.query(models.BranchInventory).filter(
        models.BranchInventory.branch_id == branch_id,
        models.BranchInventory.item_name == item_data.item_name
    ).first()
    
    if item:
        item.price = item_data.price
        item.max_daily_stock = item_data.max_daily_stock
        item.current_stock = item_data.max_daily_stock  # Reset/refresh current stock for the day
        item.is_available = item_data.is_available
    else:
        item = models.BranchInventory(
            branch_id=branch_id,
            item_name=item_data.item_name,
            price=item_data.price,
            max_daily_stock=item_data.max_daily_stock,
            current_stock=item_data.max_daily_stock,
            is_available=item_data.is_available,
            is_daily_special=True
        )
        db.add(item)
        
    db.commit()
    db.refresh(item)
    return {
        "success": True,
        "message": f"Daily menu item '{item_data.item_name}' set with {item_data.max_daily_stock} servings.",
        "item": {
            "name": item.item_name,
            "price": item.price,
            "current_stock": item.current_stock,
            "is_available": item.is_available
        }
    }


@router.post("/branch/{branch_id}/inventory/{item_id}/deduct")
def deduct_carinderia_stock(branch_id: int, item_id: int, payload: StockDeductRequest, db: Session = Depends(get_db)):
    """Automatically decrement stock/servings when a dish is ordered. Auto-disables item if stock hits 0."""
    item = db.query(models.BranchInventory).filter(
        models.BranchInventory.id == item_id,
        models.BranchInventory.branch_id == branch_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found for this branch")
        
    if item.current_stock is not None:
        item.current_stock = max(0, item.current_stock - payload.quantity_sold)
        if item.current_stock == 0:
            item.is_available = False  # Automatically mark as sold out!
            
    db.commit()
    db.refresh(item)
    
    return {
        "success": True,
        "message": f"Deducted {payload.quantity_sold} serving(s) for '{item.item_name}'.",
        "current_stock": item.current_stock,
        "is_available": item.is_available
    }


@router.post("/branch/{branch_id}/daily-reset")
def trigger_daily_stock_reset(branch_id: int, db: Session = Depends(get_db)):
    """
    One-click reset button for partners.
    Refreshes all daily items (is_daily_special=True) back to their maximum daily stock 
    and reactivates their availability.
    """
    branch = db.query(models.MerchantBranch).filter(models.MerchantBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Micro-hub / Branch not found")
        
    daily_items = db.query(models.BranchInventory).filter(
        models.BranchInventory.branch_id == branch_id,
        models.BranchInventory.is_daily_special == True
    ).all()
    
    reset_count = 0
    for item in daily_items:
        if item.max_daily_stock is not None:
            item.current_stock = item.max_daily_stock
            item.is_available = True
            reset_count += 1
            
    db.commit()
    
    return {
        "success": True,
        "message": f"Successfully reset stock for {reset_count} daily menu item(s).",
        "branch_id": branch_id,
        "reset_count": reset_count
    }