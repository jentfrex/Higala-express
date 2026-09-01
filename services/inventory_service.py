# services/inventory_service.py - SEPARATED INVENTORY LOGIC (ENHANCED)

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from models import BranchInventory
import logging

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Isolated inventory management.
    Ensures food/goods orders don't contaminate ride-hailing logic.
    """
    
    @staticmethod
    def validate_and_lock_item(
        db: Session,
        item_id: int,
        quantity: int,
        item_type: str = "food"  # "food", "goods", "ride_accessory"
    ) -> dict:
        """
        Validates inventory item exists, has sufficient stock, and locks it safely.
        Returns dict with 'valid' flag and either 'inventory' object or 'reason' for failure.
        """
        if quantity <= 0:
            return {"valid": False, "reason": "Quantity must be greater than zero"}

        if item_type not in ["food", "goods", "ride_accessory"]:
            return {"valid": False, "reason": f"Unknown item type: {item_type}"}
        
        try:
            # Lock the inventory row to prevent race conditions during concurrent orders
            inventory = db.query(BranchInventory).filter(
                BranchInventory.id == item_id
            ).with_for_update().first()
            
            if not inventory:
                return {"valid": False, "reason": f"{item_type.title()} item not found: {item_id}"}
            
            if not inventory.is_available:
                return {"valid": False, "reason": f"Item '{inventory.item_name}' is currently unavailable"}
            
            if inventory.current_stock is None:
                # Item type might not use stock tracking (e.g., specific accessories)
                if item_type == "ride_accessory":
                    return {"valid": True, "inventory": inventory}
                return {"valid": False, "reason": f"Item '{inventory.item_name}' has no stock tracking"}
            
            if inventory.current_stock < quantity:
                return {
                    "valid": False,
                    "reason": f"Insufficient stock for '{inventory.item_name}': "
                              f"requested {quantity}, available {inventory.current_stock}"
                }
            
            return {"valid": True, "inventory": inventory}
            
        except OperationalError as oe:
            logger.error(f"Database lock timeout or operational error on item {item_id}: {str(oe)}")
            return {"valid": False, "reason": "System is busy processing other orders. Please try again."}
        except Exception as e:
            logger.error(f"Unexpected error validating inventory item {item_id}: {str(e)}")
            return {"valid": False, "reason": f"Inventory validation error: {str(e)}"}
    
    @staticmethod
    def deduct_inventory_batch(
        db: Session,
        items_to_deduct: list  # [{"inventory_id": int, "quantity": int}, ...]
    ) -> bool:
        """
        Atomically deduct multiple inventory items in batch.
        Returns True if successful, raises exception on failure.
        """
        if not items_to_deduct:
            return True

        for item in items_to_deduct:
            inv_id = item.get("inventory_id")
            qty = item.get("quantity", 0)

            if qty <= 0:
                raise ValueError("Deduction quantity must be positive")

            inv = db.query(BranchInventory).filter(
                BranchInventory.id == inv_id
            ).with_for_update().first()
            
            if not inv:
                raise ValueError(f"Inventory item ID {inv_id} not found")
            
            if inv.current_stock < qty:
                raise ValueError(f"Stock conflict: '{inv.item_name}' has only {inv.current_stock} left, but {qty} required.")
            
            inv.current_stock -= qty
            if inv.current_stock <= 0:
                inv.current_stock = 0
                inv.is_available = False
        
        return True