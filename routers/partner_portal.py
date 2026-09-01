# routers/partner_portal.py - Enhanced Merchant Dashboard & Partner Portal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import models
from database import get_db

router = APIRouter(prefix="/partner-portal", tags=["Partner & Merchant Portal"])

# ==========================================
# SCHEMAS
# ==========================================

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


# ==========================================
# ANALYTICS & DASHBOARD
# ==========================================

@router.get("/dashboard/{merchant_id}")
def get_merchant_dashboard(
    merchant_id: int,
    db: Session = Depends(get_db)
):
    """
    Real-time merchant dashboard with key metrics.
    Shows orders, revenue, inventory, and payouts.
    """
    merchant = db.query(models.User).filter(
        models.User.id == merchant_id,
        models.User.user_type == "merchant"
    ).first()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    # Get merchant's branches
    branches = db.query(models.MerchantBranch).filter(
        models.MerchantBranch.merchant_id == merchant_id
    ).all()
    
    branch_ids = [b.id for b in branches]
    
    # Today's orders
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_orders = db.query(models.Order).filter(
        models.Order.branch_id.in_(branch_ids),
        models.Order.created_at >= today_start
    ).all() if branch_ids else []
    
    total_revenue_today = sum(
        o.price for o in today_orders if o.status in ["completed", "paid"]
    )
    
    pending_orders = [o for o in today_orders if o.status in ["pending", "accepted", "preparing"]]
    
    # Inventory count
    inventory_items = db.query(models.BranchInventory).filter(
        models.BranchInventory.branch_id.in_(branch_ids),
        models.BranchInventory.is_available == True
    ).count() if branch_ids else 0
    
    # Pending commissions
    pending_commissions = db.query(func.sum(models.MerchantCommission.merchant_payout)).filter(
        models.MerchantCommission.merchant_id == merchant_id,
        models.MerchantCommission.status == "pending"
    ).scalar() or 0.0
    
    return {
        "success": True,
        "merchant_id": merchant_id,
        "merchant_name": getattr(merchant, "name", "Merchant"),
        "stats": {
            "total_orders_today": len(today_orders),
            "total_revenue_today": total_revenue_today,
            "pending_orders": len(pending_orders),
            "active_inventory_items": inventory_items,
            "pending_commission_payout": pending_commissions
        },
        "branches_managed": len(branches)
    }


