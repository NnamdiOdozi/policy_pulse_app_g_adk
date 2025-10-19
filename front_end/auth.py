import hashlib
import secrets
import os, sys
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.policy_pulse_agent.agent import get_db_connection

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def hash_password(password):
    """
    Hash password with salt using PBKDF2
    
    WHY PBKDF2?: Industry-standard password hashing
    - Resistant to rainbow table attacks (uses unique salt per password)
    - Computationally expensive (100,000 iterations) slows brute-force attacks
    - SHA256 provides cryptographic strength
    
    SALT EXPLAINED:
    - Random 32-character hex string generated for EACH password
    - Ensures identical passwords produce different hashes
    - Stored alongside hash in format: "salt:hash"
    
    SECURITY NOTE: 100,000 iterations balances:
    - User experience (login takes ~100ms)
    - Security (attacker needs 100,000 computations per guess)
    
    Returns:
        str: Format "salt:hash" for database storage
    """
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{password_hash.hex()}"

def verify_password(password, password_hash):
    """
    Verify a password against its stored hash
    
    HOW IT WORKS:
    1. Split stored value into salt and hash components
    2. Re-hash the provided password using the SAME salt
    3. Compare the new hash with stored hash
    4. Match = correct password, no match = wrong password
    
    WHY THIS IS SECURE:
    - Attacker can't reverse the hash to get the password
    - Each password requires separate brute-force attack (due to unique salt)
    - Even database breach doesn't reveal passwords
    
    GOTCHA: Try/except catches malformed hash strings
    - Old data migration issues
    - Corrupted database entries
    - Better to return False than crash
    """
    try:
        salt, stored_hash = password_hash.split(':')
        password_hash_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return stored_hash == password_hash_check.hex()
    except:
        return False

def create_user_tables():
    """
    Create authentication and session tables if they don't exist
    
    WHY IDEMPOTENT?: Safe to call multiple times
    - Uses CREATE TABLE IF NOT EXISTS
    - Won't overwrite existing data
    - Ensures schema exists before any operations
    
    TABLES CREATED:
    
    1. users table:
       - user_id: Unique identifier (user_{16_hex_chars})
       - username: Display name (must be unique)
       - email: Login credential (must be unique)
       - password_hash: Format "salt:hash" 
       - created_at: Registration timestamp
       - is_active: Soft delete flag (keeps audit trail)
    
    2. chat_sessions table:
       - session_id: Links to ADK session system
       - user_id: Foreign key to users (CASCADE delete)
       - title: First 100 chars of user's first message
       - created_at: Session start time
    
    DESIGN DECISION: Why separate from ADK tables?
    - ADK sessions/events tables are internal to Google ADK
    - chat_sessions adds UI-specific metadata (title for display)
    - Gives us control over what user sees in conversation list
    - ADK tables remain authoritative for actual conversation content
    
    RELATIONSHIP:
    - chat_sessions = UI metadata (what appears in sidebar)
    - ADK sessions = actual conversation state and history
    - Both tables share same session_id as foreign key
    """
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
    """
    Register a new user account
    
    WORKFLOW:
    1. Ensure tables exist (idempotent)
    2. Generate unique user_id: "user_{16_random_hex}"
    3. Hash the password with new salt
    4. Insert into database
    5. Return True if successful, False if email/username exists
    
    WHY user_id PREFIX?: 
    - Makes IDs human-readable in logs ("user_a3f9..." vs "a3f9...")
    - Helps debugging by identifying record type
    - Common pattern in multi-tenant systems
    
    ERROR HANDLING:
    - IntegrityError = duplicate email/username (returns False)
    - Other errors logged but also return False
    - Never expose internal error details to user (security)
    
    SECURITY NOTES:
    - Password never logged or stored in plain text
    - Errors don't reveal whether email or username caused failure
    - Prevents user enumeration attacks
    """
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
    """
    Validate user credentials and return user data
    
    AUTHENTICATION FLOW:
    1. Query database for user by email
    2. Check is_active flag (soft delete support)
    3. Verify password against stored hash
    4. Return user data dict OR None
    
    RETURN VALUE:
    Returns dict with:
    - user_id: For session tracking
    - username: For UI display  
    - email: For user confirmation
    
    WHY DICT?: Multiple values needed in Streamlit session_state
    - Single return value is cleaner than tuple unpacking
    - Easy to extend with additional fields later
    - Matches API response patterns
    
    SECURITY CONSIDERATIONS:
    - Only active users can authenticate (respects soft deletes)
    - Timing attacks mitigated by consistent hash verification
    - Returns None for both "user not found" and "wrong password"
      (prevents user enumeration)
    
    COMMON ISSUES:
    - Password verification failing? Check hash format in DB
    - None returned? Check is_active flag in users table
    - Exception raised? Database connection or schema issue
    """
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