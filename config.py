# config.py
# ULTIMATE SMS BOMBER BOT - FINAL

import os
from dotenv import load_dotenv

load_dotenv()

# ========================================
# 🔐 BOT TOKEN
# ========================================
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ========================================
# 👑 OWNER & ADMINS
# ========================================
OWNER_ID = int(os.getenv('OWNER_ID', 8112149031))
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

# ========================================
# 📢 CREDITS
# ========================================
BOT_NAME = "💣 SMS BOMBER"
VERSION = "v6.0"
OWNER = "@lordzenox"
CHANNEL1 = "@zenoxtool"
CHANNEL2 = "@Dev_Null_X_NODE_JS"

# ========================================
# 💰 COIN SYSTEM - ONLY 3 OPTIONS
# ========================================
FREE_COINS = 11
REFERRAL_BONUS = 10
MAX_SMS_LIMIT = 10000

# Pricing - Only 3 Options
BOMB_PRICES = {
    200: 2,
    500: 5,
    'unlimited': 8
}

def get_price(count):
    if count == MAX_SMS_LIMIT:
        return BOMB_PRICES['unlimited']
    return BOMB_PRICES.get(count, 2)

# ========================================
# ⚙️ SPEED SETTINGS - 3 OPTIONS
# ========================================
SPEED_SETTINGS = {
    'slow': {
        'delay': 0.05,
        'timeout': 3,
        'apis': 300,
        'label': '🐢 SLOW',
        'description': 'Stable & Safe',
        'emoji': '🐢'
    },
    'medium': {
        'delay': 0.02,
        'timeout': 2,
        'apis': 500,
        'label': '⚡ MEDIUM',
        'description': 'Balanced Speed',
        'emoji': '⚡'
    },
    'fast': {
        'delay': 0.005,
        'timeout': 1,
        'apis': 800,
        'label': '🚀 FAST',
        'description': 'Maximum Speed',
        'emoji': '🚀'
    }
}

# ========================================
# 📁 FILES
# ========================================
DB_NAME = 'bomber.db'
SERVICES_FILE = 'services.json'

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found!")

print("✅ Configuration loaded!")
print("💰 Pricing: 200→2 | 500→5 | Unlimited→8")
print("⚡ Speed: 🐢 SLOW | ⚡ MEDIUM | 🚀 FAST")
