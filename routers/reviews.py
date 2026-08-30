from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

import models
from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/reviews", tags=["Reviews"])

class ReviewCreate(BaseModel):
    order_id: int
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: Optional[str] = None
    driver_id: Optional[int] = None
    merchant_id: Optional[int] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_review(
    review: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Verify that the order exists and is completed
    order = db.query(models.Order).filter(models.Order.id == review.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if order.status.lower() != "completed":
        raise HTTPException(status_code=400, detail="Can only review completed orders")

    # 2. Ensure the user making the request is the customer of the order
    if order.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to review this order")

    # 3. Check if a review for this order already exists
    existing_review = db.query(models.Review).filter(models.Review.order_id == review.order_id).first()
    if existing_review:
        raise HTTPException(status_code=400, detail="You have already reviewed this order")

    # 4. Create and persist the review matching models.py schema
    new_review = models.Review(
        order_id=review.order_id,
        customer_id=current_user.id,
        driver_id=review.driver_id or order.driver_id,
        merchant_id=review.merchant_id or order.merchant_id,
        rating=review.rating,
        comment=review.comment
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    return {
        "success": True,
        "message": "Review submitted successfully",
        "review_id": new_review.id,
        "rating": new_review.rating
    }

@router.get("/")
def get_reviews(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Fetch reviews based on user role matching models.py columns
    if current_user.role == "admin":
        reviews = db.query(models.Review).all()
    elif current_user.role == "driver":
        reviews = db.query(models.Review).filter(models.Review.driver_id == current_user.id).all()
    elif current_user.role == "merchant":
        reviews = db.query(models.Review).filter(models.Review.merchant_id == current_user.id).all()
    else:
        reviews = db.query(models.Review).filter(models.Review.customer_id == current_user.id).all()
        
    return {"reviews": reviews}