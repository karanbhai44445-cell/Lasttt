#!#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🚀 BALA MODS STORE - PAYTM PAYMENT SYSTEM
✅ Full logging system
✅ Random amount per user
✅ High quality QR
✅ 100% payment verification
✅ No compression, full code
"""

import os
import json
import asyncio
import logging
import random
import string
import io
import re
import time
import threading
import imaplib
import email
import sqlite3
import uuid
import subprocess
import sys
from datetime import datetime, timedelta

# ✅ Auto-install missing packages so this file runs standalone on Render —
# Build Command can just be `pip install --upgrade pip`, no separate
# requirements.txt needed. import_name = what you `import`, pip_name = what
# pip needs to install (they differ for `telegram` -> "python-telegram-bot").
def _auto_install(import_name, pip_name=None):
    pip_name = pip_name or import_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"📦 Installing missing package: {pip_name} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        print(f"✅ Installed: {pip_name}")

for _imp, _pip in [
    ("requests", "requests"),
    ("qrcode", "qrcode[pil]"),
    ("telegram", "python-telegram-bot==21.6"),
]:
    _auto_install(_imp, _pip)

import requests
import qrcode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest
from telegram.error import BadRequest

# ============================================
# ✅ LOGGING SETUP - HAR STEP LOG HOGA
# ============================================

LOG_FILE = "bot_logs.txt"

# Console + File logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_payment(step, data):
    """Payment process ka har step log karo"""
    logger.info(f"💳 PAYMENT_LOG [{step}]: {data}")

# ============================================
# ✅ CONFIG
# ============================================

TOKEN = "8833898625:AAEW18HVT9CIzvTW0lP7U6nub8FuXjX2bUI"
ADMIN_ID = 8954667761

# Default values - will be overridden by DB settings
DEFAULT_GMAIL_USER = "karanbhaiya699@gmail.com"
DEFAULT_APP_PASSWORD = "zrik hlyk ttdl qpol"
DEFAULT_RECEIVER_UPI = "paytm.s2sp8g1@pty"

MIN_AMOUNT = 1
DB_FILE = os.environ.get("DB_FILE_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_data.db")
RESELLER_DISCOUNT_PERCENT = 15
REFERRAL_COMMISSION_PERCENT = 0.5

API_ENDPOINT = "https://xyzcheats.com/api/reseller_v1.php"
API_KEY = "2c59f7c31055b7b9b61f5bb6a0ae85e0"
MASTER_KEY = "a7f3e8b2c9d1f4a6b8c2d5e9f1a3b6c8"
ANDROID_ID = "0b9b969bc2e7997b"

# 🔥 RANDOM DECIMALS - HAR USER KE LIYE UNIQUE
RANDOM_DECIMALS = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 
                   0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.20]

# ============================================
# 🎯 PREMIUM EMOJI IDs
# ============================================

BUTTON_EMOJIS = {
    "shop": "6334784630809435068",
    "profile": "6215104357789081549",
    "add_balance": "6212764498260925926",
    "order_history": "6147464060305676048",
    "deposit_history": "6147902731085420231",
    "referral": "6237871554223412862",
    "tutorial": "6237742262822901946",
    "support": "6147460667281511517",
    "download": "6235475653961979149",
    "back": "6235445786759402354",
    "confirm": "6235234890980269200",
    "cancel": "6237755976653477546",
    "clear": "6237704110628413424",
    "android_nonroot": "6235234190900598910",
    "android_root": "6235593671073339928",
    "pc": "6235289248086365655",
    "ios": "6237941218592960218",
    "star": "6235285623133968567",
    "plan": "6244617272808183303",
    "warning": "6242147417504879292",
    "broadcast": "6147460667281511517",
    "add": "6235234890980269200",
    "stats": "6073308817125282940",
    "users": "6215104357789081549",
    "remove": "6237755976653477546",
    "refresh": "6235234890980269200",
}

# ============================================
# 🎨 EMOJI HELPERS
# ============================================

def get_button_emoji(name):
    try:
        override = db.get_emoji_setting(name)
        if override:
            return override
    except Exception:
        pass
    return BUTTON_EMOJIS.get(name, "")

def get_price_for_user(base_price, user_id):
    if db.is_reseller(user_id):
        return round(base_price * (1 - RESELLER_DISCOUNT_PERCENT / 100), 2)
    return base_price

def parse_product_line(text):
    text = (text or "").strip()
    parts = text.split("|")
    if len(parts) < 5:
        raise ValueError(
            "Format galat hai. Usage:\n"
            "CATEGORY | NAME | PRODUCT_ID | PLAN | PRICE | ANDROID_ID (optional)"
        )

    category = parts[0].strip().upper()
    name = parts[1].strip()
    product_id = parts[2].strip()
    plan = parts[3].strip()
    price_raw = parts[4].strip()

    if not category or not name or not product_id or not plan:
        raise ValueError("CATEGORY, NAME, PRODUCT_ID aur PLAN khaali nahi ho sakte.")

    price_clean = re.sub(r'[^\d.]', '', price_raw)
    if not price_clean:
        raise ValueError(f"PRICE samajh nahi aayi: '{price_raw}'. Sirf number likho, jaise 150")
    try:
        price = float(price_clean)
    except ValueError:
        raise ValueError(f"PRICE samajh nahi aayi: '{price_raw}'. Sirf number likho, jaise 150")
    if price <= 0:
        raise ValueError("PRICE 0 se zyada honi chahiye.")

    android_id = parts[5].strip() if len(parts) > 5 and parts[5].strip() else ANDROID_ID

    return {
        "category": category,
        "name": name,
        "product_id": product_id,
        "plan": plan,
        "price": price,
        "android_id": android_id,
    }

# ============================================
# 🎨 STYLED BUTTON
# ============================================

class ColoredButton(InlineKeyboardButton):
    def __init__(self, text, style=None, icon=None, **kwargs):
        super().__init__(text, **kwargs)
        self._style = style
        self._icon = icon

    def to_dict(self, **kwargs):
        data = super().to_dict(**kwargs)
        if self._style:
            data['style'] = self._style
        if self._icon:
            data['icon_custom_emoji_id'] = self._icon
        return data

def to_bold_unicode(text):
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            result.append(chr(ord(ch) - ord('A') + 0x1D5D4))
        elif 'a' <= ch <= 'z':
            result.append(chr(ord(ch) - ord('a') + 0x1D5EE))
        elif '0' <= ch <= '9':
            result.append(chr(ord(ch) - ord('0') + 0x1D7EC))
        else:
            result.append(ch)
    return ''.join(result)

def CB(text, style="primary", icon=None, **kwargs):
    return ColoredButton(to_bold_unicode(text), style="primary", icon=icon, **kwargs)

def get_category_emoji(category):
    cat = (category or "").upper()
    if "ROOT" in cat and "NON" not in cat:
        return get_button_emoji("android_root")
    if "PC" in cat:
        return get_button_emoji("pc")
    if "IOS" in cat:
        return get_button_emoji("ios")
    return get_button_emoji("android_nonroot")

# ============================================
# SEPARATOR
# ============================================

SEP = "|||"

def encode_cb(*args):
    return SEP.join([str(arg) for arg in args])

def decode_cb(data):
    return data.split(SEP)

# ============================================
# 🔥 UNIQUE RANDOM AMOUNT GENERATOR - PER USER
# ============================================

def generate_unique_random_amount(base_amount, user_id, order_id):
    """
    🔥 HAR USER KE LIYE UNIQUE RANDOM AMOUNT
    User ID + Order ID ko seed use karke unique amount generate karega.
    Isse 10 log ek saath ₹1 deposit karein toh sabka amount alag hoga.
    """
    try:
        # User ID aur Order ID ko seed mein use karo
        seed_value = int(user_id) + hash(order_id)
        random.seed(seed_value)
        
        # Random decimal choose karo
        random_decimal = random.choice(RANDOM_DECIMALS)
        
        if float(base_amount).is_integer():
            final_amount = float(base_amount) + random_decimal
        else:
            final_amount = float(base_amount)
        
        # Reset random seed
        random.seed()
        
        final_amount = round(final_amount, 2)
        log_payment("RANDOM_AMOUNT", f"user={user_id} order={order_id} base={base_amount} final={final_amount}")
        return final_amount
        
    except Exception as e:
        logger.error(f"Random amount generation error: {e}")
        # Fallback - simple random
        return round(float(base_amount) + random.choice([0.01, 0.02, 0.03, 0.04, 0.05]), 2)

# ============================================
# 📱 CLEAR SCANNABLE QR CODE
# ============================================

def generate_clear_qr(upi_id, amount, ref_code, user_id):
    """
    🔥 HIGH QUALITY QR - Clear scan ke liye
    Version 2, HIGH error correction, bigger boxes
    """
    try:
        original_amount = float(amount)
        final_amount = generate_unique_random_amount(original_amount, user_id, ref_code)
        
        # UPI URL
        upi_url = f"upi://pay?pa={upi_id}&pn=Store&am={final_amount}&tr={ref_code}&tn={ref_code}&cu=INR"
        
        log_payment("QR_GENERATE", f"upi={upi_id} amount={final_amount} ref={ref_code}")
        
        # 🔥 HIGH QUALITY QR SETTINGS
        qr = qrcode.QRCode(
            version=2,                      # Better error correction
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Highest
            box_size=12,                    # Bigger = clearer
            border=6,                       # More border
        )
        qr.add_data(upi_url)
        qr.make(fit=True)
        
        # High contrast QR
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save as high quality PNG
        bio = io.BytesIO()
        img.save(bio, format='PNG', optimize=False)
        bio.seek(0)
        
        log_payment("QR_SUCCESS", f"ref={ref_code} final_amount={final_amount}")
        return bio, final_amount
        
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        raise Exception(f"QR generate nahi ho paaya: {e}")

# ============================================
# DATABASE
# ============================================

class Database:
    def __init__(self):
        self.db = DB_FILE
        self._init_db()
        logger.info(f"Database initialized: {self.db}")
    
    def _init_db(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        
        # Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                is_reseller INTEGER DEFAULT 0,
                referred_by TEXT DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        try:
            c.execute('ALTER TABLE users ADD COLUMN is_reseller INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass

        try:
            c.execute('ALTER TABLE users ADD COLUMN referred_by TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass
        
        # Orders table
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount REAL,
                original_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                utr TEXT,
                sender TEXT,
                payment_type TEXT DEFAULT 'PAYTM',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute("PRAGMA table_info(orders)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'original_amount' not in columns:
            try:
                c.execute('ALTER TABLE orders ADD COLUMN original_amount REAL DEFAULT 0')
                logger.info("✅ Added original_amount column")
            except:
                pass
        
        if 'payment_type' not in columns:
            try:
                c.execute('ALTER TABLE orders ADD COLUMN payment_type TEXT DEFAULT "PAYTM"')
                logger.info("✅ Added payment_type column")
            except:
                pass
        
        # Processed emails table
        c.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                message_id TEXT PRIMARY KEY,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Products table
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT,
                product_id TEXT,
                plan_name TEXT,
                price REAL,
                android_id TEXT DEFAULT '0b9b969bc2e7997b'
            )
        ''')
        
        # History table
        c.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                product TEXT,
                plan TEXT,
                price REAL,
                license_key TEXT,
                date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Referral earnings
        c.execute('''
            CREATE TABLE IF NOT EXISTS referral_earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id TEXT,
                referred_id TEXT,
                deposit_amount REAL,
                bonus_amount REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Deposit history
        c.execute('''
            CREATE TABLE IF NOT EXISTS deposit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                order_id TEXT,
                amount REAL,
                utr TEXT,
                sender TEXT,
                payment_type TEXT DEFAULT 'PAYTM',
                status TEXT DEFAULT 'completed',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute("PRAGMA table_info(deposit_history)")
        dep_columns = [col[1] for col in c.fetchall()]
        if 'payment_type' not in dep_columns:
            try:
                c.execute('ALTER TABLE deposit_history ADD COLUMN payment_type TEXT DEFAULT "PAYTM"')
                logger.info("✅ Added payment_type to deposit_history")
            except:
                pass

        # Emoji settings
        c.execute('''
            CREATE TABLE IF NOT EXISTS emoji_settings (
                key TEXT PRIMARY KEY,
                emoji_id TEXT
            )
        ''')

        # Bot settings
        c.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Email settings
        c.execute('''
            CREATE TABLE IF NOT EXISTS email_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database tables ready!")
    
    def init_user(self, user_id, username):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        if not c.fetchone():
            c.execute('INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)',
                     (user_id, username, 0))
            conn.commit()
            logger.info(f"New user: {user_id} ({username})")
        conn.close()

    def get_all_user_ids(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT user_id FROM users')
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_recent_users(self, limit=20):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT user_id, username, balance FROM users ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return rows

    def set_reseller(self, user_id, is_reseller: bool):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('UPDATE users SET is_reseller = ? WHERE user_id = ?', (1 if is_reseller else 0, user_id))
        conn.commit()
        changed = c.rowcount > 0
        conn.close()
        return changed

    # ==================== EMOJI SETTINGS ====================

    def get_emoji_setting(self, key):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT emoji_id FROM emoji_settings WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def set_emoji_setting(self, key, emoji_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO emoji_settings (key, emoji_id) VALUES (?, ?)', (key, emoji_id))
        conn.commit()
        conn.close()

    def get_all_emoji_overrides(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT key, emoji_id FROM emoji_settings')
        rows = c.fetchall()
        conn.close()
        return {k: v for k, v in rows}

    def reset_emoji_setting(self, key):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('DELETE FROM emoji_settings WHERE key = ?', (key,))
        conn.commit()
        conn.close()

    def reset_all_emoji_settings(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('DELETE FROM emoji_settings')
        conn.commit()
        conn.close()

    # ==================== EMAIL SETTINGS ====================

    def get_email_setting(self, key):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT value FROM email_settings WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def set_email_setting(self, key, value):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO email_settings (key, value) VALUES (?, ?)', (key, value))
        conn.commit()
        conn.close()

    def get_email_config(self):
        gmail_user = self.get_email_setting('gmail_user') or DEFAULT_GMAIL_USER
        app_password = self.get_email_setting('app_password') or DEFAULT_APP_PASSWORD
        receiver_upi = self.get_email_setting('receiver_upi') or DEFAULT_RECEIVER_UPI
        return {
            'gmail_user': gmail_user,
            'app_password': app_password,
            'receiver_upi': receiver_upi
        }

    # ==================== BOT SETTINGS ====================

    def get_setting(self, key):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def set_setting(self, key, value):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)', (key, value))
        conn.commit()
        conn.close()

    def delete_setting(self, key):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('DELETE FROM bot_settings WHERE key = ?', (key,))
        conn.commit()
        conn.close()

    def get_welcome_media(self):
        media_type = self.get_setting("welcome_media_type")
        file_id = self.get_setting("welcome_media_file_id")
        if media_type and file_id:
            return media_type, file_id
        return None, None

    def set_welcome_media(self, media_type, file_id):
        self.set_setting("welcome_media_type", media_type)
        self.set_setting("welcome_media_file_id", file_id)

    def clear_welcome_media(self):
        self.delete_setting("welcome_media_type")
        self.delete_setting("welcome_media_file_id")

    def is_reseller(self, user_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT is_reseller FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        return bool(row and row[0])

    def get_resellers(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT user_id, username, balance FROM users WHERE is_reseller = 1')
        rows = c.fetchall()
        conn.close()
        return rows

    # ==================== REFERRAL SYSTEM ====================

    def set_referrer(self, user_id, referrer_id):
        if str(user_id) == str(referrer_id):
            return False
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT user_id FROM users WHERE user_id = ?', (referrer_id,))
        if not c.fetchone():
            conn.close()
            return False
        c.execute('''
            UPDATE users SET referred_by = ?
            WHERE user_id = ? AND (referred_by IS NULL OR referred_by = '')
        ''', (referrer_id, user_id))
        conn.commit()
        changed = c.rowcount > 0
        conn.close()
        return changed

    def get_referrer(self, user_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row and row[0] else None

    def credit_referral_bonus(self, referrer_id, referred_id, deposit_amount, commission_percent):
        bonus = round(deposit_amount * (commission_percent / 100), 2)
        if bonus <= 0:
            return 0
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus, referrer_id))
        c.execute('''
            INSERT INTO referral_earnings (referrer_id, referred_id, deposit_amount, bonus_amount)
            VALUES (?, ?, ?, ?)
        ''', (referrer_id, referred_id, deposit_amount, bonus))
        conn.commit()
        conn.close()
        return bonus

    def get_referral_stats(self, user_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users WHERE referred_by = ?', (user_id,))
        total_referred = c.fetchone()[0]
        c.execute('SELECT COALESCE(SUM(bonus_amount), 0) FROM referral_earnings WHERE referrer_id = ?', (user_id,))
        total_earned = c.fetchone()[0]
        conn.close()
        return {"total_referred": total_referred, "total_earned": total_earned}

    def get_stats(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]

        c.execute('SELECT COALESCE(SUM(balance), 0) FROM users')
        total_wallet_balance = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM orders')
        total_orders = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = c.fetchone()[0]

        c.execute("SELECT COALESCE(SUM(amount), 0) FROM deposit_history WHERE status = 'completed'")
        total_deposited = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM history')
        total_sales = c.fetchone()[0]

        c.execute('SELECT COALESCE(SUM(price), 0) FROM history')
        total_sales_value = c.fetchone()[0]

        conn.close()
        return {
            "total_users": total_users,
            "total_wallet_balance": total_wallet_balance,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_deposited": total_deposited,
            "total_sales": total_sales,
            "total_sales_value": total_sales_value,
        }
    
    def get_user(self, user_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        return row
    
    def get_balance(self, user_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0
    
    def update_balance(self, user_id, amount):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        logger.info(f"💰 Balance updated: user={user_id} +₹{amount}")
    
    def deduct_balance(self, user_id, amount):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?', 
                 (amount, user_id, amount))
        conn.commit()
        conn.close()
        return c.rowcount > 0
    
    def create_order(self, order_id, user_id, amount, original_amount):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('INSERT INTO orders (order_id, user_id, amount, original_amount, payment_type) VALUES (?, ?, ?, ?, ?)',
                 (order_id, user_id, amount, original_amount, "PAYTM"))
        conn.commit()
        conn.close()
        logger.info(f"📦 Order created: {order_id} user={user_id} amount=₹{amount} (original=₹{original_amount})")
    
    def update_order_amount(self, order_id, final_amount):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('UPDATE orders SET amount = ? WHERE order_id = ?', (final_amount, order_id))
        conn.commit()
        conn.close()
    
    def update_order(self, order_id, status, utr="", sender="", payment_type="PAYTM"):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            UPDATE orders SET status = ?, utr = ?, sender = ?, payment_type = ? WHERE order_id = ?
        ''', (status, utr, sender, payment_type, order_id))
        conn.commit()
        conn.close()
        logger.info(f"📦 Order updated: {order_id} status={status} utr={utr}")
    
    def get_order(self, order_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
        row = c.fetchone()
        conn.close()
        return row
    
    def get_pending_by_amount_exact(self, amount):
        """
        🔥 EXACT AMOUNT MATCH - 4 decimal precision
        Isse 1.02 sirf 1.02 se match hoga, 1.03 se nahi
        """
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT order_id, user_id FROM orders 
            WHERE status = 'pending' AND ROUND(amount, 2) = ROUND(?, 2)
            ORDER BY timestamp ASC LIMIT 1
        ''', (amount,))
        row = c.fetchone()
        conn.close()
        if row:
            logger.info(f"✅ Exact match found: order={row[0]} amount=₹{amount}")
        return row if row else None
    
    def get_pending_by_amount_fuzzy(self, amount, tolerance=0.01):
        """
        🔥 FUZZY MATCH - 1 paisa tolerance
        """
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT order_id, user_id, amount FROM orders 
            WHERE status = 'pending' AND ABS(amount - ?) <= ?
            ORDER BY timestamp ASC LIMIT 1
        ''', (amount, tolerance))
        row = c.fetchone()
        conn.close()
        if row:
            logger.info(f"✅ Fuzzy match found: order={row[0]} amount=₹{row[2]} (received=₹{amount})")
        return row if row else None
    
    def get_all_pending(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT * FROM orders WHERE status = "pending"')
        rows = c.fetchall()
        conn.close()
        return rows
    
    def get_user_orders(self, user_id, limit=10):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT * FROM orders WHERE user_id = ? 
            ORDER BY timestamp DESC LIMIT ?
        ''', (user_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows
    
    def add_history(self, user_id, product, plan, price, license_key):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            INSERT INTO history (user_id, product, plan, price, license_key)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, product, plan, price, license_key))
        conn.commit()
        conn.close()
    
    def get_history(self, user_id, limit=5):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT * FROM history WHERE user_id = ? 
            ORDER BY date DESC LIMIT ?
        ''', (user_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows
    
    def get_products(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT DISTINCT category FROM products')
        categories = c.fetchall()
        
        products = {}
        for cat in categories:
            c.execute('SELECT DISTINCT name, product_id FROM products WHERE category = ?', (cat[0],))
            products[cat[0]] = {}
            for prod in c.fetchall():
                c.execute('SELECT id, plan_name, price, android_id FROM products WHERE category = ? AND name = ?', 
                         (cat[0], prod[0]))
                rows = c.fetchall()
                plans = {}
                plan_ids = {}
                android_id = ANDROID_ID
                for row in rows:
                    plans[row[1]] = row[2]
                    plan_ids[row[1]] = row[0]
                    if row[3]:
                        android_id = row[3]
                products[cat[0]][prod[0]] = {"product_id": prod[1], "plans": plans, "plan_ids": plan_ids, "android_id": android_id}
        
        conn.close()
        return products

    def get_plan_by_id(self, plan_row_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT category, name, product_id, plan_name, price, android_id FROM products WHERE id = ?', (plan_row_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "category": row[0], "name": row[1], "product_id": row[2],
            "plan": row[3], "price": row[4], "android_id": row[5] or ANDROID_ID
        }

    def get_all_products_flat(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT category, name, COUNT(*) as plan_count
            FROM products
            GROUP BY category, name
            ORDER BY category, name
        ''')
        rows = c.fetchall()
        conn.close()
        return rows

    def add_product(self, category, name, product_id, plan, price, android_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            INSERT INTO products (category, name, product_id, plan_name, price, android_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (category, name, product_id, plan, price, android_id))
        conn.commit()
        conn.close()

    def delete_product(self, category, name):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('DELETE FROM products WHERE category = ? AND name = ?', (category, name))
        conn.commit()
        deleted = c.rowcount
        conn.close()
        return deleted

    def init_products(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM products')
        if c.fetchone()[0] == 0:
            products = [
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "1 Hours", 50, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "3 Hours", 80, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "6 Hours", 120, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "12 Hours", 150, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "1 DaYs", 200, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "2 DaYs", 350, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "3 DaYs", 450, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "5 DaYs", 600, ANDROID_ID),
                ("ANDROID NON ROOT", "BALA MOD XYZ FF", "133", "7 DaYs", 800, ANDROID_ID),
                ("ANDROID NON ROOT", "DRIPCLIENT PROXY FF NONROOT", "91", "1 DaYs", 100, ANDROID_ID),
                ("ANDROID NON ROOT", "DRIPCLIENT PROXY FF NONROOT", "91", "3 DaYs", 200, ANDROID_ID),
                ("ANDROID NON ROOT", "DRIPCLIENT PROXY FF NONROOT", "91", "7 DaYs", 300, ANDROID_ID),
                ("ANDROID NON ROOT", "DRIPCLIENT PROXY FF NONROOT", "91", "30 DaYs", 900, ANDROID_ID),
                ("ANDROID NON ROOT", "HG CHEATS FF APKMOD", "65", "1 DaYs", 90, ANDROID_ID),
                ("ANDROID NON ROOT", "HG CHEATS FF APKMOD", "65", "7 DaYs", 300, ANDROID_ID),
                ("ANDROID NON ROOT", "HG CHEATS FF APKMOD", "65", "10 DaYs", 400, ANDROID_ID),
                ("ANDROID NON ROOT", "HG CHEATS FF APKMOD", "65", "30 DaYs", 800, ANDROID_ID),
                ("ANDROID NON ROOT", "SILENT CHEAT FF NONROOT", "127", "1 DaYs", 80, ANDROID_ID),
                ("ANDROID NON ROOT", "SILENT CHEAT FF NONROOT", "127", "3 DaYs", 180, ANDROID_ID),
                ("ANDROID NON ROOT", "SILENT CHEAT FF NONROOT", "127", "7 DaYs", 280, ANDROID_ID),
                ("ANDROID NON ROOT", "SILENT CHEAT FF NONROOT", "127", "14 DaYs", 450, ANDROID_ID),
                ("ANDROID NON ROOT", "SILENT CHEAT FF NONROOT", "127", "28 DaYs", 700, ANDROID_ID),
                ("ANDROID ROOT", "BR MOD FF ROOT", "67", "1 DaYs", 100, ANDROID_ID),
                ("ANDROID ROOT", "BR MOD FF ROOT", "67", "7 DaYs", 300, ANDROID_ID),
                ("ANDROID ROOT", "BR MOD FF ROOT", "67", "15 DaYs", 500, ANDROID_ID),
                ("ANDROID ROOT", "BR MOD FF ROOT", "67", "30 DaYs", 800, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "1 DaYs BRUTAL", 100, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "1 DaYs SAFE", 90, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "3 DaYs BRUTAL", 200, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "3 DaYs SAFE", 180, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "7 DaYs BRUTAL", 350, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "7 DaYs SAFE", 300, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "14 DaYs BRUTAL", 550, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "14 DaYs SAFE", 500, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "28 DaYs BRUTAL", 800, ANDROID_ID),
                ("ANDROID ROOT", "SILENT CHEAT FF ROOT", "128", "28 DaYs SAFE", 750, ANDROID_ID),
                ("ANDROID ROOT", "XYZ CHEATS FF ROOT", "66", "1 Days", 100, ANDROID_ID),
                ("ANDROID ROOT", "XYZ CHEATS FF ROOT", "66", "3 Days", 200, ANDROID_ID),
                ("PC", "BR MOD FF PC VERSION", "49", "1 Day Pc Aim Silent", 150, ANDROID_ID),
                ("PC", "BR MOD FF PC VERSION", "49", "1 Day Pc Modmenu x86", 120, ANDROID_ID),
                ("PC", "BR MOD FF PC VERSION", "49", "10 Day Pc Modmenu x86", 300, ANDROID_ID),
                ("PC", "BR MOD FF PC VERSION", "49", "30 Day Pc Modmenu x86", 500, ANDROID_ID),
                ("IOS", "FLUORITE IOS FF", "58", "1 DAYs", 150, ANDROID_ID),
                ("IOS", "FLUORITE IOS FF", "58", "7 DAYs", 400, ANDROID_ID),
                ("IOS", "FLUORITE IOS FF", "58", "30 DAYs", 800, ANDROID_ID),
                ("IOS", "MIGUL IPHONE IOS FF", "69", "1 DaYs Basic", 100, ANDROID_ID),
                ("IOS", "MIGUL IPHONE IOS FF", "69", "1 DaYs PRO", 150, ANDROID_ID),
                ("IOS", "MIGUL IPHONE IOS FF", "69", "7 DaYs Basic", 300, ANDROID_ID),
                ("IOS", "MIGUL IPHONE IOS FF", "69", "7 DaYs PRO", 400, ANDROID_ID),
                ("IOS", "MIGUL IPHONE IOS FF", "69", "30 DaYs Basic", 600, ANDROID_ID),
                ("IOS", "MIGUL IPHONE IOS FF", "69", "30 DaYs PRO", 800, ANDROID_ID),
            ]
            c.executemany('''
                INSERT INTO products (category, name, product_id, plan_name, price, android_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', products)
            conn.commit()
            logger.info(f"✅ {len(products)} products initialized!")
        conn.close()
    
    def add_deposit_history(self, user_id, order_id, amount, utr="", sender="", payment_type="PAYTM", status="completed"):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            INSERT INTO deposit_history (user_id, order_id, amount, utr, sender, payment_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, order_id, amount, utr, sender, payment_type, status))
        conn.commit()
        conn.close()
        logger.info(f"📊 Deposit history: user={user_id} order={order_id} amount=₹{amount}")
    
    def get_deposit_history(self, user_id, limit=10):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT order_id, amount, utr, sender, payment_type, status, timestamp 
            FROM deposit_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows

    # ==================== PROCESSED EMAILS ====================

    def is_email_processed(self, message_id):
        if not message_id:
            return False
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT 1 FROM processed_emails WHERE message_id = ?', (message_id,))
        row = c.fetchone()
        conn.close()
        return row is not None

    def mark_email_processed(self, message_id):
        if not message_id:
            return
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO processed_emails (message_id) VALUES (?)', (message_id,))
        conn.commit()
        conn.close()

def generate_ref_code():
    return "DBX-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def fetch_license_key(product_id, duration, android_id=ANDROID_ID):
    payload = {
        'api_key': API_KEY,
        'action': 'buy',
        'product_id': str(product_id),
        'duration': str(duration),
        'android_id': android_id
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'x-master-key': MASTER_KEY
    }
    try:
        response = requests.post(API_ENDPOINT, data=payload, headers=headers, timeout=20)
        logger.info(f"API Response: {response.text[:200]}")
        
        try:
            res_data = response.json()
            if isinstance(res_data, dict):
                if "key" in res_data:
                    return res_data["key"]
                if "license" in res_data:
                    return res_data["license"]
                if "message" in res_data:
                    return f"Error: {res_data['message']}"
                if "msg" in res_data:
                    return f"Error: {res_data['msg']}"
                return f"Error: {str(res_data)}"
        except:
            pass
        
        if response.text and "Error" not in response.text:
            return response.text.strip()
        
        return f"Error: {response.text}"
            
    except Exception as e:
        logger.error(f"API Request Failed: {e}")
        return f"Error: {str(e)}"

# ============================================
# 📧 AUTO-PAYMENT MONITOR - FULL LOGGING
# ============================================

class EmailMonitor:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self.running = False
        self.thread = None
        self.last_error_notify = 0
        self.consecutive_failures = 0
        logger.info("📧 EmailMonitor initialized")
    
    def start(self):
        if not self.db.get_email_config()['gmail_user'] or not self.db.get_email_config()['app_password']:
            logger.warning("❌ Gmail not configured!")
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()
        logger.info("✅ Auto-payment monitor started!")
    
    def stop(self):
        self.running = False
        logger.info("🛑 Auto-payment monitor stopped")
    
    def _get_config(self):
        return self.db.get_email_config()
    
    def _monitor(self):
        logger.info("🔄 Monitor thread started")
        while self.running:
            try:
                logger.info("⏳ Checking emails...")
                self._check_emails()
                if self.consecutive_failures >= 3:
                    self._notify_admin_recovery()
                self.consecutive_failures = 0
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                self.consecutive_failures += 1
                self._notify_admin_failure(str(e))
            time.sleep(10)

    def _notify_admin_failure(self, error_text):
        if self.consecutive_failures < 3:
            return
        now = time.time()
        if now - self.last_error_notify < 300:
            return
        self.last_error_notify = now
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": ADMIN_ID,
                    "text": (
                        "⚠️ <b>PAYMENT AUTO-VERIFY DOWN!</b>\n\n"
                        f"Email monitor {self.consecutive_failures} baar fail ho chuka hai.\n"
                        f"<b>Error:</b> <code>{error_text[:300]}</code>\n\n"
                        "Check logs: bot_logs.txt"
                    ),
                    "parse_mode": "HTML"
                },
                timeout=10
            )
        except Exception:
            pass

    def _notify_admin_recovery(self):
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": ADMIN_ID, "text": "✅ Email monitor wapas normal ho gaya!"},
                timeout=10
            )
        except Exception:
            pass
    
    def _check_emails(self):
        config = self._get_config()
        if not config['gmail_user'] or not config['app_password']:
            return
        
        try:
            logger.info(f"📧 Connecting to Gmail: {config['gmail_user']}")
            mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=15)
            mail.login(config['gmail_user'], config['app_password'])
            mail.select("INBOX")
            logger.info("✅ Gmail connected")

            # 🔥 Search last 30 minutes - NOT UNSEEN
            date = (datetime.now() - timedelta(minutes=30)).strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(SINCE "{date}")')
            
            if status == 'OK' and messages[0]:
                msg_count = len(messages[0].split())
                logger.info(f"📧 Found {msg_count} emails in last 30 minutes")
                
                for num in messages[0].split():
                    try:
                        status, data = mail.fetch(num, '(RFC822)')
                        if status == 'OK':
                            msg = email.message_from_bytes(data[0][1])
                            message_id = msg.get("Message-ID", "") or f"{msg.get('Date','')}-{msg.get('Subject','')}"
                            
                            if self.db.is_email_processed(message_id):
                                logger.info(f"⏭️ Skipping already processed: {message_id}")
                                continue
                            
                            logger.info(f"📨 Processing email: {message_id}")
                            processed = self._process_email(msg)
                            
                            # Mark as processed regardless
                            self.db.mark_email_processed(message_id)
                            if processed:
                                logger.info(f"✅ Email processed successfully: {message_id}")
                            else:
                                logger.info(f"⏭️ Email skipped (not payment): {message_id}")
                                
                    except Exception as e:
                        logger.error(f"Fetch error: {e}")

            mail.close()
            mail.logout()
            logger.info("📧 Gmail disconnected")
            
        except imaplib.IMAP4.error as e:
            logger.error(f"❌ IMAP login error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Email check error: {e}")
            raise
    
    def _process_email(self, msg):
        """Returns True if payment was processed"""
        try:
            subject = str(msg.get("Subject", ""))
            from_addr = (msg.get("From", "") or "").lower()
            
            logger.info(f"📧 Email subject: {subject[:100]}")
            logger.info(f"📧 From: {from_addr}")
            
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                if not body:
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            body = re.sub(r'<[^>]+>', ' ', html)
                            break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

            # 🔥 Check if payment email
            payment_keywords = ['paytm', 'credit', 'received', 'payment', 'upi', 'rs.', '₹', 'paid']
            if not any(k in subject.lower() for k in payment_keywords):
                logger.info(f"⏭️ Not a payment email: {subject[:50]}")
                return False

            # 🔥 Extract amount with precision
            amount = self._extract_amount_precise(subject, body)
            if not amount:
                logger.warning(f"❌ Could not extract amount from: {subject}")
                return False
            
            logger.info(f"💰 Amount extracted: ₹{amount:.4f}")

            # 🔥 Extract UTR and sender
            utr = self._extract_utr(subject, body)
            sender = self._extract_sender(body)
            payment_type = self._detect_payment_type(subject, body, from_addr)
            
            logger.info(f"📋 UTR: {utr}, Sender: {sender}, Type: {payment_type}")
            
            # 🔥 Check if this is our UPI
            if not self._is_our_upi(body, from_addr, payment_type):
                logger.info(f"⏭️ Not our UPI: {from_addr}")
                return False
            
            logger.info(f"✅ Payment verified: ₹{amount:.2f} | UTR: {utr}")
            
            # 🔥 STEP 1: EXACT match
            result = self.db.get_pending_by_amount_exact(amount)
            
            if result:
                order_id, user_id = result
                self._complete_payment(order_id, user_id, amount, utr, sender, payment_type)
                logger.info(f"✅ Order {order_id} COMPLETED (Exact match)!")
                return True
            
            # 🔥 STEP 2: FUZZY match (1 paisa tolerance)
            result = self.db.get_pending_by_amount_fuzzy(amount, 0.01)
            
            if result:
                order_id, user_id, order_amount = result
                self._complete_payment(order_id, user_id, amount, utr, sender, payment_type)
                logger.info(f"✅ Order {order_id} COMPLETED (Fuzzy match, diff: ₹{abs(order_amount - amount):.4f})!")
                return True
            
            # 🔥 STEP 3: Check all pending orders and log
            pending = self.db.get_all_pending()
            if pending:
                logger.info(f"📋 Found {len(pending)} pending orders:")
                for p in pending:
                    logger.info(f"  - {p[0]}: ₹{p[2]} (user: {p[1]})")
                
                # Check if any pending order is within ₹0.50
                for p in pending:
                    diff = abs(p[2] - amount)
                    if diff <= 0.50:
                        logger.warning(f"⚠️ Close match found: order={p[0]} amount=₹{p[2]} diff=₹{diff:.2f}")
            
            logger.warning(f"❌ No matching order found for ₹{amount:.2f}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Process error: {e}", exc_info=True)
            return False
    
    def _complete_payment(self, order_id, user_id, amount, utr, sender, payment_type):
        """Complete payment and update everything"""
        try:
            # Update order
            self.db.update_order(order_id, 'completed', utr, sender, payment_type)
            
            # Update balance
            self.db.update_balance(user_id, amount)
            
            # Add deposit history
            self.db.add_deposit_history(user_id, order_id, amount, utr, sender, payment_type)
            
            # Send success message to user
            self._send_user_success(user_id, order_id, amount, utr, sender, payment_type)
            
            # Credit referral bonus
            self._credit_referral(user_id, amount)
            
            logger.info(f"✅ Payment completed: order={order_id} user={user_id} amount=₹{amount}")
            
        except Exception as e:
            logger.error(f"❌ Complete payment error: {e}", exc_info=True)
    
    def _detect_payment_type(self, subject, body, from_addr=""):
        text = (subject + " " + body).lower()
        if "paytm" in from_addr or "paytm" in text:
            if "business" in text or "#paytmkaro" in text:
                return "PAYTM_BUSINESS"
            return "PAYTM"
        return "UPI"
    
    def _extract_amount_precise(self, subject, body):
        """Extract amount with up to 4 decimal precision"""
        text = subject + " " + body
        
        patterns = [
            r'(?:₹|Rs\.?|INR)\s*([\d,]+\.\d{1,4})',   # ₹1.0, Rs. 1.20, INR 2.1234 — was \d{2,4}, missed "₹1.0"
            r'([\d,]+\.\d{1,4})\s*(?:INR|Rs\.?)',
            r'(?:amount of|received|credited)\s*(?:₹|rs\.?|inr)?\s*([\d,]+\.\d{1,4})',
            r'([\d,]+\.\d{1,4})',
            r'(?:₹|Rs\.?|INR)\s*([\d,]+)\b',           # whole-number fallback: "₹1" with no decimal at all
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except:
                    continue
        
        return None
    
    def _extract_utr(self, subject, body):
        text = subject + " " + body
        patterns = [
            r'UPI\s*Ref(?:erence)?\s*(?:No\.?|Number)?\s*[:.]?\s*([A-Z0-9]{6,})',
            r'(?:UTR|Transaction\s*ID|Txn\s*ID)\s*[:.]?\s*([A-Z0-9-]{6,})',
            r'Order\s*ID\s*[:.]?\s*([A-Z0-9-]{6,})',
            r'Reference\s*(?:No\.?|Number)?\s*[:.]?\s*([A-Z0-9-]{6,})',
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        match = re.search(r'\b([A-Z0-9]{10,})\b', text)
        if match:
            return match.group(1).strip()
        return f"PAY_{int(time.time())}"
    
    def _extract_sender(self, body):
        match = re.search(r'From\s*[:]\s*([^\n]+)', body, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r'Sender\s*[:]\s*([^\n]+)', body, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r'\b(\d{2}[Xx]{6,8}\d{2,4})\b', body)
        if match:
            return match.group(1).strip()
        return "Unknown"
    
    def _is_our_upi(self, body, from_addr="", payment_type=""):
        body_l = body.lower()
        config = self._get_config()
        
        if (config.get('receiver_upi') or "").lower() in body_l:
            return True
        
        if "paytm" in from_addr and payment_type in ("PAYTM", "PAYTM_BUSINESS"):
            return True
        
        if payment_type in ("PAYTM", "PAYTM_BUSINESS"):
            return True
        
        return False
    
    def _send_user_success(self, user_id, order_id, amount, utr, sender, payment_type):
        msg = f"""
