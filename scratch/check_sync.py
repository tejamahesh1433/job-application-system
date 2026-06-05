import psycopg2
from config import settings
from utils.database import Base, engine
from sqlalchemy import inspect

def check_sync():
    # Get columns from models
    inspector = inspect(engine)
    
    for table_name in inspector.get_table_names():
        print(f"\nChecking table: {table_name}")
        db_cols = {col['name'] for col in inspector.get_columns(table_name)}
        
        # This is a bit tricky with SQLAlchemy Base, but we can try to find the model
        model = None
        for cls in Base.__subclasses__():
            if getattr(cls, '__tablename__', None) == table_name:
                model = cls
                break
        
        if model:
            model_cols = {c.key for c in model.__table__.columns}
            missing_in_db = model_cols - db_cols
            missing_in_model = db_cols - model_cols
            
            if missing_in_db:
                print(f"  [!] Missing in DB: {missing_in_db}")
            else:
                print("  [OK] All model columns present in DB")
                
            if missing_in_model:
                print(f"  [?] Extra in DB: {missing_in_model}")
        else:
            print("  [?] No matching model found")

if __name__ == "__main__":
    check_sync()
