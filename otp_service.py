import random
import string
from datetime import datetime, timedelta
import sqlite3
from database import get_db_path

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def store_otp(email, otp):
    """Store OTP in database with expiration time (10 minutes)"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Remove any existing OTP for this email
    c.execute('DELETE FROM otp_storage WHERE email = ?', (email,))
    
    # Store new OTP
    expiration = datetime.now() + timedelta(minutes=10)
    c.execute('''
        INSERT INTO otp_storage (email, otp, expiration)
        VALUES (?, ?, ?)
    ''', (email, otp, expiration))
    
    conn.commit()
    conn.close()

def verify_otp(email, otp):
    """Verify if OTP is valid and not expired"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    c.execute('''
        SELECT otp, expiration 
        FROM otp_storage 
        WHERE email = ?
    ''', (email,))
    
    result = c.fetchone()
    
    if not result:
        return False
    
    stored_otp, expiration = result
    expiration_time = datetime.fromisoformat(expiration)
    
    # Remove the OTP regardless of validity
    c.execute('DELETE FROM otp_storage WHERE email = ?', (email,))
    conn.commit()
    conn.close()
    
    # Check if OTP matches and hasn't expired
    return stored_otp == otp and datetime.now() <= expiration_time