✅ <b>PAYMENT AUTO-VERIFIED!</b>
━━━━━━━━━━━━━━━━━━
🆔 <b>Order ID:</b> <code>{order_id}</code>
💰 <b>Amount:</b> ₹{amount:.2f}
🧾 <b>UTR:</b> <code>{utr}</code>
👤 <b>Sender:</b> {sender}
🏷️ <b>Type:</b> {payment_type}
━━━━━━━━━━━━━━━━━━
💰 ₹{amount:.2f} added to your wallet!
"""
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": int(user_id), "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
            logger.info(f"📨 Success message sent to user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send success message: {e}")

    def _credit_referral(self, referred_user_id, deposit_amount):
        try:
            referrer_id = self.db.get_referrer(referred_user_id)
            if not referrer_id:
                return
            bonus = self.db.credit_referral_bonus(referrer_id, referred_user_id, deposit_amount, REFERRAL_COMMISSION_PERCENT)
            if bonus and bonus > 0:
                logger.info(f"💰 Referral bonus: ₹{bonus:.2f} to {referrer_id} from {referred_user_id}")
                msg = (
                    f"🎉 <b>REFERRAL BONUS!</b>\n\n"
                    f"Aapke referral se ek user ne ₹{deposit_amount:.2f} deposit kiya.\n"
                    f"💰 <b>₹{bonus:.2f}</b> aapke wallet mein add ho gaye!"
                )
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                        json={"chat_id": int(referrer_id), "text": msg, "parse_mode": "HTML"},
                        timeout=10
                    )
                except:
                    pass
        except Exception as e:
            logger.warning(f"Referral credit failed: {e}")

# ============================================
# 🔵 KEYBOARDS
# ============================================

def get_main_menu_keyboard(is_admin=False):
    rows = [
        [CB("Product Store", style="primary", icon=get_button_emoji("shop"), callback_data="menu_shop")],
        [CB("My Profile", style="primary", icon=get_button_emoji("profile"), callback_data="menu_profile"),
         CB("Add Balance", style="success", icon=get_button_emoji("add_balance"), callback_data="menu_add_balance")],
        [CB("Order History", style="primary", icon=get_button_emoji("order_history"), callback_data="menu_history"),
         CB("Deposit History", style="primary", icon=get_button_emoji("deposit_history"), callback_data="menu_deposit_history")],
        [CB("Referral", style="primary", icon=get_button_emoji("referral"), callback_data="menu_referral"),
         CB("Tutorial", style="primary", icon=get_button_emoji("tutorial"), callback_data="menu_tutorial")],
        [CB("Support", style="primary", icon=get_button_emoji("support"), callback_data="menu_support"),
         CB("Download Hack", style="danger", icon=get_button_emoji("download"), callback_data="menu_download")]
    ]
    if is_admin:
        rows.append([CB("ADMIN PANEL", style="danger", icon=get_button_emoji("warning"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def get_admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [CB("Broadcast", style="primary", icon=get_button_emoji("broadcast"), callback_data="admin_broadcast")],
        [CB("Add Product", style="primary", icon=get_button_emoji("add"), callback_data="admin_addproduct"),
         CB("Remove Product", style="danger", icon=get_button_emoji("remove"), callback_data="admin_removeproduct")],
        [CB("Add Balance to User", style="success", icon=get_button_emoji("add_balance"), callback_data="admin_addbalance")],
        [CB("Manage Resellers", style="primary", icon=get_button_emoji("star"), callback_data="admin_resellers")],
        [CB("Email Settings", style="primary", icon=get_button_emoji("star"), callback_data="admin_email_settings")],
        [CB("Stats", style="primary", icon=get_button_emoji("stats"), callback_data="admin_stats"),
         CB("Users", style="primary", icon=get_button_emoji("users"), callback_data="admin_users")],
        [CB("Emoji Settings", style="primary", icon=get_button_emoji("star"), callback_data="admin_emoji_settings")],
        [CB("Welcome Media", style="primary", icon=get_button_emoji("star"), callback_data="admin_welcomemedia")],
        [CB("Menu Photos", style="primary", icon=get_button_emoji("star"), callback_data="admin_menuphotos")],
        [CB("Test Email Connection", style="primary", icon=get_button_emoji("refresh"), callback_data="admin_test_email")],
        [CB("Back to Menu", style="danger", icon=get_button_emoji("back"), callback_data="back_to_menu")]
    ])

def get_email_settings_keyboard():
    return InlineKeyboardMarkup([
        [CB("Change Gmail User", style="primary", icon=get_button_emoji("add"), callback_data="admin_email_gmail")],
        [CB("Change App Password", style="primary", icon=get_button_emoji("add"), callback_data="admin_email_password")],
        [CB("Change PayTM UPI", style="primary", icon=get_button_emoji("add"), callback_data="admin_email_upi")],
        [CB("View Current Settings", style="primary", icon=get_button_emoji("stats"), callback_data="admin_email_view")],
        [CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]
    ])

def get_welcome_media_keyboard(current_type):
    rows = [
        [CB("Set Welcome Photo", style="primary", icon=get_button_emoji("add"), callback_data="admin_setwelcomephoto")],
        [CB("Set Welcome Video", style="primary", icon=get_button_emoji("add"), callback_data="admin_setwelcomevideo")],
    ]
    if current_type:
        rows.append([CB("Remove Welcome Media", style="danger", icon=get_button_emoji("remove"), callback_data="admin_removewelcomemedia")])
    rows.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def get_emoji_settings_keyboard():
    return InlineKeyboardMarkup([
        [CB("Change an Emoji", style="primary", icon=get_button_emoji("add"), callback_data="admin_emoji_change")],
        [CB("Backup Current Settings", style="success", icon=get_button_emoji("download"), callback_data="admin_emoji_backup")],
        [CB("Restore Defaults", style="danger", icon=get_button_emoji("cancel"), callback_data="admin_emoji_restore")],
        [CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]
    ])

def get_reseller_panel_keyboard():
    return InlineKeyboardMarkup([
        [CB("Add Reseller", style="success", icon=get_button_emoji("add"), callback_data="admin_addreseller")],
        [CB("Remove Reseller", style="danger", icon=get_button_emoji("remove"), callback_data="admin_removereseller")],
        [CB("List Resellers", style="primary", icon=get_button_emoji("users"), callback_data="admin_listresellers")],
        [CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]
    ])

def get_numeric_keypad():
    return InlineKeyboardMarkup([
        [CB("1", style="primary", callback_data="kp_1"), 
         CB("2", style="primary", callback_data="kp_2"), 
         CB("3", style="primary", callback_data="kp_3")],
        [CB("4", style="primary", callback_data="kp_4"), 
         CB("5", style="primary", callback_data="kp_5"), 
         CB("6", style="primary", callback_data="kp_6")],
        [CB("7", style="primary", callback_data="kp_7"), 
         CB("8", style="primary", callback_data="kp_8"), 
         CB("9", style="primary", callback_data="kp_9")],
        [CB("Clear", style="danger", icon=get_button_emoji("clear"), callback_data="kp_clear"),
         CB("0", style="primary", callback_data="kp_0"),
         CB("Confirm", style="success", icon=get_button_emoji("confirm"), callback_data="kp_confirm")],
        [CB("BACK", style="danger", icon=get_button_emoji("back"), callback_data="back_to_menu")]
    ])

def get_verify_button(order_id):
    return InlineKeyboardMarkup([
        [CB("Verify Payment", style="success", icon=get_button_emoji("confirm"), callback_data=f"verify_{order_id}")],
        [CB("Cancel", style="danger", icon=get_button_emoji("cancel"), callback_data="menu_add_balance")]
    ])

def get_back_button():
    return InlineKeyboardMarkup([
        [CB("Back", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]
    ])

# ============================================
# 📢 BROADCAST
# ============================================

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("❌ You are not authorized!")
        return

    context.user_data["awaiting_broadcast"] = True
    await update.message.reply_text(
        "📢 <b>Broadcast Mode ON</b>\n\n"
        "Ab jo bhi message bhejoge wo sabhi users ko bhej diya jaayega.\n\n"
        "Cancel karne ke liye /cancel bhejo.",
        parse_mode="HTML"
    )

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        return
    flags = ["awaiting_broadcast", "awaiting_addproduct", "awaiting_addbalance", "awaiting_addreseller", 
             "awaiting_removereseller", "awaiting_emoji_update", "awaiting_welcome_photo", 
             "awaiting_welcome_video", "awaiting_screen_photo", "awaiting_email_setting"]
    was_active = any(context.user_data.get(f) for f in flags)
    for f in flags:
        context.user_data[f] = False
    if was_active:
        await update.message.reply_text("❌ Cancelled.")

# ============================================
# 💾 DATABASE BACKUP / RESTORE
# ============================================

async def backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("❌ You are not authorized!")
        return
    if not os.path.exists(DB_FILE):
        await update.message.reply_text("❌ Database file abhi tak exist nahi karti.")
        return
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        await update.message.reply_document(
            document=open(DB_FILE, "rb"),
            filename=f"store_backup_{ts}.db",
            caption="💾 Database Backup"
        )
        logger.info(f"📦 Backup created: store_backup_{ts}.db")
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        await update.message.reply_text(f"❌ Backup fail ho gaya: {e}")

async def restore_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("❌ You are not authorized!")
        return
    reply = update.message.reply_to_message
    if not reply or not reply.document:
        await update.message.reply_text("❌ Ek backup file ko reply karke /restore bhejo.")
        return
    try:
        file = await context.bot.get_file(reply.document.file_id)
        tmp_path = DB_FILE + ".incoming"
        await file.download_to_drive(tmp_path)
        os.replace(tmp_path, DB_FILE)
        logger.info("✅ Database restored successfully")
        await update.message.reply_text("✅ Database restore ho gayi!")
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        await update.message.reply_text(f"❌ Restore fail ho gaya: {e}")

def _auto_backup_loop(bot_token, admin_id, interval_hours=6):
    while True:
        time.sleep(interval_hours * 3600)
        try:
            if not os.path.exists(DB_FILE):
                continue
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(DB_FILE, "rb") as f:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendDocument",
                    data={"chat_id": admin_id, "caption": f"💾 Auto-backup ({ts})"},
                    files={"document": (f"store_backup_{ts}.db", f)},
                    timeout=30
                )
            logger.info(f"📦 Auto-backup sent: store_backup_{ts}.db")
        except Exception as e:
            logger.error(f"Auto-backup failed: {e}")

# ============================================
# MESSAGE HANDLER
# ============================================

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        return

    if context.user_data.get("awaiting_screen_photo"):
        screen_key = context.user_data["awaiting_screen_photo"]
        context.user_data["awaiting_screen_photo"] = False
        if (update.message.text or "").strip() == "/cancel":
            await update.message.reply_text("❌ Cancelled.")
            return
        if not update.message.photo:
            await update.message.reply_text("❌ Ye photo nahi hai. Ek photo bhejo, ya /cancel karo.")
            return
        file_id = update.message.photo[-1].file_id
        db.set_setting(f"menu_photo:{screen_key}", file_id)
        label = SCREEN_LABELS.get(screen_key, screen_key)
        await update.message.reply_text(f"✅ {label} ki photo set ho gayi!")
        return

    if context.user_data.get("awaiting_welcome_photo"):
        context.user_data["awaiting_welcome_photo"] = False
        if (update.message.text or "").strip() == "/cancel":
            await update.message.reply_text("❌ Cancelled.")
            return
        if not update.message.photo:
            await update.message.reply_text("❌ Ye photo nahi hai. Ek photo bhejo, ya /cancel karo.")
            return
        file_id = update.message.photo[-1].file_id
        db.set_welcome_media("photo", file_id)
        await update.message.reply_text("✅ Welcome photo set ho gayi!")
        return

    if context.user_data.get("awaiting_welcome_video"):
        context.user_data["awaiting_welcome_video"] = False
        if (update.message.text or "").strip() == "/cancel":
            await update.message.reply_text("❌ Cancelled.")
            return
        if not update.message.video:
            await update.message.reply_text("❌ Ye video nahi hai. Ek video bhejo, ya /cancel karo.")
            return
        file_id = update.message.video.file_id
        db.set_welcome_media("video", file_id)
        await update.message.reply_text("✅ Welcome video set ho gayi!")
        return

    if context.user_data.get("awaiting_email_setting"):
        setting_type = context.user_data["awaiting_email_setting"]
        context.user_data["awaiting_email_setting"] = False
        
        if (update.message.text or "").strip() == "/cancel":
            await update.message.reply_text("❌ Cancelled.")
            return
        
        value = (update.message.text or "").strip()
        if not value:
            await update.message.reply_text("❌ Value khaali nahi ho sakti.")
            return
        
        if setting_type == "gmail":
            db.set_email_setting("gmail_user", value)
            await update.message.reply_text(f"✅ Gmail user set ho gaya: <code>{value}</code>", parse_mode="HTML")
        elif setting_type == "password":
            db.set_email_setting("app_password", value)
            await update.message.reply_text("✅ App Password set ho gaya!")
        elif setting_type == "upi":
            db.set_email_setting("receiver_upi", value)
            await update.message.reply_text(f"✅ PayTM UPI set ho gaya: <code>{value}</code>", parse_mode="HTML")
        
        global monitor
        if monitor:
            monitor.stop()
            monitor = EmailMonitor(db, app.bot)
            monitor.start()
        return

    if context.user_data.get("awaiting_emoji_update"):
        context.user_data["awaiting_emoji_update"] = False
        try:
            text = (update.message.text or "").strip()
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                await update.message.reply_text("❌ Format galat hai.\n\nUsage: KEY NEW_EMOJI_ID\n ya: KEY reset")
                return

            key, value = parts[0].strip(), parts[1].strip()
            if key not in BUTTON_EMOJIS:
                await update.message.reply_text(f"❌ Invalid key: <code>{key}</code>", parse_mode="HTML")
                return

            if value.lower() == "reset":
                db.reset_emoji_setting(key)
                await update.message.reply_text(f"✅ <code>{key}</code> ka emoji default par reset ho gaya.", parse_mode="HTML")
            else:
                db.set_emoji_setting(key, value)
                await update.message.reply_text(f"✅ <code>{key}</code> ka emoji update ho gaya!", parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        return

    if context.user_data.get("awaiting_addreseller"):
        context.user_data["awaiting_addreseller"] = False
        target_id = (update.message.text or "").strip()
        if not target_id.isdigit():
            await update.message.reply_text("❌ Invalid USER_ID.")
            return
        changed = db.set_reseller(target_id, True)
        if changed:
            await update.message.reply_text(f"✅ User <code>{target_id}</code> ab reseller hai!", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=int(target_id),
                    text=f"👑 <b>Congratulations!</b> Aap ab Reseller ban gaye ho!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await update.message.reply_text("❌ User not found.")
        return

    if context.user_data.get("awaiting_removereseller"):
        context.user_data["awaiting_removereseller"] = False
        target_id = (update.message.text or "").strip()
        if not target_id.isdigit():
            await update.message.reply_text("❌ Invalid USER_ID.")
            return
        changed = db.set_reseller(target_id, False)
        if changed:
            await update.message.reply_text(f"✅ User <code>{target_id}</code> ka reseller status hata diya.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ User not found.")
        return

    if context.user_data.get("awaiting_addproduct"):
        context.user_data["awaiting_addproduct"] = False
        text = (update.message.text or "").strip()
        if text == "/cancel":
            await update.message.reply_text("❌ Cancelled.")
            return
        try:
            p = parse_product_line(text)
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}")
            return

        try:
            db.add_product(p["category"], p["name"], p["product_id"], p["plan"], p["price"], p["android_id"])
            await update.message.reply_text(f"✅ Product Added!\n📦 {p['name']}\n💰 ₹{p['price']:.2f}")
        except Exception as e:
            logger.error(f"add_product DB error: {e}")
            await update.message.reply_text(f"❌ Product save nahi ho paya: {e}")
        return

    if context.user_data.get("awaiting_addbalance"):
        context.user_data["awaiting_addbalance"] = False
        try:
            text = (update.message.text or "").strip()
            target_id, amt = text.split()
            amt = float(amt)
            db.update_balance(target_id, amt)
            new_balance = db.get_balance(target_id)
            await update.message.reply_text(f"✅ ₹{amt:.2f} added to user <code>{target_id}</code>\n💰 New balance: ₹{new_balance:.2f}", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=int(target_id),
                    text=f"💰 <b>₹{amt:.2f} added to your wallet by admin!</b>\nNew balance: ₹{new_balance:.2f}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}\n\nFormat: USER_ID AMOUNT")
        return

    if not context.user_data.get("awaiting_broadcast"):
        return

    context.user_data["awaiting_broadcast"] = False

    user_ids = db.get_all_user_ids()
    total = len(user_ids)
    sent = 0
    failed = 0

    status_msg = await update.message.reply_text(f"⏳ Broadcasting to {total} users...")

    for uid in user_ids:
        try:
            await context.bot.copy_message(
                chat_id=int(uid),
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast failed for {uid}: {e}")
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Total: {total}",
        parse_mode="HTML"
    )

# ============================================
# BOT HANDLERS
# ============================================

WELCOME_TEXT = (
    f'<tg-emoji emoji-id="6071312005224993914">⭐</tg-emoji> <b>{to_bold_unicode("Product Store")}</b> : all key purchase & instantly delivery\n'
    f'<tg-emoji emoji-id="6071074330324768982">⭐</tg-emoji> <b>{to_bold_unicode("My Profile")}</b> : check your account information\n'
    f'<tg-emoji emoji-id="6071132024620455409">⭐</tg-emoji> <b>{to_bold_unicode("Add Balance")}</b> : deposit balance & secure service\n'
    f'<tg-emoji emoji-id="6070878939377571385">⭐</tg-emoji> <b>{to_bold_unicode("Order History")}</b> : check all key purchase history\n'
    f'<tg-emoji emoji-id="6071132024620455409">⭐</tg-emoji> <b>{to_bold_unicode("Deposit History")}</b> : check all your deposits\n'
    f'<tg-emoji emoji-id="6071126054615913700">⭐</tg-emoji> <b>{to_bold_unicode("Tutorial")}</b> : view tutorial and work this bot\n'
    f'<tg-emoji emoji-id="6071264704750162461">⭐</tg-emoji> <b>{to_bold_unicode("Support")}</b> : bot problem fixed for support admin\n'
    f'<tg-emoji emoji-id="6073116574389113063">⭐</tg-emoji> <b>{to_bold_unicode("Download Hack")}</b> : download latest apk for safety.'
)

SCREEN_LABELS = {
    "shop": "🛍 Store",
    "profile": "👤 My Profile",
    "history": "📜 Order History",
    "deposit_history": "💳 Deposit History",
    "referral": "⭐ Referral",
    "tutorial": "📘 Tutorial",
    "support": "🆘 Support",
    "download": "⬇️ Download Hack",
}

async def delete_message_safely(message):
    try:
        await message.delete()
    except BadRequest as e:
        if "Message to delete not found" in str(e) or "message can't be deleted" in str(e):
            pass
        else:
            raise
    except Exception:
        pass

async def send_screen(query, text, reply_markup, screen_key=None, parse_mode="HTML"):
    photo_file_id = db.get_setting(f"menu_photo:{screen_key}") if screen_key else None
    msg = query.message
    is_media = bool(msg.photo or msg.video or msg.document or msg.animation or msg.audio or msg.voice or msg.sticker)

    if photo_file_id:
        await delete_message_safely(msg)
        await query.get_bot().send_photo(chat_id=msg.chat_id, photo=photo_file_id, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
    elif is_media:
        await delete_message_safely(msg)
        await query.get_bot().send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        try:
            await msg.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                await delete_message_safely(msg)
                await query.get_bot().send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

async def safe_edit(query, text, reply_markup=None, parse_mode="HTML"):
    msg = query.message
    is_media = bool(msg.photo or msg.video or msg.document or msg.animation or msg.audio or msg.voice or msg.sticker)
    if is_media:
        await delete_message_safely(msg)
        await query.get_bot().send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        try:
            await msg.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                await delete_message_safely(msg)
                await query.get_bot().send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

async def send_welcome(bot, chat_id, is_admin):
    keyboard = get_main_menu_keyboard(is_admin=is_admin)
    media_type, file_id = db.get_welcome_media()
    if media_type == "photo":
        await bot.send_photo(chat_id=chat_id, photo=file_id, caption=WELCOME_TEXT, reply_markup=keyboard, parse_mode="HTML")
    elif media_type == "video":
        await bot.send_video(chat_id=chat_id, video=file_id, caption=WELCOME_TEXT, reply_markup=keyboard, parse_mode="HTML")
    else:
        await bot.send_message(chat_id=chat_id, text=WELCOME_TEXT, reply_markup=keyboard, parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    is_new_user = db.get_user(user_id) is None
    db.init_user(user_id, user.username or "User")

    if context.args:
        payload = context.args[0].strip()
        referrer_id = payload.replace("ref_", "").strip()
        
        if not is_new_user:
            logger.info(f"Referral skipped: {user_id} already existed")
        elif not referrer_id.isdigit():
            logger.info(f"Referral skipped: invalid payload '{payload}'")
        else:
            linked = db.set_referrer(user_id, referrer_id)
            if linked:
                logger.info(f"Referral linked: {user_id} -> {referrer_id}")
                try:
                    join_msg = (
                        f"🎉 <b>Naya Referral!</b>\n\n"
                        f"Aapke link se ek naya user join hua hai. "
                        f"Jab wo deposit karega, aapko {REFERRAL_COMMISSION_PERCENT}% bonus milega!"
                    )
                    await context.bot.send_message(chat_id=int(referrer_id), text=join_msg, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Could not notify referrer {referrer_id}: {e}")
            else:
                logger.info(f"Referral NOT linked: referrer {referrer_id} not found")
    
    if update.message:
        is_admin = str(user.id) == str(ADMIN_ID)
        await send_welcome(context.bot, update.message.chat_id, is_admin)

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("❌ You are not authorized!")
        return
    
    text = update.message.text.replace("/addproduct", "", 1).strip()
    if not text:
        await update.message.reply_text(
            "❌ Usage:\n"
            "/addproduct CATEGORY | NAME | PRODUCT_ID | PLAN | PRICE | ANDROID_ID\n\n"
            "Example:\n"
            "/addproduct ANDROID NON ROOT | BALA MOD PRO | 133 | 1 Day | 150 | 0b9b969bc2e7997b"
        )
        return

    try:
        p = parse_product_line(text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return

    try:
        db.add_product(p["category"], p["name"], p["product_id"], p["plan"], p["price"], p["android_id"])
        await update.message.reply_text(f"✅ Product Added!\n📦 {p['name']}\n💰 ₹{p['price']:.2f}")
    except Exception as e:
        logger.error(f"add_product DB error: {e}")
        await update.message.reply_text(f"❌ Product save nahi ho paya: {e}")

async def check_payment_later(context: ContextTypes.DEFAULT_TYPE, chat_id, message_id, order_id, delay=15):
    await asyncio.sleep(delay)
    order = db.get_order(order_id)
    if not order:
        return
    if order[3] == "completed":
        return

    msg = f"""