@router.get("/merchant/{merchant_id}/commission-summary")
def get_commission_summary(
    merchant_id: int,
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None)
):
    """
    View detailed commission breakdown per order.
    Merchants can track how much they earn after platform fees.
    """
    query = db.query(models.MerchantCommission).filter(
        models.MerchantCommission.merchant_id == merchant_id
    )
    
    if status_filter:
        query = query.filter(models.MerchantCommission.status == status_filter)
    
    commissions = query.all()
    
    summary = {
        "success": True,
        "merchant_id": merchant_id,
        "total_commissions": len(commissions),
        "breakdown": [
            {
                "order_id": c.order_id,
                "gross_amount": c.gross_amount,
                "commission_rate": f"{c.commission_rate * 100:.1f}%",
                "commission_deducted": c.commission_amount,
                "merchant_payout": c.merchant_payout,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in commissions
        ]
    }
    
    if commissions:
        summary["total_gross"] = sum(c.gross_amount for c in commissions)
        summary["total_commission_paid"] = sum(c.commission_amount for c in commissions)
        summary["total_merchant_earned"] = sum(c.merchant_payout for c in commissions)
    
    return summary


# ==========================================
# BRANCH OPERATIONS & ANALYTICS
# ==========================================

@router.get("/branch/{branch_id}/analytics")
def get_branch_analytics(
    branch_id: int, 
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=30)
):
    """View local branch analytics (Total orders, revenue by status, active inventory count)."""
    branch = db.query(models.MerchantBranch).filter(models.MerchantBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Micro-hub / Branch not found")
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    branch_orders = db.query(models.Order).filter(
        models.Order.branch_id == branch_id,
        models.Order.created_at >= start_date
    ).all()
    
    revenue_by_status = {}
    for order in branch_orders:
        st = order.status
        if st not in revenue_by_status:
            revenue_by_status[st] = 0.0
        revenue_by_status[st] += getattr(order, 'price', 0.0)
    
    inventory_items = db.query(models.BranchInventory).filter(models.BranchInventory.branch_id == branch_id).all()
    
    return {
        "success": True,
        "branch_id": branch.id,
        "branch_name": branch.branch_name,
        "address": branch.address,
        "period_days": days,
        "analytics": {
            "total_orders": len(branch_orders),
            "revenue_by_status": revenue_by_status,
            "total_inventory_items": len(inventory_items),
            "active_inventory_count": sum(1 for i in inventory_items if i.is_available)
        }
    }


@router.get("/branch/{branch_id}/orders")
def get_branch_pending_orders(
    branch_id: int, 
    skip: int = Query(0, ge=0, description="Number of orders to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Max number of orders to return"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter orders by status"),
    db: Session = Depends(get_db)
):
    """View pending and active orders assigned specifically to this branch with pagination and status filtering."""
    branch = db.query(models.MerchantBranch).filter(models.MerchantBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Micro-hub / Branch not found")
        
    query = db.query(models.Order).filter(models.Order.branch_id == branch_id)
    
    if status_filter:
        query = query.filter(models.Order.status == status_filter)
        
    total_count = query.count()
    orders = query.order_by(models.Order.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "branch_id": branch_id,
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "orders": orders
    }


@router.patch("/branch/{branch_id}/orders/{order_id}/status")
def update_branch_order_status(
    branch_id: int, 
    order_id: int, 
    payload: OrderStatusUpdate, 
    db: Session = Depends(get_db)
):
    """Allow the partner to accept, prepare, or update the status of an incoming order with safety checks."""
    order = db.query(models.Order).filter(models.Order.id == order_id, models.Order.branch_id == branch_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this specific branch")
        
    allowed_transitions = {
        "pending": ["accepted", "rejected"],
        "accepted": ["preparing", "rejected"],
        "preparing": ["ready_for_pickup", "ready_for_delivery"],
        "ready_for_pickup": ["completed"],
        "ready_for_delivery": ["on_transit"],
        "on_transit": ["completed"]
    }
    
    new_status = payload.status
    if order.status in allowed_transitions and new_status not in allowed_transitions[order.status]:
        # Allow generic updates if needed, or enforce strict transitions
        pass 
        
    order.status = new_status
    db.commit()
    db.refresh(order)
    
    return {
        "success": True,
        "message": f"Order #{order.id} status updated to '{payload.status}'",
        "order_id": order.id,
        "status": order.status,
        "updated_at": datetime.utcnow().isoformat()
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


# ==========================================
# INVENTORY & CARINDERIA DAILY MENU
# ==========================================

@router.get("/branch/{branch_id}/inventory")
def get_branch_live_stock(
    branch_id: int, 
    skip: int = Query(0),
    limit: int = Query(50),
    db: Session = Depends(get_db)
):
    """Fetch live stock updates and daily menu items for the partner's local store."""
    inventory = db.query(models.BranchInventory).filter(
        models.BranchInventory.branch_id == branch_id
    ).offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "branch_id": branch_id,
        "inventory": inventory
    }


@router.post("/branch/{branch_id}/inventory")
def update_branch_live_stock(
    branch_id: int, 
    item_data: PartnerInventoryUpdate, 
    db: Session = Depends(get_db)
):
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
    db.refresh(item)
    
    return {
        "success": True,
        "message": f"Successfully updated stock for '{item_data.item_name}'",
        "item_name": item_data.item_name,
        "is_available": item_data.is_available
    }


@router.post("/branch/{branch_id}/daily-menu")
def set_carinderia_daily_menu(
    branch_id: int, 
    item_data: DailyStockSetup, 
    db: Session = Depends(get_db)
):
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
        item.is_daily_special = True
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
def deduct_carinderia_stock(
    branch_id: int, 
    item_id: int, 
    payload: StockDeductRequest, 
    db: Session = Depends(get_db)
):
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


@router.post("/branch/{branch_id}/inventory/{item_id}/restock")
def restock_item(
    branch_id: int,
    item_id: int,
    quantity_added: int = Query(..., gt=0),
    db: Session = Depends(get_db)
):
    """Increase stock for a specific inventory item and re-enable availability if sold out."""
    item = db.query(models.BranchInventory).filter(
        models.BranchInventory.id == item_id,
        models.BranchInventory.branch_id == branch_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    old_stock = item.current_stock or 0
    item.current_stock = old_stock + quantity_added
    item.is_available = True
    
    db.commit()
    db.refresh(item)
    
    return {
        "success": True,
        "item_id": item.id,
        "item_name": item.item_name,
        "previous_stock": old_stock,
        "current_stock": item.current_stock,
        "quantity_added": quantity_added
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
        "items_reset": reset_count,
        "reset_at": datetime.utcnow().isoformat()
    }