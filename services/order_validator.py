from fastapi import HTTPException

# Define the strict allowed sequence of states
ALLOWED_TRANSITIONS = {
    "pending": ["assigned", "cancelled"],
    "assigned": ["picked_up", "cancelled"],
    "picked_up": ["delivered", "cancelled"],
    "delivered": [],
    "cancelled": []
}

def validate_status_transition(current_status: str, new_status: str):
    """Ensures an order cannot jump invalid states."""
    if current_status == new_status:
        return  # No-op if status isn't changing

    allowed_next_states = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_next_states:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition: Cannot change order status from '{current_status}' to '{new_status}'."
        )