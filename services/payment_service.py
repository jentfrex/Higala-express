# services/payment_service.py - Production Ready (Wallet Deduction & Multi-Vendor Settlement Safe)
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import uuid

from models import (
    Payment, PaymentStatus, PaymentMethodEnum, MasterOrder, 
    MerchantCommission, BankTransferRequest, Order, User
)

class PaymentService:
    
    @staticmethod
    def generate_reference_number(user_id: int) -> str:
        """Generate a unique payment reference (e.g., HG-20260902-ABC123)"""
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
        db.flush() # Flush to assign ID without forcing early outer commit
        return payment
    
    @staticmethod
    def confirm_payment(db: Session, payment_id: int) -> Payment:
        """Mark payment as completed"""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if payment:
            payment.status = PaymentStatus.COMPLETED
            payment.payment_date = datetime.utcnow()
            db.flush()
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
        db.flush()
        return request
    
    @staticmethod
    def confirm_bank_transfer(db: Session, reference_number: str) -> Optional[BankTransferRequest]:
        """Admin confirms bank transfer receipt"""
        request = db.query(BankTransferRequest).filter(
            BankTransferRequest.reference_number == reference_number
        ).first()
        
        if request:
            request.status = "payment_confirmed"
            db.flush()
        return request
    
    @staticmethod
    def calculate_merchant_commission(
        db: Session,
        order_id: int,
        merchant_id: int,
        gross_amount: float,
        commission_rate: float = 0.20  # Updated to standard 20% platform commission
    ) -> MerchantCommission:
        """Calculate and record merchant commission"""
        commission_amount = round(gross_amount * commission_rate, 2)
        merchant_payout = round(gross_amount - commission_amount, 2)
        
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
        db.flush()
        return commission
    
    @staticmethod
    def process_order_payments(
        db: Session,
        master_order_id: int,
        amount: float,
        payment_method: str,
        user_id: int
    ) -> dict:
        """Main payment processing flow with safe wallet ledger deduction"""
        try:
            norm_method = payment_method.lower()

            # 1. Create payment record
            payment = PaymentService.create_payment(
                db, master_order_id, user_id, amount, norm_method
            )
            
            # 2. If wallet, deduct balance and immediately confirm
            if norm_method == "wallet":
                user = db.query(User).filter(User.id == user_id).with_for_update().first()
                if not user:
                    raise ValueError("User account not found for wallet debit")
                
                current_bal = user.wallet_balance or 0.0
                if current_bal < amount:
                    raise ValueError(f"Insufficient wallet funds. Balance: ₱{current_bal:.2f}, Required: ₱{amount:.2f}")
                
                # Deduct balance safely
                user.wallet_balance = round(current_bal - amount, 2)
                
                PaymentService.confirm_payment(db, payment.id)
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "status": "completed",
                    "message": "Wallet payment processed and deducted successfully",
                    "reference": payment.transaction_reference
                }
            
            # 3. If bank transfer, QR Ph, or GCash, create bank/digital transfer request
            elif norm_method in ["bank_transfer", "gcash", "qr_ph"]:
                bank_request = PaymentService.create_bank_transfer_request(
                    db=db,
                    user_id=user_id,
                    order_id=master_order_id,
                    bank_name="BDO / GCash QRPh Gateway",
                    account_name="Higala Express Inc.",
                    account_number="1234-5678-9012",
                    amount=amount
                )
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "status": "awaiting_payment",
                    "message": "Digital payment transfer details generated",
                    "reference": bank_request.reference_number,
                    "bank_details": {
                        "bank": bank_request.bank_name,
                        "account_name": bank_request.account_name,
                        "account_number": bank_request.account_number,
                        "amount": bank_request.amount,
                        "deadline": bank_request.payment_deadline.isoformat()
                    }
                }
            
            # 4. If Cash on Delivery (COD)
            elif norm_method in ["cash_on_delivery", "cod"]:
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "status": "pending",
                    "message": "Cash on delivery - payment will be collected by rider",
                    "reference": payment.transaction_reference
                }
            
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }