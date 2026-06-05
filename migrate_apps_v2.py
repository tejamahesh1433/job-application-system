import os
import sys
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from utils.database import engine
    with engine.connect() as conn:
        print("Ensuring all columns exist in 'applications'...")
        from sqlalchemy import inspect
        existing_cols = [c['name'] for c in inspect(engine).get_columns('applications')]
        
        cols_to_add = [
            ('application_tracking_id', 'VARCHAR(255)'),
            ('response_received', 'BOOLEAN DEFAULT FALSE'),
            ('interview_scheduled', 'BOOLEAN DEFAULT FALSE'),
            ('response_type', 'VARCHAR(50)'),
            ('follow_up_date', 'TIMESTAMP'),
            ('interview_probability', 'DOUBLE PRECISION'),
            ('notes', 'TEXT')
        ]
        
        for name, dtype in cols_to_add:
            if name not in existing_cols:
                conn.execute(text(f'ALTER TABLE applications ADD COLUMN {name} {dtype}'))
                print(f" - Added {name}")
            else:
                print(f" - {name} already exists")
            
        conn.commit()
    print("Done.")
except Exception as e:
    print(f"Error: {e}")
