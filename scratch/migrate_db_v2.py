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

    print("Migrating 'jobs' table...")
    add_column("jobs", "required_skills", "JSONB DEFAULT '{}'")
    add_column("jobs", "nice_to_haves", "JSONB DEFAULT '[]'")
    add_column("jobs", "responsibilities", "JSONB DEFAULT '[]'")
    add_column("jobs", "company_size", "VARCHAR(50)")

    print("\nMigrating 'resumes' table...")
    add_column("resumes", "keyword_match_score", "FLOAT")
    add_column("resumes", "resume_content", "TEXT")
    add_column("resumes", "resume_json", "JSONB")
    add_column("resumes", "customization_details", "JSONB DEFAULT '{}'")
    add_column("resumes", "interviews_generated", "INTEGER DEFAULT 0")
    add_column("resumes", "offers_generated", "INTEGER DEFAULT 0")
    add_column("resumes", "customized_for_job_id", "INTEGER REFERENCES jobs(id)")

    cur.close()
    conn.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    migrate()