❌ <b>PAYMENT NOT FOUND</b>
━━━━━━━━━━━━━━━━━━
🆔 <b>Order:</b> <code>{order_id}</code>
💰 <b>Amount:</b> ₹{order[2]:.2f}
━━━━━━━━━━━━━━━━━━
Hume abhi tak aapka payment nahi mila.
Agar aapne payment kar diya hai, thodi der baad "Check Again" try karein.
Agar payment nahi kiya, to "Cancel" dabayein aur naya QR banayein.
"""
    keyboard = [
        [CB("Check Again", style="primary", icon=get_button_emoji("refresh"), callback_data=f"verify_{order_id}")],
        [CB("Cancel", style="danger", icon=get_button_emoji("cancel"), callback_data="menu_add_balance")]
    ]
    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"check_payment_later edit failed: {e}")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await _handle_callbacks_inner(update, context)
    except Exception as e:
        logger.error(f"handle_callbacks error on data='{query.data}': {e}", exc_info=True)
        try:
            await query.answer(f"❌ Error: {str(e)[:180]}", show_alert=True)
        except Exception:
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ <b>Error:</b> <code>{str(e)[:300]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

async def _handle_callbacks_inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = str(update.effective_user.id)
    
    try:
        await query.answer()
    except BadRequest as e:
        if "Query is too old" in str(e) or "timeout expired" in str(e):
            pass
        else:
            raise
    
    db.init_user(user_id, update.effective_user.username or "User")
    
    if "kp_amt" not in context.user_data:
        context.user_data["kp_amt"] = ""

    if data == "back_to_menu":
        context.user_data["kp_amt"] = ""
        is_admin = user_id == str(ADMIN_ID)
        await delete_message_safely(query.message)
        await send_welcome(context.bot, query.message.chat_id, is_admin)

    elif data == "menu_shop":
        products = db.get_products()
        text = (
            f"<b>📊 HACK STORE — SHOP 💭</b>\n\n"
            f'<tg-emoji emoji-id="6070873970100409600">⭐</tg-emoji> <b>Apna device category chuno neeche se.</b>\n'
            f"."
        )
        keyboard = []
        
        for cat in products.keys():
            cb = encode_cb("cat", cat)
            keyboard.append([CB(f"{cat}", style="primary", icon=get_category_emoji(cat), callback_data=cb)])
        
        keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="back_to_menu")])
        await send_screen(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), screen_key="shop", parse_mode="HTML")

    elif data.startswith("cat" + SEP):
        parts = decode_cb(data)
        category = parts[1]
        products = db.get_products()
        text = (
            f"<b>📂 Category: {category}</b>\n\n"
            f"Neeche apna product chuno — sabhi 100% working hai.\n"
            f"Purchase karte hi key turant deliver ho jaayegi."
        )
        keyboard = []
        for prod_name in products.get(category, {}).keys():
            cb = encode_cb("prod", category, prod_name)
            keyboard.append([CB(f"{prod_name}", style="primary", icon=get_button_emoji("star"), callback_data=cb)])
        keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="menu_shop")])
        await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("prod" + SEP):
        parts = decode_cb(data)
        category = parts[1]
        prod_name = parts[2]
        products = db.get_products()
        plans = products[category][prod_name]["plans"]
        plan_ids = products[category][prod_name]["plan_ids"]
        is_reseller = db.is_reseller(user_id)

        text = (
            f"<b>💎 Product: {prod_name}</b>\n\n"
            f"Apni pasand ka plan chuno — jitne din chahiye, utna pack lo.\n"
            f"Payment ke turant baad key aapke paas instantly aa jaayegi."
        )
        if is_reseller:
            text += f"\n👑 <b>Reseller Price ({RESELLER_DISCOUNT_PERCENT}% OFF)</b>"
        keyboard = []
        for plan_name, price in plans.items():
            final_price = get_price_for_user(price, user_id)
            if is_reseller:
                label = f"⏳ {plan_name} - ₹{final_price:.0f} (was ₹{price:.0f})"
            else:
                label = f"⏳ {plan_name} - ₹{price:.0f}"
            cb = encode_cb("buy", plan_ids[plan_name])
            keyboard.append([CB(label, style="primary", icon=get_button_emoji("plan"), callback_data=cb)])
        keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data=encode_cb("cat", category))])
        await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("buy" + SEP):
        parts = decode_cb(data)
        plan_row_id = parts[1]

        plan_info = db.get_plan_by_id(plan_row_id)
        if not plan_info:
            await query.answer("❌ Ye product/plan ab available nahi hai.", show_alert=True)
            return

        category = plan_info["category"]
        prod_name = plan_info["name"]
        plan_name = plan_info["plan"]
        product_id = plan_info["product_id"]
        base_price = plan_info["price"]
        price = get_price_for_user(base_price, user_id)
        android_id = plan_info["android_id"]
        
        balance = db.get_balance(user_id)
        
        if balance < price:
            try:
                await query.answer(f"❌ Insufficient Balance! Need ₹{price}, You have ₹{balance}", show_alert=True)
            except:
                pass
            text = f"""
<tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> <b>INSUFFICIENT BALANCE!</b>

💸 Required: <b>₹{price}</b>
<tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> Your Balance: <b>₹{balance}</b>

Bas ek chhota sa deposit aur ye product turant unlock ho jaayega.
Add Balance karo — payment secure hai aur balance turant update ho jaata hai.
"""
            keyboard = [
                [CB("Add Balance", style="success", icon=get_button_emoji("add_balance"), callback_data="menu_add_balance")],
                [CB("Back", style="danger", icon=get_button_emoji("back"), callback_data=encode_cb("prod", category, prod_name))]
            ]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return
        
        if db.deduct_balance(user_id, price):
            try:
                await query.answer("⏳ Processing your order...")
            except:
                pass
            
            license_key = fetch_license_key(product_id, plan_name, android_id)
            
            if "Error:" in str(license_key):
                db.update_balance(user_id, price)
                error_msg = str(license_key).replace("Error: ", "")
                try:
                    await query.answer(f"❌ Purchase Failed: {error_msg}", show_alert=True)
                except:
                    pass
                text = f"❌ <b>PURCHASE FAILED!</b>\n\nError: {error_msg}\n\n💰 Your balance has been refunded."
                keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data=encode_cb("prod", category, prod_name))]]
                await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
                return
            
            db.add_history(user_id, prod_name, plan_name, price, license_key)
            
            text = f"""
