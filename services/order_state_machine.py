# services/order_state_machine.py - PRODUCTION STATE MANAGEMENT

from enum import Enum
from typing import List, Tuple

class OrderStatus(str, Enum):
    """Strict order lifecycle"""
    PENDING = "pending"                    # Initial state
    ACCEPTED = "accepted"                  # Merchant accepted
    PREPARING = "preparing"                # Being prepared
    READY_FOR_DELIVERY = "ready_for_delivery"
    PICKED_UP = "picked_up"                # Driver picked up
    ON_TRANSIT = "on_transit"              # In transit
    COMPLETED = "completed"                # Delivered
    CANCELLED = "cancelled"                # Cancelled by customer/merchant
    REJECTED = "rejected"                  # Rejected by merchant

# Valid transitions define the state machine
STATE_TRANSITIONS = {
    OrderStatus.PENDING: {
        OrderStatus.ACCEPTED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED
    },
    OrderStatus.ACCEPTED: {
        OrderStatus.PREPARING,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED
    },
    OrderStatus.PREPARING: {
        OrderStatus.READY_FOR_DELIVERY,
        OrderStatus.CANCELLED
    },
    OrderStatus.READY_FOR_DELIVERY: {
        OrderStatus.PICKED_UP,
        OrderStatus.CANCELLED
    },
    OrderStatus.PICKED_UP: {
        OrderStatus.ON_TRANSIT,
        OrderStatus.CANCELLED
    },
    OrderStatus.ON_TRANSIT: {
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED
    },
    OrderStatus.CANCELLED: set(),          # Terminal state
    OrderStatus.REJECTED: set(),           # Terminal state
    OrderStatus.COMPLETED: set()           # Terminal state
}

class OrderStateValidator:
    """Enforce strict state machine"""
    
    @staticmethod
    def validate_transition(current_status: str, desired_status: str) -> Tuple[bool, str]:
        """
        Validates if transition is allowed.
        Returns (is_valid: bool, reason: str)
        """
        try:
            current = OrderStatus(current_status)
            desired = OrderStatus(desired_status)
        except ValueError as e:
            return False, f"Invalid status value: {str(e)}"
        
        if desired not in STATE_TRANSITIONS[current]:
            allowed = [s.value for s in STATE_TRANSITIONS[current]]
            return False, (
                f"Cannot transition from {current.value} to {desired.value}. "
                f"Allowed: {', '.join(allowed) if allowed else 'None (terminal state)'}"
            )
        
        return True, ""
    
    @staticmethod
    def who_can_transition(current_status: str, desired_status: str) -> List[str]:
        """Returns list of user roles that can perform this transition"""
        roles_map = {
            (OrderStatus.PENDING, OrderStatus.ACCEPTED): ["merchant", "admin"],
            (OrderStatus.PENDING, OrderStatus.CANCELLED): ["customer", "admin"],
            (OrderStatus.PENDING, OrderStatus.REJECTED): ["merchant", "admin"],
            (OrderStatus.ACCEPTED, OrderStatus.PREPARING): ["merchant", "admin"],
            (OrderStatus.PREPARING, OrderStatus.READY_FOR_DELIVERY): ["merchant", "admin"],
            (OrderStatus.READY_FOR_DELIVERY, OrderStatus.PICKED_UP): ["driver", "admin"],
            (OrderStatus.PICKED_UP, OrderStatus.ON_TRANSIT): ["driver", "admin"],
            (OrderStatus.ON_TRANSIT, OrderStatus.COMPLETED): ["driver", "admin"],
            # Cancellations
            (OrderStatus.ACCEPTED, OrderStatus.CANCELLED): ["customer", "merchant", "admin"],
            (OrderStatus.PREPARING, OrderStatus.CANCELLED): ["merchant", "admin"],
        }
        
        try:
            current = OrderStatus(current_status)
            desired = OrderStatus(desired_status)
            return roles_map.get((current, desired), ["admin"])
        except ValueError:
            return ["admin"]