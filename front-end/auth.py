import hashlib
import secrets
import os
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get database connection"""
    db_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{password_hash.hex()}"

def verify_password(password, password_hash):
    """Verify password against hash"""
    try:
        salt, stored_hash = password_hash.split(':')
        password_hash_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return stored_hash == password_hash_check.hex()
    except:
        return False

def create_user_tables():
    """Create user authentication tables if they don't exist"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(50) PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Chat sessions metadata table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id VARCHAR(100) PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()

def create_user(username, email, password):
    """Create a new user"""
    try:
        # Ensure tables exist
        create_user_tables()
        
        user_id = f"user_{secrets.token_hex(8)}"
        password_hash = hash_password(password)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, email, password_hash)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, username, email, password_hash))
                conn.commit()
                return True
                
    except psycopg2.IntegrityError:
        # Email or username already exists
        return False
    except Exception as e:
        print(f"Error creating user: {e}")
        return False

def authenticate_user(email, password):
    """Authenticate user with email and password"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id, username, email, password_hash
                    FROM users 
                    WHERE email = %s AND is_active = TRUE
                """, (email,))
                
                user = cur.fetchone()
                
                if user and verify_password(password, user['password_hash']):
                    return {
                        'user_id': user['user_id'],
                        'username': user['username'],
                        'email': user['email']
                    }
                return None
                
    except Exception as e:
        print(f"Authentication error: {e}")
        return None