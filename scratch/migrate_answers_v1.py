import psycopg2
from config import settings

def migrate():
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    cur = conn.cursor()
    
    # helper to add column safely
    def add_column(table, column, definition):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            print(f"- Added {table}.{column}")
        except Exception as e:
            if "already exists" in str(e):
                print(f"- {table}.{column} already exists")
            else:
                print(f"- Error adding {table}.{column}: {e}")

    print("Migrating 'approved_answers' table...")
    add_column("approved_answers", "category", "VARCHAR(100)")
    add_column("approved_answers", "role_type", "VARCHAR(100)")
    add_column("approved_answers", "version_history", "JSONB DEFAULT '[]'")
    add_column("approved_answers", "interview_outcomes", "JSONB DEFAULT '[]'")
    add_column("approved_answers", "recommender_notes", "TEXT")
    add_column("approved_answers", "weak_indicators", "JSONB DEFAULT '[]'")
    add_column("approved_answers", "company_specific", "VARCHAR(255)")
    
    # Also add index for category
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS ix_approved_answers_category ON approved_answers (category)")
        print("- Created index on category")
    except Exception as e:
        print(f"- Error creating index: {e}")

    cur.close()
    conn.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    migrate()
