import os
import sys
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from utils.database import engine
    with engine.connect() as conn:
        res = conn.execute(text('SELECT count(*) FROM users')).fetchone()
        print(f"Users count: {res[0]}")
        if res[0] == 0:
            print("Creating default user...")
            conn.execute(text("INSERT INTO users (email, name) VALUES ('test@example.com', 'Test User')"))
            conn.commit()
            print("User created.")
except Exception as e:
    print(f"Error: {e}")