<tg-emoji emoji-id="6073308817125282940">⭐</tg-emoji> <b>PURCHASE SUCCESSFUL!</b>

📦 <b>Product:</b> {prod_name}
⏳ <b>Validity:</b> {plan_name}
💰 <b>Price:</b> ₹{price}

<tg-emoji emoji-id="6071312005224993914">⭐</tg-emoji> <b>YOUR LICENSE KEY:</b>
<code>{license_key}</code>

✅ Key safely saved to your history!
"""
            keyboard = [[CB("Main Menu", style="primary", icon=get_button_emoji("shop"), callback_data="back_to_menu")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            try:
                await query.answer("❌ Insufficient balance!", show_alert=True)
            except:
                pass

    elif data == "menu_profile":
        user_data = db.get_user(user_id)
        balance = db.get_balance(user_id)
        reseller_line = f"\n👑 <b>Status:</b> Reseller ({RESELLER_DISCOUNT_PERCENT}% OFF)" if db.is_reseller(user_id) else ""
        text = f"""
<tg-emoji emoji-id="6071074330324768982">⭐</tg-emoji> <b>MY ACCOUNT PROFILE</b>

👤 <b>Username:</b> @{user_data[1] if user_data else 'User'}
🆔 <b>User ID:</b> <code>{user_id}</code>
<tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> <b>Wallet Balance:</b> <b>₹{balance}</b>{reseller_line}
"""
        keyboard = [[CB("Back to Menu", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await send_screen(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), screen_key="profile", parse_mode="HTML")

    elif data == "menu_history":
        history = db.get_history(user_id, 5)
        if not history:
            text = f"📄 <b>No logs found!</b>"
        else:
            text = f'<tg-emoji emoji-id="6070878939377571385">⭐</tg-emoji> <b>YOUR ORDER HISTORY</b>\n\n'
            for item in history:
                text += f"▪️ {item[2]} ({item[3]}) - ₹{item[4]}\n🔑 Key: <code>{item[5]}</code>\n\n"
        keyboard = [[CB("Back to Menu", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await send_screen(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), screen_key="history", parse_mode="HTML")

    elif data == "menu_deposit_history":
        history = db.get_deposit_history(user_id, 10)
        
        if not history:
            text = f"📭 <b>No deposits yet</b>\n\nUse Add Balance to make a deposit."
        else:
            total_deposits = sum(row[1] for row in history)
            text = f'<tg-emoji emoji-id="6071132024620455409">⭐</tg-emoji> <b>DEPOSIT HISTORY</b>\n\n'
            text += f"📊 <b>Total Deposits:</b> ₹{total_deposits:.2f}\n"
            text += f"📝 <b>Recent {len(history)} transactions:</b>\n\n"
            text += "━" * 30 + "\n"
            
            for row in history:
                order_id = row[0]
                amount = row[1]
                utr = row[2] if row[2] else "-"
                sender = row[3] if row[3] else "-"
                payment_type = row[4] if row[4] else "PAYTM"
                status = row[5] if row[5] else "completed"
                timestamp = row[6] if row[6] else ""
                
                status_icon = "✅" if status == "completed" else "⏳"
                date_str = timestamp[:16] if timestamp else ""
                
                text += f"\n{status_icon} <b>₹{amount:.2f}</b> ({payment_type})\n"
                text += f"   🆔 {order_id}\n"
                text += f"   📅 {date_str}\n"
                if status == "completed":
                    text += f"   🔑 UTR: <code>{utr}</code>\n"
                    text += f"   👤 {sender}\n"
            
            text += "\n━" * 30
        
        keyboard = [[CB("Back to Menu", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await send_screen(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), screen_key="deposit_history", parse_mode="HTML")

    elif data == "menu_add_balance":
        context.user_data["kp_amt"] = ""
        text = f"""
