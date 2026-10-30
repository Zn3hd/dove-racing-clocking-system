"""Create the initial chairman account from environment variables. Run once locally."""
import os
from uuid import uuid4
from sqlalchemy import create_engine, text
from app.auth import hash_password

def main():
    email = os.environ["BOOTSTRAP_ADMIN_EMAIL"].strip().lower()
    password = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]
    name = os.environ["BOOTSTRAP_ADMIN_NAME"].strip()
    if len(password) < 12 or not name or "@" not in email:
        raise ValueError("Set a valid name, email, and password of 12+ characters")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT id FROM users WHERE role_code IN ('chairman','president') LIMIT 1")).first()
        if exists:
            raise RuntimeError("An administrator already exists; bootstrap refused")
        conn.execute(text("""INSERT INTO users(id,role_code,full_name,email,password_hash)
            VALUES (:id,'chairman',:name,:email,:password)"""),
            {"id":uuid4(),"name":name,"email":email,"password":hash_password(password)})
    print("Initial chairman account created. Remove bootstrap credentials from your shell.")

if __name__ == "__main__":
    main()
