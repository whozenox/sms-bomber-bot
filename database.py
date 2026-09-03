# database.py
# ULTIMATE SMS BOMBER BOT - COMPLETE DATABASE

import sqlite3
import random
import string
from datetime import datetime, timedelta
from config import DB_NAME, FREE_COINS, REFERRAL_BONUS

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # USERS TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            coins INTEGER DEFAULT 0,
            total_bombs INTEGER DEFAULT 0,
            total_sms INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            join_date TEXT,
            is_admin INTEGER DEFAULT 0,
            is_owner INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            last_active TEXT,
            total_spent INTEGER DEFAULT 0,
            speed TEXT DEFAULT 'slow'
        )''')
        
        # TRANSACTIONS TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT,
            description TEXT,
            date TEXT
        )''')
        
        # BOMB LOGS TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS bomb_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            target TEXT,
            sms_count INTEGER,
            success INTEGER,
            failed INTEGER,
            cost INTEGER,
            speed TEXT,
            stopped INTEGER DEFAULT 0,
            date TEXT
        )''')
        
        # API STATS TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS api_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_name TEXT,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            last_used TEXT
        )''')
        
        # REFERRALS TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            coins_earned INTEGER DEFAULT 0,
            date TEXT
        )''')
        
        # REDEEM CODES TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS redeem_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            amount INTEGER,
            used_by INTEGER DEFAULT 0,
            is_used INTEGER DEFAULT 0,
            created_by INTEGER,
            created_date TEXT,
            expiry_date TEXT
        )''')
        
        # ADMIN LOGS TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
            date TEXT
        )''')
        
        # USER STATS TABLE
        c.execute('''CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            total_bombs_used INTEGER DEFAULT 0,
            total_sms_sent INTEGER DEFAULT 0,
            total_coins_earned INTEGER DEFAULT 0,
            total_coins_spent INTEGER DEFAULT 0,
            last_bomb_date TEXT,
            first_bomb_date TEXT
        )''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized!")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

# ============================================================
# USER FUNCTIONS
# ============================================================