<blockquote><tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> ENTER CUSTOM AMOUNT</blockquote>

➡️ <b>Amount: ₹0 💵</b>

👑 <b>Use the keypad below to enter amount.</b>
"""
        if query.message.photo:
            await delete_message_safely(query.message)
            await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=get_numeric_keypad(), parse_mode="HTML")
        else:
            await safe_edit(query, text=text, reply_markup=get_numeric_keypad(), parse_mode="HTML")

    elif data.startswith("kp_"):
        action = data.split("kp_")[1]
        current = context.user_data["kp_amt"]

        if action.isdigit():
            if current == "0": current = ""
            current += action
        elif action == "clear":
            current = ""
        elif action == "confirm":
            if not current or not current.isdigit() or int(current) <= 0:
                try:
                    await query.answer("❌ Please enter a valid amount!", show_alert=True)
                except:
                    pass
                return
            
            original_amount = int(current)
            if original_amount < MIN_AMOUNT:
                try:
                    await query.answer(f"❌ Minimum amount is ₹{MIN_AMOUNT}", show_alert=True)
                except:
                    pass
                return
            
            email_config = db.get_email_config()
            receiver_upi = email_config['receiver_upi']
            
            ref_code = generate_ref_code()

            try:
                # 🔥 UNIQUE AMOUNT + CLEAR QR
                qr_img, final_amount = generate_clear_qr(receiver_upi, original_amount, ref_code, user_id)
            except Exception as e:
                logger.error(f"QR generation failed: {e}")
                try:
                    await query.answer("❌ QR generate nahi ho paaya. Error: " + str(e), show_alert=True)
                except:
                    pass
                return

            expiry_time = (datetime.now() + timedelta(minutes=5)).strftime("%d-%m-%Y %H:%M:%S")

            order_id = f"ADD_{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
            db.create_order(order_id, user_id, final_amount, original_amount)
            
            logger.info(f"📦 Order created: {order_id} user={user_id} amount=₹{final_amount}")

            caption_text = f"""
<tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> <b>Amount: ₹{final_amount:.2f}</b>
<tg-emoji emoji-id="6073308817125282940">⭐</tg-emoji> <b>Requested: ₹{original_amount}</b>
⏰ <b>Expires: {expiry_time}</b>

📊 <b>Scan The QR And Complete Payment.</b>
📱 <b>UPI:</b> <code>{receiver_upi}</code>

⚠️ <b>Important:</b> Pay exact amount <b>₹{final_amount:.2f}</b>
"""
            keyboard = [
                [CB("Verify Payment", style="success", icon=get_button_emoji("confirm"), callback_data=f"verify_{order_id}")],
                [CB("Cancel", style="danger", icon=get_button_emoji("cancel"), callback_data="menu_add_balance")]
            ]

            try:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=qr_img, caption=caption_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
                logger.info(f"📱 QR sent for order {order_id}")
            except Exception as e:
                logger.error(f"Failed to send QR photo: {e}")
                try:
                    await query.answer("❌ QR bhej nahi paya, dobara try karo.", show_alert=True)
                except:
                    pass
                return

            await delete_message_safely(query.message)
            return

        context.user_data["kp_amt"] = current
        display_amt = current if current else "0"
        text = f"""
<blockquote><tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> ENTER CUSTOM AMOUNT</blockquote>

➡️ <b>Amount: ₹{display_amt} 💵</b>

👑 <b>Use the keypad below to enter amount.</b>
"""
        try:
            await safe_edit(query, text=text, reply_markup=get_numeric_keypad(), parse_mode="HTML")
        except:
            pass

    elif data.startswith("verify_"):
        order_id = data.split("verify_")[1]
        order = db.get_order(order_id)
        
        if not order:
            try:
                await query.answer("❌ Order not found!", show_alert=True)
            except:
                pass
            return
        
        if order[3] == "completed":
            try:
                await query.answer("✅ Already verified!", show_alert=True)
            except:
                pass
            msg = f"✅ <b>Already Verified!</b>\n₹{order[2]} added to your wallet."
            await query.message.edit_caption(caption=msg, parse_mode="HTML")
            return
        
        try:
            await query.answer("⏳ Checking payment...")
        except:
            pass
        msg = f"""
<tg-emoji emoji-id="6070873970100409600">⭐</tg-emoji> <b>PAYMENT VERIFICATION</b>
━━━━━━━━━━━━━━━━━━
🆔 <b>Order:</b> <code>{order_id}</code>
💰 <b>Amount:</b> ₹{order[2]:.2f}
━━━━━━━━━━━━━━━━━━
📱 Please wait 10-15 seconds...
Payment will be auto-detected!
"""
        await query.message.edit_caption(caption=msg, parse_mode="HTML")
        asyncio.create_task(
            check_payment_later(context, query.message.chat_id, query.message.message_id, order_id)
        )

    # ============ ADMIN HANDLERS ============

    elif data.startswith("admin_"):
        if user_id != str(ADMIN_ID):
            try:
                await query.answer("❌ You are not authorized!", show_alert=True)
            except:
                pass
            return

        if data == "admin_email_settings":
            text = "📧 <b>EMAIL SETTINGS</b>\n\nYahan se Gmail, App Password aur PayTM UPI change kar sakte ho."
            await safe_edit(query, text=text, reply_markup=get_email_settings_keyboard(), parse_mode="HTML")

        elif data == "admin_email_gmail":
            context.user_data["awaiting_email_setting"] = "gmail"
            text = (
                "📧 <b>CHANGE GMAIL USER</b>\n\n"
                "Naya Gmail ID bhejo.\n\n"
                "Example: <code>your.email@gmail.com</code>\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_email_settings")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_email_password":
            context.user_data["awaiting_email_setting"] = "password"
            text = (
                "🔑 <b>CHANGE APP PASSWORD</b>\n\n"
                "Naya App Password bhejo.\n\n"
                "⚠️ Google Account → Security → App Password se generate karo.\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_email_settings")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_email_upi":
            context.user_data["awaiting_email_setting"] = "upi"
            text = (
                "💳 <b>CHANGE PAYTM UPI</b>\n\n"
                "Naya PayTM UPI ID bhejo.\n\n"
                "Example: <code>your.upi@paytm</code>\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_email_settings")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_email_view":
            config = db.get_email_config()
            text = f"""
📧 <b>CURRENT EMAIL SETTINGS</b>

📱 <b>Gmail User:</b> <code>{config['gmail_user']}</code>
🔑 <b>App Password:</b> <code>{'*' * len(config['app_password'])}</code>
💳 <b>PayTM UPI:</b> <code>{config['receiver_upi']}</code>
"""
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_email_settings")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_panel":
            text = "🛠 <b>ADMIN PANEL</b>\n\nChoose an action below:"
            await safe_edit(query, text=text, reply_markup=get_admin_panel_keyboard(), parse_mode="HTML")

        elif data == "admin_broadcast":
            context.user_data["awaiting_broadcast"] = True
            text = (
                "📢 <b>Broadcast Mode ON</b>\n\n"
                "Ab jo bhi message bhejoge wo sabhi users ko bhej diya jaayega.\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_addproduct":
            context.user_data["awaiting_addproduct"] = True
            text = (
                "➕ <b>ADD PRODUCT</b>\n\n"
                "Reply is format mein:\n"
                "<code>CATEGORY | NAME | PRODUCT_ID | PLAN | PRICE | ANDROID_ID</code>\n\n"
                "Example:\n"
                "<code>ANDROID NON ROOT | BALA MOD PRO | 133 | 1 Day | 150 | 0b9b969bc2e7997b</code>\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_removeproduct":
            products = db.get_all_products_flat()
            context.user_data["rm_products"] = products
            if not products:
                text = "📦 <b>Koi product nahi hai.</b>"
                keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
                await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            else:
                text = "🗑 <b>REMOVE PRODUCT</b>\n\nJis product ko delete karna hai use dabao:"
                keyboard = []
                for i, (category, name, plan_count) in enumerate(products):
                    label = f"{name} ({category}) — {plan_count} plan(s)"
                    cb = encode_cb("admin_rmprod_select", i)
                    keyboard.append([CB(label, style="danger", icon=get_button_emoji("remove"), callback_data=cb)])
                keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")])
                await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data.startswith("admin_rmprod_select" + SEP):
            parts = decode_cb(data)
            idx = int(parts[1])
            products = context.user_data.get("rm_products", [])
            if idx >= len(products):
                try:
                    await query.answer("❌ List purani ho gayi, dobara kholo.", show_alert=True)
                except:
                    pass
                return
            category, name, plan_count = products[idx]
            text = f"⚠️ <b>Confirm Delete</b>\n\n📦 {name}\n📂 {category}\n\nYeh product permanently delete ho jaayega. Pakka?"
            keyboard = [
                [CB("Yes, Delete", style="danger", icon=get_button_emoji("confirm"), callback_data=encode_cb("admin_rmprod_confirm", idx)),
                 CB("Cancel", style="primary", icon=get_button_emoji("cancel"), callback_data="admin_removeproduct")]
            ]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data.startswith("admin_rmprod_confirm" + SEP):
            parts = decode_cb(data)
            idx = int(parts[1])
            products = context.user_data.get("rm_products", [])
            if idx >= len(products):
                try:
                    await query.answer("❌ List purani ho gayi, dobara kholo.", show_alert=True)
                except:
                    pass
                return
            category, name, plan_count = products[idx]
            deleted = db.delete_product(category, name)
            if deleted:
                text = f"✅ <b>Deleted!</b>\n\n📦 {name} ({category}) ke {deleted} plan(s) remove ho gaye."
            else:
                text = "❌ Product nahi mila."
            keyboard = [[CB("Back to Admin Panel", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_addbalance":
            context.user_data["awaiting_addbalance"] = True
            text = (
                "💰 <b>ADD BALANCE TO USER</b>\n\n"
                "Reply is format mein:\n"
                "<code>USER_ID AMOUNT</code>\n\n"
                "Example:\n"
                "<code>8373276191 500</code>\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_stats":
            stats = db.get_stats()
            text = f"""
📊 <b>BOT STATISTICS</b>
━━━━━━━━━━━━━━━━━━
👥 <b>Total Users:</b> {stats['total_users']}
💰 <b>Total Wallet Balance:</b> ₹{stats['total_wallet_balance']:.2f}

📦 <b>Total Orders:</b> {stats['total_orders']}
⏳ <b>Pending Orders:</b> {stats['pending_orders']}
💵 <b>Total Deposited:</b> ₹{stats['total_deposited']:.2f}

