import psycopg2
from config import settings

def migrate():
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Adding missing columns to 'applications' table...")
    
    try:
        cur.execute("ALTER TABLE applications ADD COLUMN follow_up_sent BOOLEAN DEFAULT FALSE")
        print("- Added follow_up_sent")
    except Exception as e:
        print(f"- follow_up_sent already exists or error: {e}")
        
    try:
        cur.execute("ALTER TABLE applications ADD COLUMN form_fields_filled INTEGER")
        print("- Added form_fields_filled")
    except Exception as e:
        print(f"- form_fields_filled already exists or error: {e}")
        
    try:
        cur.execute("ALTER TABLE applications ADD COLUMN form_fields_total INTEGER")
        print("- Added form_fields_total")
    except Exception as e:
        print(f"- form_fields_total already exists or error: {e}")
    
    cur.close()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
