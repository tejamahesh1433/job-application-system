import os
import sys
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from utils.database import engine
    with engine.connect() as conn:
        print("Adding columns...")
        # Check if they exist first to avoid errors
        from sqlalchemy import inspect
        existing_cols = [c['name'] for c in inspect(engine).get_columns('applications')]
        
        if 'application_tracking_id' not in existing_cols:
            conn.execute(text('ALTER TABLE applications ADD COLUMN application_tracking_id VARCHAR(100)'))
            print(" - Added application_tracking_id")
        
        if 'response_received' not in existing_cols:
            conn.execute(text('ALTER TABLE applications ADD COLUMN response_received BOOLEAN DEFAULT FALSE'))
            print(" - Added response_received")
            
        if 'interview_scheduled' not in existing_cols:
            conn.execute(text('ALTER TABLE applications ADD COLUMN interview_scheduled BOOLEAN DEFAULT FALSE'))
            print(" - Added interview_scheduled")
            
        if 'response_type' not in existing_cols:
            conn.execute(text('ALTER TABLE applications ADD COLUMN response_type VARCHAR(50)'))
            print(" - Added response_type")
            
        conn.commit()
    print("Done.")
except Exception as e:
    print(f"Error: {e}")
