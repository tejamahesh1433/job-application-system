import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from utils.database import engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if 'applications' in inspector.get_table_names():
        columns = inspector.get_columns('applications')
        print("Columns in 'applications':")
        for col in columns:
            print(f" - {col['name']}: {col['type']}")
    else:
        print("Table 'applications' not found.")
except Exception as e:
    print(f"Error: {e}")
