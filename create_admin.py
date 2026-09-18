from app import create_app
from app.extensions import db, bcrypt
from app.models import User

def create_admin():
    app = create_app()
    with app.app_context():
        print("--- Create Admin Account (Local Setup) ---")
        email = input("Enter email: ").strip().lower()
        
        if not email:
            print("Error: Email is required.")
            return

        # Check if email is already registered
        if User.query.filter_by(email=email).first():
            print("Error: Email already registered.")
            return

        # Derive username from email prefix
        username = email.split('@')[0].capitalize()
        
        password = input("Enter password: ").strip()
        if not password:
            print("Error: Password is required.")
            return

        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        
        admin = User(
            username=username,
            email=email,
            password_hash=hashed,
            role='admin',
            is_verified=True
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print(f"Admin created successfully!")
        print(f"Username: {username}")
        print(f"Email: {email}")

if __name__ == "__main__":
    create_admin()
