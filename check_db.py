import sqlite3

conn = sqlite3.connect("higala_express.db")
tables_to_check = ['users', 'orders', 'merchants', 'delivery_zones', 'support_tickets', 'reviews']

for table in tables_to_check:
    print(f"\n{'='*10} TABLE: {table} {'='*10}")
    try:
        columns = conn.execute(f"PRAGMA table_info({table});").fetchall()
        print("Columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]}) | NotNull: {col[3]} | PK: {col[5]}")

        sample = conn.execute(f"SELECT * FROM {table} LIMIT 3;").fetchall()
        print("Sample Data:")
        if sample:
            for row in sample:
                print(f"  {row}")
        else:
            print("  (Table is empty)")
    except Exception as e:
        print(f"Error inspecting {table}: {e}")

conn.close()
