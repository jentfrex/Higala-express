import sqlite3
from datetime import datetime

conn = sqlite3.connect("higala_express.db")
cursor = conn.cursor()

try:
    # Insert support tickets referencing valid user_id (1, 2) and order_id (1)
    cursor.execute('''
        INSERT INTO support_tickets (user_id, order_id, subject, description, status, is_deleted, created_at, updated_at)
        VALUES 
        (1, 1, 'Late Delivery', 'My food arrived 30 minutes later than estimated.', 'open', 0, ?, ?),
        (2, NULL, 'Payment Issue', 'Charged twice for my subscription.', 'resolved', 0, ?, ?)
    ''', (datetime.utcnow(), datetime.utcnow(), datetime.utcnow(), datetime.utcnow()))

    # Insert reviews referencing valid order_id, customer_id, driver_id
    cursor.execute('''
        INSERT INTO reviews (order_id, customer_id, driver_id, merchant_id, rating, comment, is_deleted, created_at, updated_at)
        VALUES 
        (1, 1, 1, 1, 5, 'Great packaging and friendly driver!', 0, ?, ?),
        (2, 2, 2, 1, 3, 'Food was okay, but a bit cold.', 0, ?, ?)
    ''', (datetime.utcnow(), datetime.utcnow(), datetime.utcnow(), datetime.utcnow()))

    conn.commit()
    print('Successfully added sample data to support_tickets and reviews!')
except Exception as e:
    print(f'Error seeding data: {e}')
    conn.rollback()
finally:
    conn.close()