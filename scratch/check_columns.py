import psycopg2
from config import settings

def check_columns():
    conn = psycopg2.connect(settings.database_url)
    cur = conn.cursor()
    
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'applications'")
    columns = [row[0] for row in cur.fetchall()]
    
    print("Columns in 'applications' table:")
    for col in sorted(columns):
        print(f"- {col}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_columns()
