import os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+psycopg://")
engine = create_engine(db_url)
with engine.connect() as conn:
    print("=== TABLES BY SCHEMA ===")
    cols = conn.execute(text("""
        SELECT table_schema, table_name, column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name IN ('conversations', 'messages') 
        ORDER BY table_schema, table_name, ordinal_position
    """)).fetchall()
    for col in cols:
        print(f"  {col[0]}.{col[1]} -> {col[2]}: {col[3]} (nullable: {col[4]}, default: {col[5]})")

    print("\n=== FOREIGN KEYS ===")
    fks = conn.execute(text("""
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid IN ('conversations'::regclass, 'messages'::regclass)
    """)).fetchall()
    for fk in fks:
        print(f"  {fk[0]}: {fk[1]}")