def get_user(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return c.fetchone()
    except:
        return None
    finally:
        try:
            conn.close()
        except:
            pass

def create_user(user_id, username, first_name, referral_code=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            conn.close()
            return False, "User already exists"
        
        # Generate referral code
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        while True:
            c.execute("SELECT user_id FROM users WHERE referral_code = ?", (ref_code,))
            if not c.fetchone():
                break
            ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        referred_by = 0
        if referral_code:
            c.execute("SELECT user_id FROM users WHERE referral_code = ?", (referral_code,))
            ref_user = c.fetchone()
            if ref_user:
                referred_by = ref_user[0]
                c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (REFERRAL_BONUS, referred_by))
                c.execute('''INSERT INTO transactions (user_id, amount, type, description, date)
                    VALUES (?, ?, ?, ?, ?)''',
                    (referred_by, REFERRAL_BONUS, 'credit', f'Referral from {username}', datetime.now().isoformat()))
                c.execute('''INSERT INTO referrals (referrer_id, referred_id, coins_earned, date)
                    VALUES (?, ?, ?, ?)''',
                    (referred_by, user_id, REFERRAL_BONUS, datetime.now().isoformat()))
        
        from config import OWNER_ID
        is_owner = 1 if user_id == OWNER_ID else 0
        is_admin = 1 if is_owner else 0
        
        c.execute('''INSERT INTO users 
            (user_id, username, first_name, coins, referral_code, referred_by, 
             join_date, last_active, is_admin, is_owner, speed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, username or first_name, first_name, FREE_COINS, ref_code, referred_by,
             datetime.now().isoformat(), datetime.now().isoformat(), is_admin, is_owner, 'slow'))
        
        conn.commit()
        conn.close()
        return True, "User created successfully"
    except Exception as e:
        print(f"❌ Create user error: {e}")
        return False, f"Error: {e}"

# ============================================================
# SPEED FUNCTIONS
# ============================================================

def get_user_speed(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT speed FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 'slow'
    except:
        return 'slow'

def set_user_speed(user_id, speed):
    if speed not in ['slow', 'medium', 'fast']:
        return False
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET speed = ? WHERE user_id = ?", (speed, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# ============================================================
# COIN FUNCTIONS
# ============================================================

def get_balance(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except:
        return 0

def add_coins(user_id, amount, description):
    if amount <= 0:
        return False
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
        c.execute('''INSERT INTO transactions (user_id, amount, type, description, date)
            VALUES (?, ?, ?, ?, ?)''',
            (user_id, amount, 'credit', description, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def deduct_coins(user_id, amount, description):
    if amount <= 0:
        return False
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user or user[0] < amount:
            conn.close()
            return False
        c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, user_id))
        c.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?", (amount, user_id))
        c.execute('''INSERT INTO transactions (user_id, amount, type, description, date)
            VALUES (?, ?, ?, ?, ?)''',
            (user_id, amount, 'debit', description, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def transfer_coins(from_user, to_user, amount):
    if amount <= 0:
        return False, "Amount must be positive"
    if from_user == to_user:
        return False, "Cannot transfer to yourself"
    if not get_user(to_user):
        return False, "User not found"
    if not deduct_coins(from_user, amount, f"Transferred to {to_user}"):
        return False, "Insufficient coins"
    add_coins(to_user, amount, f"Received from {from_user}")
    return True, "Transfer successful"

# ============================================================
# STATS FUNCTIONS
# ============================================================

def update_user_stats(user_id, sms_count, cost):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
        existing = c.fetchone()
        now = datetime.now().isoformat()
        if existing:
            c.execute('''UPDATE user_stats 
                SET total_bombs_used = total_bombs_used + 1,
                    total_sms_sent = total_sms_sent + ?,
                    total_coins_spent = total_coins_spent + ?,
                    last_bomb_date = ?
                WHERE user_id = ?''',
                (sms_count, cost, now, user_id))
        else:
            c.execute('''INSERT INTO user_stats 
                (user_id, total_bombs_used, total_sms_sent, total_coins_spent, first_bomb_date, last_bomb_date)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (user_id, 1, sms_count, cost, now, now))
        conn.commit()
        conn.close()
    except:
        pass

def get_total_active_users():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM user_stats")
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def get_total_bombs_used():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT SUM(total_bombs_used) FROM user_stats")
        result = c.fetchone()[0]
        conn.close()
        return result or 0
    except:
        return 0

def get_total_sms_sent_all():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT SUM(total_sms_sent) FROM user_stats")
        result = c.fetchone()[0]
        conn.close()
        return result or 0
    except:
        return 0

def get_user_stats_detail(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            return {
                'total_bombs': result[2],
                'total_sms': result[3],
                'total_earned': result[4],
                'total_spent': result[5],
                'first_bomb': result[6],
                'last_bomb': result[7]
            }
        return None
    except:
        return None

def get_top_bombers(limit=10):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''SELECT u.user_id, u.username, u.first_name, us.total_bombs_used, us.total_sms_sent
            FROM user_stats us
            JOIN users u ON u.user_id = us.user_id
            ORDER BY us.total_bombs_used DESC
            LIMIT ?''', (limit,))
        result = c.fetchall()
        conn.close()
        return result
    except:
        return []

# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def is_admin(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 1
    except:
        return False

def is_owner(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT is_owner FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 1
    except:
        return False

def is_banned(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 1
    except:
        return False

def ban_user(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def unban_user(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def add_admin(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def remove_admin(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def get_all_admins():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name FROM users WHERE is_admin = 1")
        admins = c.fetchall()
        conn.close()
        return admins
    except:
        return []

def get_user_stats(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT coins, total_bombs, total_sms, referred_by, total_spent FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            return {
                'coins': result[0],
                'total_bombs': result[1],
                'total_sms': result[2],
                'referred_by': result[3],
                'total_spent': result[4]
            }
        return None
    except:
        return None

def get_referral_code(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None

def get_referral_count(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def add_bomb_stats(user_id, target, sms_count, success, failed, cost, speed, stopped=0):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET total_bombs = total_bombs + 1, total_sms = total_sms + ? WHERE user_id = ?", 
                  (sms_count, user_id))
        c.execute('''INSERT INTO bomb_logs (user_id, target, sms_count, success, failed, cost, speed, stopped, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, target, sms_count, success, failed, cost, speed, stopped, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        update_user_stats(user_id, sms_count, cost)
    except:
        pass

def get_bomb_logs(user_id, limit=10):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT target, sms_count, success, failed, cost, speed, stopped, date FROM bomb_logs WHERE user_id = ? ORDER BY date DESC LIMIT ?", 
                  (user_id, limit))
        logs = c.fetchall()
        conn.close()
        return logs
    except:
        return []

def get_transactions(user_id, limit=10):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT amount, type, description, date FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?", 
                  (user_id, limit))
        transactions = c.fetchall()
        conn.close()
        return transactions
    except:
        return []

def get_all_users(limit=1000):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, username, coins, total_bombs, total_sms FROM users ORDER BY coins DESC LIMIT ?", (limit,))
        users = c.fetchall()
        conn.close()
        return users
    except:
        return []

def get_total_stats():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT SUM(coins) FROM users")
        total_coins = c.fetchone()[0] or 0
        c.execute("SELECT SUM(total_bombs) FROM users")
        total_bombs = c.fetchone()[0] or 0
        c.execute("SELECT SUM(total_sms) FROM users")
        total_sms = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        total_admins = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        total_banned = c.fetchone()[0]
        conn.close()
        return {
            'users': total_users,
            'coins': total_coins,
            'bombs': total_bombs,
            'sms': total_sms,
            'admins': total_admins,
            'banned': total_banned
        }
    except:
        return {'users': 0, 'coins': 0, 'bombs': 0, 'sms': 0, 'admins': 0, 'banned': 0}

def get_leaderboard(limit=10):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, username, coins, total_bombs, total_sms FROM users ORDER BY coins DESC LIMIT ?", (limit,))
        users = c.fetchall()
        conn.close()
        return users
    except:
        return []

def update_api_stats(api_name, success):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM api_stats WHERE api_name = ?", (api_name,))
        existing = c.fetchone()
        if existing:
            if success:
                c.execute("UPDATE api_stats SET success_count = success_count + 1, last_used = ? WHERE api_name = ?", 
                          (datetime.now().isoformat(), api_name))
            else:
                c.execute("UPDATE api_stats SET fail_count = fail_count + 1, last_used = ? WHERE api_name = ?", 
                          (datetime.now().isoformat(), api_name))
        else:
            c.execute('''INSERT INTO api_stats (api_name, success_count, fail_count, last_used)
                VALUES (?, ?, ?, ?)''',
                (api_name, 1 if success else 0, 0 if success else 1, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

def log_admin_action(admin_id, action, target_id, details):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO admin_logs (admin_id, action, target_id, details, date)
            VALUES (?, ?, ?, ?, ?)''',
            (admin_id, action, target_id, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

def create_redeem_code(code, amount, created_by):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO redeem_codes (code, amount, created_by, created_date, expiry_date)
            VALUES (?, ?, ?, ?, ?)''',
            (code, amount, created_by, datetime.now().isoformat(),
             (datetime.now() + timedelta(days=365)).isoformat()))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def use_redeem_code(user_id, code):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM redeem_codes WHERE code = ? AND is_used = 0", (code,))
        code_data = c.fetchone()
        if not code_data:
            conn.close()
            return False, "❌ Invalid or expired code"
        if code_data[7] and datetime.now().isoformat() > code_data[7]:
            conn.close()
            return False, "❌ Code expired"
        c.execute("UPDATE redeem_codes SET is_used = 1, used_by = ? WHERE code = ?", (user_id, code))
        amount = code_data[2]
        add_coins(user_id, amount, f"Redeemed code: {code}")
        conn.commit()
        conn.close()
        return True, f"✅ Successfully redeemed {amount} coins"
    except:
        return False, "❌ Error redeeming code"

if __name__ == "__main__":
    init_db()