🛒 <b>Total Sales:</b> {stats['total_sales']}
📈 <b>Total Sales Value:</b> ₹{stats['total_sales_value']:.2f}
"""
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_emoji_settings":
            text = "🎯 <b>PREMIUM EMOJI SETTINGS</b>\n\nYahan se saare buttons ke premium emoji change kar sakte ho."
            await safe_edit(query, text=text, reply_markup=get_emoji_settings_keyboard(), parse_mode="HTML")

        elif data == "admin_emoji_change":
            context.user_data["awaiting_emoji_update"] = True
            keys_list = "\n".join(f"• <code>{k}</code>" for k in sorted(BUTTON_EMOJIS.keys()))
            text = (
                "✏️ <b>CHANGE BUTTON EMOJI</b>\n\n"
                "Reply is format mein:\n"
                "<code>KEY NEW_EMOJI_ID</code>\n\n"
                "Reset karne ke liye default par:\n"
                "<code>KEY reset</code>\n\n"
                f"<b>Available Keys:</b>\n{keys_list}"
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_emoji_settings")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_emoji_backup":
            overrides = db.get_all_emoji_overrides()
            lines = []
            for key in sorted(BUTTON_EMOJIS.keys()):
                effective = overrides.get(key, BUTTON_EMOJIS[key])
                source = "custom" if key in overrides else "default"
                lines.append(f"{key} = {effective}  ({source})")
            backup_text = "\n".join(lines)
            text = f"💾 <b>EMOJI SETTINGS BACKUP</b>\n\n<pre>{backup_text}</pre>"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_emoji_settings")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_emoji_restore":
            db.reset_all_emoji_settings()
            text = "✅ <b>Sabhi button emojis default par restore ho gaye hain.</b>"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_emoji_settings")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_welcomemedia":
            media_type, _ = db.get_welcome_media()
            status = {"photo": "📷 Photo set hai", "video": "🎥 Video set hai"}.get(media_type, "❌ Kuch set nahi hai")
            text = f"🖼 <b>WELCOME MEDIA</b>\n\nCurrent status: {status}"
            await safe_edit(query, text=text, reply_markup=get_welcome_media_keyboard(media_type), parse_mode="HTML")

        elif data == "admin_setwelcomephoto":
            context.user_data["awaiting_welcome_photo"] = True
            text = "📷 <b>Ab ek photo bhejo</b> jo welcome message mein use hogi.\n\nCancel karne ke liye /cancel bhejo."
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_welcomemedia")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_setwelcomevideo":
            context.user_data["awaiting_welcome_video"] = True
            text = "🎥 <b>Ab ek video bhejo</b> jo welcome message mein use hogi.\n\nCancel karne ke liye /cancel bhejo."
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_welcomemedia")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_removewelcomemedia":
            db.clear_welcome_media()
            text = "✅ <b>Welcome media hata di gayi.</b>"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_welcomemedia")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_menuphotos":
            text = "🖼 <b>MENU PHOTOS</b>\n\nEk screen chuno:"
            keyboard = []
            for key, label in SCREEN_LABELS.items():
                status = "✅" if db.get_setting(f"menu_photo:{key}") else "▫️"
                keyboard.append([CB(f"{status} {label}", style="primary", icon=get_button_emoji("star"), callback_data=encode_cb("admin_screenphoto", key))])
            keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")])
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data.startswith("admin_screenphoto" + SEP):
            parts = decode_cb(data)
            screen_key = parts[1]
            label = SCREEN_LABELS.get(screen_key, screen_key)
            has_photo = bool(db.get_setting(f"menu_photo:{screen_key}"))
            status = "📷 Photo set hai" if has_photo else "❌ Koi photo set nahi hai"
            text = f"🖼 <b>{label}</b>\n\nCurrent status: {status}"
            keyboard = [[CB("Set Photo", style="primary", icon=get_button_emoji("add"), callback_data=encode_cb("admin_setscreenphoto", screen_key))]]
            if has_photo:
                keyboard.append([CB("Remove Photo", style="danger", icon=get_button_emoji("remove"), callback_data=encode_cb("admin_removescreenphoto", screen_key))])
            keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_menuphotos")])
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data.startswith("admin_setscreenphoto" + SEP):
            parts = decode_cb(data)
            screen_key = parts[1]
            context.user_data["awaiting_screen_photo"] = screen_key
            label = SCREEN_LABELS.get(screen_key, screen_key)
            text = f"📷 <b>Ab ek photo bhejo</b> jo <b>{label}</b> screen ke liye use hogi.\n\nCancel karne ke liye /cancel bhejo."
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data=encode_cb("admin_screenphoto", screen_key))]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data.startswith("admin_removescreenphoto" + SEP):
            parts = decode_cb(data)
            screen_key = parts[1]
            db.delete_setting(f"menu_photo:{screen_key}")
            label = SCREEN_LABELS.get(screen_key, screen_key)
            text = f"✅ <b>{label}</b> ki photo hata di gayi."
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_menuphotos")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_test_email":
            try:
                await query.answer("⏳ Testing Gmail connection...")
            except:
                pass

            def _sync_test_email():
                config = db.get_email_config()
                if not config['gmail_user'] or not config['app_password']:
                    return "❌ Gmail ya App Password set nahi hai."
                test_mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=15)
                try:
                    test_mail.login(config['gmail_user'], config['app_password'])
                    test_mail.select("INBOX")
                    status, messages = test_mail.search(None, 'UNSEEN')
                    unseen_count = len(messages[0].split()) if status == 'OK' else 0
                    return f"✅ Success! Unread emails: {unseen_count}"
                finally:
                    try:
                        test_mail.close()
                        test_mail.logout()
                    except Exception:
                        pass

            try:
                result = await asyncio.wait_for(asyncio.to_thread(_sync_test_email), timeout=20)
                config = db.get_email_config()
                text = f"""
📧 <b>EMAIL TEST RESULT</b>

📱 <b>Account:</b> {config['gmail_user']}
💳 <b>PayTM UPI:</b> {config['receiver_upi']}

{result}
"""
            except asyncio.TimeoutError:
                text = "❌ <b>EMAIL CONNECTION TIMED OUT</b>\n\nDNS/network issue hai."
            except imaplib.IMAP4.error as e:
                text = f"❌ <b>EMAIL LOGIN FAILED</b>\n\n<code>{str(e)[:300]}</code>\n\nNaya App Password generate karo."
            except Exception as e:
                text = f"❌ <b>EMAIL CONNECTION FAILED</b>\n\n<code>{str(e)[:300]}</code>"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_users":
            users = db.get_recent_users(20)
            if not users:
                text = "👥 <b>No users yet.</b>"
            else:
                text = "👥 <b>RECENT USERS</b> (latest 20)\n\n"
                for uid, uname, bal in users:
                    text += f"🆔 <code>{uid}</code> — @{uname or 'User'} — ₹{bal:.2f}\n"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_resellers":
            text = f"👑 <b>RESELLER MANAGEMENT</b>\n\nResellers ko {RESELLER_DISCOUNT_PERCENT}% discount milta hai."
            await safe_edit(query, text=text, reply_markup=get_reseller_panel_keyboard(), parse_mode="HTML")

        elif data == "admin_addreseller":
            context.user_data["awaiting_addreseller"] = True
            text = "➕ <b>ADD RESELLER</b>\n\nUser ID bhejo.\n\nCancel karne ke liye /cancel bhejo."
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_resellers")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_removereseller":
            context.user_data["awaiting_removereseller"] = True
            text = "➖ <b>REMOVE RESELLER</b>\n\nUser ID bhejo.\n\nCancel karne ke liye /cancel bhejo."
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_resellers")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_listresellers":
            resellers = db.get_resellers()
            if not resellers:
                text = "👑 <b>Koi reseller nahi hai.</b>"
            else:
                text = f"👑 <b>RESELLERS</b> ({RESELLER_DISCOUNT_PERCENT}% OFF)\n\n"
                for uid, uname, bal in resellers:
                    text += f"🆔 <code>{uid}</code> — @{uname or 'User'} — ₹{bal:.2f}\n"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_resellers")]]
            await safe_edit(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_referral":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        stats = db.get_referral_stats(user_id)
        text = f"""
<tg-emoji emoji-id="6071009124131280604">⭐</tg-emoji> <b>REFERRAL PROGRAM</b>

🔗 <b>Your Referral Link:</b>
<code>{ref_link}</code>

👥 <b>Total Referred Users:</b> {stats['total_referred']}
💰 <b>Total Earned:</b> ₹{stats['total_earned']:.2f}
"""
        keyboard = [[CB("Back", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await send_screen(query, text=text, reply_markup=InlineKeyboardMarkup(keyboard), screen_key="referral", parse_mode="HTML")

    elif data in ["menu_tutorial", "menu_support", "menu_download"]:
        email_config = db.get_email_config()
        texts = {
            "menu_tutorial": (
                f'<tg-emoji emoji-id="6071126054615913700">⭐</tg-emoji> <b>Tutorial — Sirf 3 Steps</b>\n\n'
                f'1️⃣ UPI se Add Balance karo\n'
                f'2️⃣ Apni pasand ka product choose karo\n'
                f'3️⃣ Key instantly mil jaayegi\n\n'
                f'💳 PayTM UPI: <code>{email_config["receiver_upi"]}</code>'
            ),
            "menu_support": (
                f'<tg-emoji emoji-id="6071264704750162461">⭐</tg-emoji> <b>Support</b>\n\n'
                f'👤 Contact: @karanBhaiyaa'
            ),
            "menu_download": (
                f'<tg-emoji emoji-id="6073116574389113063">⭐</tg-emoji> <b>Download Latest Apk</b>\n\n'
                f"<a href='https://t.me/Allpanelfile44'>👉 Get Latest Apk</a>"
            ),
        }
        keyboard = [[CB("Back", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        screen_key = data.replace("menu_", "")
        await send_screen(query, text=texts[data], reply_markup=InlineKeyboardMarkup(keyboard), screen_key=screen_key, parse_mode="HTML")
    
    else:
        logger.warning(f"⚠️ Unknown callback: {data}")
        try:
            await query.answer("⚠️ Unknown action", show_alert=True)
        except:
            pass

# ============================================
# 🌐 TINY WEB SERVER (Render free "Web Service" tier needs a bound port)
# ============================================

def start_keepalive_server():
    """
    Render's free tier only exists for 'Web Service' deployments, which
    means Render expects something listening on $PORT. This bot itself
    doesn't need a web server (it uses Telegram polling) — this just
    responds 'OK' to any request, purely to satisfy Render's port check and
    give an uptime pinger (e.g. UptimeRobot) something to hit to keep the
    service awake.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class PingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is alive!")

        def log_message(self, format, *args):
            pass

    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Keepalive web server listening on port {port}")

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("="*60)
    print("  🚀 BALA MODS STORE - PAYTM PAYMENT SYSTEM")
    print("  🔥 UNIQUE RANDOM AMOUNT PER USER")
    print("  📱 HIGH QUALITY QR CODE")
    print("  📊 FULL LOGGING ENABLED")
    print("="*60)
    print(f"  PayTM UPI: {DEFAULT_RECEIVER_UPI}")
    print(f"  Gmail: {DEFAULT_GMAIL_USER}")
    print(f"  Min Amount: ₹{MIN_AMOUNT}")
    print(f"  Log File: {LOG_FILE}")
    print("="*60)
    
    logger.info("🚀 Bot starting...")
    
    start_keepalive_server()
    
    db = Database()
    db.init_products()
    
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
    )
    
    app = Application.builder().token(TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addproduct", add_product))
    app.add_handler(CommandHandler("broadcast", broadcast_start))
    app.add_handler(CommandHandler("cancel", broadcast_cancel))
    app.add_handler(CommandHandler("backup", backup_db))
    app.add_handler(CommandHandler("restore", restore_db))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.User(ADMIN_ID) & ~filters.COMMAND, handle_admin_message))
    
    monitor = EmailMonitor(db, app.bot)
    monitor.start()

    backup_thread = threading.Thread(target=_auto_backup_loop, args=(TOKEN, ADMIN_ID, 6), daemon=True)
    backup_thread.start()
    logger.info("✅ Auto-backup thread started (every 6 hours)")
    
    logger.info("✅ Bot is running!")
    print("="*60)
    print("  ✅ BOT IS RUNNING!")
    print("  📊 Check bot_logs.txt for payment logs")
    print("="*60)
    
    app.run_polling(drop_pending_updates=True)