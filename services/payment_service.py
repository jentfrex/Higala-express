# services/payment_service.py
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from models import (
    Payment, PaymentStatus, PaymentMethod, MasterOrder, 
    MerchantCommission, BankTransferRequest, Order, User
)
import uuid

class PaymentService:
    
    @staticmethod
    def generate_reference_number(user_id: int) -> str:
        """Generate a unique payment reference (e.g., HG-20240901-ABC123)"""
        date_str = datetime.utcnow().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"HG-{date_str}-{unique_id}"
    
    @staticmethod
    def create_payment(
        db: Session,
        master_order_id: int,
        user_id: int,
        amount: float,
        payment_method: str
    ) -> Payment:
        """Create a payment record"""
        payment = Payment(
            master_order_id=master_order_id,
            user_id=user_id,
            amount=amount,
            payment_method=payment_method,
            status=PaymentStatus.PENDING,
            transaction_reference=PaymentService.generate_reference_number(user_id)
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment
    
    @staticmethod
    def confirm_payment(db: Session, payment_id: int) -> Payment:
        """Mark payment as completed"""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if payment:
            payment.status = PaymentStatus.COMPLETED
            payment.payment_date = datetime.utcnow()
            db.commit()
            db.refresh(payment)
        return payment
    
    @staticmethod
    def create_bank_transfer_request(
        db: Session,
        user_id: int,
        order_id: int,
        bank_name: str,
        account_name: str,
        account_number: str,
        amount: float,
        validity_hours: int = 24
    ) -> BankTransferRequest:
        """Create a bank transfer payment request"""
        reference = PaymentService.generate_reference_number(user_id)
        deadline = datetime.utcnow() + timedelta(hours=validity_hours)
        
        request = BankTransferRequest(
            user_id=user_id,
            order_id=order_id,
            bank_name=bank_name,
            account_name=account_name,
            account_number=account_number,
            amount=amount,
            reference_number=reference,
            status="awaiting_payment",
            payment_deadline=deadline
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request
    
    @staticmethod
    def confirm_bank_transfer(db: Session, reference_number: str) -> Optional[BankTransferRequest]:
        """Admin confirms bank transfer receipt"""
        request = db.query(BankTransferRequest).filter(
            BankTransferRequest.reference_number == reference_number
        ).first()
        
        if request:
            request.status = "payment_confirmed"
            db.commit()
            db.refresh(request)
        return request
    
    @staticmethod
    def calculate_merchant_commission(
        db: Session,
        order_id: int,
        merchant_id: int,
        gross_amount: float,
        commission_rate: float = 0.10
    ) -> MerchantCommission:
        """Calculate and record merchant commission"""
        commission_amount = gross_amount * commission_rate
        merchant_payout = gross_amount - commission_amount
        
        commission = MerchantCommission(
            order_id=order_id,
            merchant_id=merchant_id,
            gross_amount=gross_amount,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            merchant_payout=merchant_payout,
            status="pending"
        )
        db.add(commission)
        db.commit()
        db.refresh(commission)
        return commission
    
    @staticmethod
    def process_order_payments(
        db: Session,
        master_order_id: int,
        amount: float,
        payment_method: str,
        user_id: int
    ) -> dict:
        """Main payment processing flow"""
        try:
            # 1. Create payment record
            payment = PaymentService.create_payment(
                db, master_order_id, user_id, amount, payment_method
            )
            
            # 2. If wallet, immediately confirm
            if payment_method == PaymentMethod.WALLET:
                PaymentService.confirm_payment(db, payment.id)
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "status": "completed",
                    "message": f"Wallet payment processed successfully",
                    "reference": payment.transaction_reference
                }
            
            # 3. If bank transfer, create request
            elif payment_method == PaymentMethod.BANK_TRANSFER:
                # Get merchant bank details (could be stored in User model or config)
                bank_request = PaymentService.create_bank_transfer_request(
                    db=db,
                    user_id=user_id,
                    order_id=master_order_id,
                    bank_name="BDO Unibank",  # Placeholder
                    account_name="Higala Express Inc.",
                    account_number="123456789",
                    amount=amount
                )
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "status": "awaiting_payment",
                    "message": "Bank transfer details sent",
                    "reference": bank_request.reference_number,
                    "bank_details": {
                        "bank": bank_request.bank_name,
                        "account_name": bank_request.account_name,
                        "account_number": bank_request.account_number,
                        "amount": bank_request.amount,
                        "deadline": bank_request.payment_deadline.isoformat()
                    }
                }
            
            # 4. If Cash on Delivery
            elif payment_method == PaymentMethod.CASH_ON_DELIVERY:
                # Don't confirm yet; waiting for driver pickup
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "status": "pending",
                    "message": "Cash on delivery - payment collected at delivery",
                    "reference": payment.transaction_reference
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }