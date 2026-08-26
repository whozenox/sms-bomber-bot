# database.py

import sqlite3
import json
from datetime import datetime

DB_NAME = 'users.db'

def init_db():
    """Initialize database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        coins INTEGER DEFAULT 0,
        total_bombs INTEGER DEFAULT 0,
        referred_by INTEGER DEFAULT 0,
        referral_code TEXT,
        join_date TEXT,
        is_admin INTEGER DEFAULT 0
    )''')
    
    # Referrals table
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        date TEXT
    )''')
    
    # Transactions table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        type TEXT,
        description TEXT,
        date TEXT
    )''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    """Get user data"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, referral_code=None):
    """Create new user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return False
    
    # Generate referral code
    import random
    import string
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Check if referred by someone
    referred_by = 0
    if referral_code:
        c.execute("SELECT user_id FROM users WHERE referral_code = ?", (referral_code,))
        ref_user = c.fetchone()
        if ref_user:
            referred_by = ref_user[0]
    
    # Create user
    c.execute('''INSERT INTO users 
        (user_id, username, first_name, coins, referral_code, referred_by, join_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_id, username, first_name, 5, ref_code, referred_by, datetime.now().isoformat()))
    
    # If referred, add bonus to referrer
    if referred_by:
        # Add 5 coins to referrer
        c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (5, referred_by))
        # Log transaction
        c.execute('''INSERT INTO transactions (user_id, amount, type, description, date)
            VALUES (?, ?, ?, ?, ?)''',
            (referred_by, 5, 'credit', f'Referral bonus from {username}', datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return True

def add_coins(user_id, amount, description):
    """Add coins to user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    c.execute('''INSERT INTO transactions (user_id, amount, type, description, date)
        VALUES (?, ?, ?, ?, ?)''',
        (user_id, amount, 'credit', description, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def deduct_coins(user_id, amount, description):
    """Deduct coins from user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user or user[0] < amount:
        conn.close()
        return False
    c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, user_id))
    c.execute('''INSERT INTO transactions (user_id, amount, type, description, date)
        VALUES (?, ?, ?, ?, ?)''',
        (user_id, amount, 'debit', description, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_balance(user_id):
    """Get user coin balance"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_referral_count(user_id):
    """Get referral count"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_user_stats(user_id):
    """Get user statistics"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins, total_bombs, referred_by FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return {'coins': user[0], 'total_bombs': user[1], 'referred_by': user[2]}
    return None

def add_bomb_count(user_id):
    """Increment bomb count"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET total_bombs = total_bombs + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    """Get all users (for admin)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, coins, total_bombs FROM users ORDER BY coins DESC")
    users = c.fetchall()
    conn.close()
    return users

def get_transactions(user_id, limit=10):
    """Get user transactions"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT amount, type, description, date FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?", 
              (user_id, limit))
    transactions = c.fetchall()
    conn.close()
    return transactions

def is_admin(user_id):
    """Check if user is admin"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1

def make_admin(user_id):
    """Make user admin"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()