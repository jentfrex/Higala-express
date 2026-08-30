import models
from database import SessionLocal
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_database():
    db = SessionLocal()
    try:
        # Check if test customer already exists
        existing_user = (
            db.query(models.User)
            .filter(models.User.username == "test_customer")
            .first()
        )

        if not existing_user:
            hashed_pw = pwd_context.hash("password123")

            # 1. Create Test Customers
            customer1 = models.User(
                username="test_customer",
                hashed_password=hashed_pw,
                role="customer",
                wallet_balance=1000.0,
            )
            customer2 = models.User(
                username="jane_customer",
                hashed_password=hashed_pw,
                role="customer",
                wallet_balance=500.0,
            )
            db.add_all([customer1, customer2])

            # 2. Create Test Drivers
            driver1 = models.User(
                username="test_driver",
                hashed_password=hashed_pw,
                role="driver",
                wallet_balance=1000.0,
                status="offline",
            )
            driver2 = models.User(
                username="speedy_driver",
                hashed_password=hashed_pw,
                role="driver",
                wallet_balance=750.0,
                status="online",
            )
            db.add_all([driver1, driver2])
            db.commit()

            # 3. Create Sample Orders (Required for foreign keys in tickets/reviews)
            order1 = models.Order(
                item_description="Groceries package",
                pickup_location="CdeO Uptown",
                dropoff_location="CdeO Downtown",
                price=100.0,
                status="delivered",
                customer_id=customer1.id,
                driver_id=driver1.id,
                landmark_description="Near the main church",
                customer_latitude=8.4542,
                customer_longitude=124.6319
            )
            order2 = models.Order(
                item_description="Document delivery",
                pickup_location="Agora Market",
                dropoff_location="Limketkai Center",
                price=75.0,
                status="completed",
                customer_id=customer2.id,
                driver_id=driver2.id,
                landmark_description="Beside the mall entrance",
                customer_latitude=8.4851,
                customer_longitude=124.6472
            )
            db.add_all([order1, order2])
            db.commit()

            print("Successfully seeded users and base orders!")
        else:
            print("Database already contains seed data.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()