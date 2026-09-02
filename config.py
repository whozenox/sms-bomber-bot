# config.py
# ULTIMATE SMS BOMBER BOT - CONFIGURATION

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
CHANNEL1 = "@Dev/_Null/_X/_NODE/_JS"
CHANNEL2 = "@zenoxtool"

# ========================================
# 💰 COIN SYSTEM
# ========================================
BOMB_COST = int(os.getenv('BOMB_COST', 1))  # Per SMS cost
FREE_COINS = int(os.getenv('FREE_COINS', 10))
REFERRAL_BONUS = int(os.getenv('REFERRAL_BONUS', 10))
MAX_SMS_LIMIT = int(os.getenv('MAX_SMS_LIMIT', 10000))
MIN_BOMB_COUNT = 1
MAX_BOMB_COUNT = 10000

# ========================================
# ⚙️ API SETTINGS
# ========================================
API_TIMEOUT = 5
REQUEST_DELAY = 0.2
MAX_APIS_PER_BOMB = 300

# ========================================
# 📁 FILES
# ========================================
DB_NAME = 'bomber.db'
SERVICES_FILE = 'services.json'

# ========================================
# ⚠️ CHECK
# ========================================
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in .env file!")

print("✅ Configuration loaded successfully!")
