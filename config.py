# config.py
# ULTIMATE SMS BOMBER BOT - CONFIGURATION

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ========================================
# 🔐 BOT TOKEN (from .env)
# ========================================
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ========================================
# 👑 ADMIN IDs (from .env)
# ========================================
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

# ========================================
# 📢 CREDITS & CHANNELS
# ========================================
BOT_NAME = os.getenv('BOT_NAME', 'SMS BOMBER')
VERSION = os.getenv('VERSION', 'v5.0')
OWNER = os.getenv('OWNER', '@lordzenox')
CHANNEL1 = os.getenv('CHANNEL1', '@zenoxtool')
CHANNEL2 = os.getenv('CHANNEL2', '@ghostpyo')

# ========================================
# 💰 COIN SYSTEM
# ========================================
BOMB_COST = int(os.getenv('BOMB_COST', 2))
FREE_COINS = int(os.getenv('FREE_COINS', 5))
REFERRAL_BONUS = int(os.getenv('REFERRAL_BONUS', 5))
MAX_SMS_PER_BOMB = int(os.getenv('MAX_SMS_PER_BOMB', 10000))

# ========================================
# ⚙️ API SETTINGS
# ========================================
API_TIMEOUT = int(os.getenv('API_TIMEOUT', 5))
REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', 0.3))
MAX_APIS_PER_BOMB = int(os.getenv('MAX_APIS_PER_BOMB', 200))

# ========================================
# 📁 FILES
# ========================================
DB_NAME = os.getenv('DB_NAME', 'bomber.db')
SERVICES_FILE = os.getenv('SERVICES_FILE', 'services.json')

# ========================================
# ⚠️ Check if token exists
# ========================================
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in .env file!")

# ========================================
# 🎨 EMOJIS
# ========================================
EMOJIS = {
    'fire': '🔥',
    'money': '💰',
    'bomb': '💣',
    'check': '✅',
    'cross': '❌',
    'crown': '👑',
    'user': '👤',
    'stats': '📊',
    'refer': '👥',
    'help': '📚',
    'warning': '⚠️',
    'rocket': '🚀'
}

print("✅ Configuration loaded successfully!")
