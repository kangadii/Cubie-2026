"""
Authentication module for CubieHelp

Provides password hashing, verification, and user authentication functions.
"""

import bcrypt
import os
from typing import Dict, Optional
from database import run_query


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    
    Args:
        password: Plain text password (e.g., "Cubie@2025")
    
    Returns:
        Hashed password string (e.g., "$2b$12$abcd...")
    
    Example:
        >>> hashed = hash_password("MySecretPass123")
        >>> print(hashed)  # "$2b$12$..."
    """
    # Convert password to bytes
    password_bytes = password.encode('utf-8')
    
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds is secure and reasonably fast
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Password user just typed
        hashed_password: Stored hash from database
    
    Returns:
        True if password matches, False otherwise
    
    Example:
        >>> stored_hash = "$2b$12$..."
        >>> verify_password("Cubie@2025", stored_hash)
        True
        >>> verify_password("WrongPassword", stored_hash)
        False
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate user credentials against database.
    
    Args:
        username: Username to check (e.g., "TCube360")
        password: Password to verify (e.g., "Cubie@2025")
    
    Returns:
        Dictionary with user info if valid, None if invalid
        Example: {"UserID": 1, "UserName": "TCube360"}
    
    Process:
        1. Look up username in UserProfile
        2. Get corresponding password hash from UserCredentials
        3. Verify password matches hash
        4. Return user data if valid, None if invalid
    """
    try:
        # Step 1: Look up user in UserProfile by username
        user_query = """
        SELECT OID, UserName, EmailId
        FROM UserProfile
        WHERE UserName = %s
        """
        user_df = run_query(user_query, (username,))
        
        if user_df.empty:
            print(f"Authentication failed: User '{username}' not found")
            return None
        
        user_id = int(user_df.iloc[0]['OID'])
        user_name = user_df.iloc[0]['UserName']
        email = user_df.iloc[0].get('EmailId', '')
        
        # Step 2: Get password hash from UserCredentials
        cred_query = """
        SELECT PasswordHash
        FROM UserCredentials
        WHERE OID = %s
        """
        cred_df = run_query(cred_query, (user_id,))
        
        if cred_df.empty:
            print(f"Authentication failed: No credentials found for OID {user_id}")
            return None
        
        stored_hash = cred_df.iloc[0]['PasswordHash']
        
        # Step 3: Verify password
        if verify_password(password, stored_hash):
            print(f"Authentication successful: {username}")
            return {
                "OID": user_id,
                "UserName": user_name,
                "EmailId": email
            }
        else:
            print(f"Authentication failed: Invalid password for '{username}'")
            return None
            
    except Exception as e:
        print(f"Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_user_credentials(oid: int, password: str) -> bool:
    """
    Create credentials for an existing user.
    
    Args:
        oid: OID from UserProfile table
        password: Plain text password to hash and store
    
    Returns:
        True if successful, False otherwise
    
    Example:
        >>> create_user_credentials(1, "Cubie@2025")
        True
    """
    try:
        from database import DB_SERVER, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
        import pymssql
        
        # Hash the password
        password_hash = hash_password(password)
        
        # Insert into UserCredentials
        conn = pymssql.connect(
            server=DB_SERVER,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO UserCredentials (OID, PasswordHash, LastLogin, CreatedDate)
            VALUES (%s, %s, GETDATE(), GETDATE())
            """,
            (oid, password_hash)
        )
        conn.commit()
        conn.close()
        
        print(f"Credentials created for OID {oid}")
        return True
        
    except Exception as e:
        print(f"Error creating credentials: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test script - generate hash for initial password
    print("=== Password Hash Generator ===")
    test_password = "Cubie@2025"
    hashed = hash_password(test_password)
    print(f"Password: {test_password}")
    print(f"Hash: {hashed}")
    print(f"\nVerification test: {verify_password(test_password, hashed)}")
