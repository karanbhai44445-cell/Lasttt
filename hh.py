usr/bin/env python3
# -*- coding: utf-8 -*-

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
from datetime import datetime, timedelta
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

# ============================================
# ✅ CONFIG
# ============================================

TOKEN = "8833898625:AAEW18HVT9CIzvTW0lP7U6nub8FuXjX2bUI"
ADMIN_ID = 8954667761

GMAIL_USER = "karanbhaiya699@gmail.com"
APP_PASSWORD = "zrik hlyk ttdl qpol"
RECEIVER_UPI = "vikrambhaiyaaa@fam"
MIN_AMOUNT = 1
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_data.db")
RESELLER_DISCOUNT_PERCENT = 15
REFERRAL_COMMISSION_PERCENT = 0.5  # referrer ko referred user ke har deposit ka 0.5% milega

API_ENDPOINT = "https://xyzcheats.com/api/reseller_v1.php"
API_KEY = "2c59f7c31055b7b9b61f5bb6a0ae85e0"
MASTER_KEY = "a7f3e8b2c9d1f4a6b8c2d5e9f1a3b6c8"
ANDROID_ID = "0b9b969bc2e7997b"

# ============================================
# 🎯 PREMIUM EMOJI IDs - ONLY FOR BUTTONS
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
    """Get button emoji ID"""
    return BUTTON_EMOJIS.get(name, "")

def get_price_for_user(base_price, user_id):
    """Apply reseller discount if the user is a reseller."""
    if db.is_reseller(user_id):
        return round(base_price * (1 - RESELLER_DISCOUNT_PERCENT / 100), 2)
    return base_price

def parse_product_line(text):
    """
    Parse 'CATEGORY | NAME | PRODUCT_ID | PLAN | PRICE | ANDROID_ID' safely.
    Returns a dict on success, or raises ValueError with a friendly message.
    """
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

    # Clean price of currency symbols/commas/spaces (₹150, 1,500 etc.)
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

def CB(text, style="primary", icon=None, **kwargs):
    """Create colored button with premium emoji icon"""
    if "ADMIN" in text.upper() or "OWNER" in text.upper():
        style = "danger"
    return ColoredButton(text, style=style, icon=icon, **kwargs)

def get_category_emoji(category):
    """Pick a fitting icon for a product category button."""
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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# 🎲 RANDOM AMOUNT GENERATOR
# ============================================

def generate_random_amount(base_amount):
    decimals = [0.1, 0.3, 0.5, 0.7, 0.9]
    random_decimal = random.choice(decimals)
    
    if float(base_amount).is_integer():
        return float(base_amount) + random_decimal
    else:
        return float(base_amount)

# ============================================
# DATABASE
# ============================================

class Database:
    def __init__(self):
        self.db = DB_FILE
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        
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
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount REAL,
                status TEXT DEFAULT 'pending',
                utr TEXT,
                sender TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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

        c.execute('''
            CREATE TABLE IF NOT EXISTS deposit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                order_id TEXT,
                amount REAL,
                utr TEXT,
                sender TEXT,
                status TEXT DEFAULT 'completed',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(" Database ready!")
    
    def init_user(self, user_id, username):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        if not c.fetchone():
            c.execute('INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)',
                     (user_id, username, 0))
            conn.commit()
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

    # -------- Referral System --------

    def set_referrer(self, user_id, referrer_id):
        """Set referred_by only once, for a brand new user, and never referring themselves."""
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
    
    def deduct_balance(self, user_id, amount):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?', 
                 (amount, user_id, amount))
        conn.commit()
        conn.close()
        return c.rowcount > 0
    
    def create_order(self, order_id, user_id, amount):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('INSERT INTO orders (order_id, user_id, amount) VALUES (?, ?, ?)',
                 (order_id, user_id, amount))
        conn.commit()
        conn.close()
    
    def update_order(self, order_id, status, utr="", sender=""):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            UPDATE orders SET status = ?, utr = ?, sender = ? WHERE order_id = ?
        ''', (status, utr, sender, order_id))
        conn.commit()
        conn.close()
    
    def get_order(self, order_id):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
        row = c.fetchone()
        conn.close()
        return row
    
    def get_pending_by_amount(self, amount):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT order_id, user_id FROM orders 
            WHERE status = 'pending' AND ABS(amount - ?) <= 0.01
            ORDER BY timestamp ASC LIMIT 1
        ''', (amount,))
        row = c.fetchone()
        conn.close()
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
        """Fetch full product/plan info by the products table row id (short & safe for callback_data)."""
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
        """List of distinct (category, name) products, with how many plans each has."""
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
        """Delete a product (and all its plans) by category + name."""
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
            print(f" {len(products)} products initialized!")
        conn.close()
    
    def add_deposit_history(self, user_id, order_id, amount, utr="", sender="", status="completed"):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            INSERT INTO deposit_history (user_id, order_id, amount, utr, sender, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, order_id, amount, utr, sender, status))
        conn.commit()
        conn.close()
    
    def get_deposit_history(self, user_id, limit=10):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''
            SELECT order_id, amount, utr, sender, status, timestamp 
            FROM deposit_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows

# ============================================
# QR CODE GENERATOR
# ============================================

def generate_upi_qr(upi_id, amount, ref_code):
    try:
        original_amount = float(amount)
        final_amount = generate_random_amount(original_amount)
        final_amount = round(final_amount, 2)
        
        upi_url = f"upi://pay?pa={upi_id}&pn=Store&am={final_amount}&tr={ref_code}&tn={ref_code}&cu=INR"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(upi_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = io.BytesIO()
        img.save(bio, format='PNG')
        bio.seek(0)
        
        return bio, final_amount
        
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        raise Exception(f"QR generate nahi ho paaya: {e}")

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
        logger.info(f"API Response: {response.text}")
        
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
# 📧 AUTO-PAYMENT MONITOR
# ============================================

class EmailMonitor:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self.running = False
        self.thread = None
        self.GMAIL_USER = GMAIL_USER
        self.APP_PASSWORD = APP_PASSWORD
    
    def start(self):
        if not self.GMAIL_USER or not self.APP_PASSWORD:
            print(" Gmail not configured!")
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()
        print(" Auto-payment monitor started!")
    
    def stop(self):
        self.running = False
    
    def _monitor(self):
        while self.running:
            try:
                self._check_emails()
            except Exception as e:
                print(f"Monitor error: {e}")
            time.sleep(10)
    
    def _check_emails(self):
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.GMAIL_USER, self.APP_PASSWORD)
            mail.select("INBOX")
            
            status, messages = mail.search(None, 'UNSEEN')
            if status == 'OK':
                for num in messages[0].split():
                    status, data = mail.fetch(num, '(RFC822)')
                    if status == 'OK':
                        msg = email.message_from_bytes(data[0][1])
                        self._process_email(msg)
                        mail.store(num, '+FLAGS', '\\Seen')
            
            mail.close()
            mail.logout()
        except Exception as e:
            print(f"Email error: {e}")
    
    def _process_email(self, msg):
        try:
            subject = str(msg.get("Subject", ""))
            if not any(k in subject.lower() for k in ['credit', 'credited', 'received', 'upi', 'payment']):
                return
            
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            amount_match = re.search(r'(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)', body, re.IGNORECASE)
            utr_match = re.search(r'(?:UTR|Transaction ID|Ref No|Txn ID|RRN)\s*:?\s*([A-Z0-9]+)', body, re.IGNORECASE)
            sender_match = re.search(r'(?:From|Sender|Credited to|Paid by|Name)\s*:?\s*([A-Za-z\s\.]+)', body, re.IGNORECASE)
            
            if amount_match:
                amount = float(amount_match.group(1).replace(',', ''))
                utr = utr_match.group(1).strip() if utr_match else 'N/A'
                sender = sender_match.group(1).strip() if sender_match else 'Unknown'
                
                print(f" Auto-payment: ₹{amount:.2f} | UTR: {utr}")
                
                result = self.db.get_pending_by_amount(amount)
                
                if result:
                    order_id, user_id = result
                    self.db.update_order(order_id, 'completed', utr, sender)
                    self.db.update_balance(user_id, amount)
                    self.db.add_deposit_history(user_id, order_id, amount, utr, sender)
                    print(f" Order {order_id} COMPLETED (Exact match)!")
                    
                    try:
                        self._send_user_success(user_id, order_id, amount, utr, sender)
                    except:
                        pass
                    self._credit_referral(user_id, amount)
                    return
                
                pending = self.db.get_all_pending()
                if pending:
                    closest = None
                    closest_diff = float('inf')
                    for p in pending:
                        diff = abs(p[2] - amount)
                        if diff < closest_diff:
                            closest_diff = diff
                            closest = p
                    
                    if closest and closest_diff <= 0.5:
                        order_id, user_id, order_amount = closest[0], closest[1], closest[2]
                        self.db.update_order(order_id, 'completed', utr, sender)
                        self.db.update_balance(user_id, amount)
                        self.db.add_deposit_history(user_id, order_id, amount, utr, sender)
                        print(f" Auto-matched (fuzzy): {order_id} (diff: {closest_diff:.2f})")
                        
                        try:
                            self._send_user_success(user_id, order_id, amount, utr, sender)
                        except:
                            pass
                        self._credit_referral(user_id, amount)
                        return
                    
                    print(f" No pending order found for ₹{amount:.2f}")
                
        except Exception as e:
            print(f"Process error: {e}")
    
    def _send_user_success(self, user_id, order_id, amount, utr, sender):
        msg = f"""
✅ <b>PAYMENT AUTO-VERIFIED!</b>
━━━━━━━━━━━━━━━━━━
🆔 <b>Order ID:</b> <code>{order_id}</code>
💰 <b>Amount:</b> ₹{amount:.2f}
🧾 <b>UTR:</b> <code>{utr}</code>
👤 <b>Sender:</b> {sender}
━━━━━━━━━━━━━━━━━━
💰 ₹{amount:.2f} added to your wallet!
"""
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": int(user_id), "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
        except:
            pass

    def _credit_referral(self, referred_user_id, deposit_amount):
        try:
            referrer_id = self.db.get_referrer(referred_user_id)
            if not referrer_id:
                return
            bonus = self.db.credit_referral_bonus(referrer_id, referred_user_id, deposit_amount, REFERRAL_COMMISSION_PERCENT)
            if bonus and bonus > 0:
                print(f" Referral bonus: ₹{bonus:.2f} to {referrer_id} (from {referred_user_id}'s ₹{deposit_amount:.2f} deposit)")
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
# 🔵 KEYBOARDS - ONLY PREMIUM EMOJIS IN BUTTONS
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
        [CB("Stats", style="primary", icon=get_button_emoji("stats"), callback_data="admin_stats"),
         CB("Users", style="primary", icon=get_button_emoji("users"), callback_data="admin_users")],
        [CB("Back to Menu", style="danger", icon=get_button_emoji("back"), callback_data="back_to_menu")]
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
        "Ab jo bhi message bhejoge (text, photo, video, voice, audio, document, sticker — kuch bhi) "
        "wo sabhi users ko bhej diya jaayega.\n\n"
        "Cancel karne ke liye /cancel bhejo.",
        parse_mode="HTML"
    )

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        return
    flags = ["awaiting_broadcast", "awaiting_addproduct", "awaiting_addbalance", "awaiting_addreseller", "awaiting_removereseller"]
    was_active = any(context.user_data.get(f) for f in flags)
    for f in flags:
        context.user_data[f] = False
    if was_active:
        await update.message.reply_text("❌ Cancelled.")

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        return

    if context.user_data.get("awaiting_addreseller"):
        context.user_data["awaiting_addreseller"] = False
        target_id = (update.message.text or "").strip()
        if not target_id.isdigit():
            await update.message.reply_text("❌ Invalid USER_ID.")
            return
        changed = db.set_reseller(target_id, True)
        if changed:
            await update.message.reply_text(f"✅ User <code>{target_id}</code> ab reseller hai ({RESELLER_DISCOUNT_PERCENT}% discount).", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=int(target_id),
                    text=f"👑 <b>Congratulations!</b> Aap ab Reseller ban gaye ho — sabhi products par {RESELLER_DISCOUNT_PERCENT}% discount milega!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await update.message.reply_text("❌ User not found. Pehle usko /start karwao.")
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
            await update.message.reply_text(
                f"✅ Product Added!\n"
                f"📦 {p['name']}\n"
                f"⏳ {p['plan']}\n"
                f"💰 ₹{p['price']:.2f}\n"
                f"🆔 ID: {p['product_id']}\n"
                f"📂 Category: {p['category']}"
            )
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
            await update.message.reply_text(
                f"✅ ₹{amt:.2f} added to user <code>{target_id}</code>\n"
                f"💰 New balance: ₹{new_balance:.2f}",
                parse_mode="HTML"
            )
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    is_new_user = db.get_user(user_id) is None
    db.init_user(user_id, user.username or "User")

    if context.args:
        payload = context.args[0].strip()
        referrer_id = payload.replace("ref_", "").strip()
        logger.info(f"Referral attempt: user={user_id} is_new={is_new_user} payload='{payload}' referrer={referrer_id}")

        if not is_new_user:
            logger.info(f"Referral skipped: {user_id} already existed in DB before this /start (not a new user).")
        elif not referrer_id.isdigit():
            logger.info(f"Referral skipped: payload '{payload}' is not a valid numeric id.")
        else:
            linked = db.set_referrer(user_id, referrer_id)
            if linked:
                logger.info(f"Referral linked: {user_id} -> referred by {referrer_id}")
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
                logger.info(f"Referral NOT linked: referrer {referrer_id} not found in DB, or {user_id} already had a referrer.")
    
    # ✅ CAPTION WITH NORMAL EMOJIS (JO PEHLE THE WAISE HI)
    welcome_text = (
        f'<tg-emoji emoji-id="6071312005224993914">⭐</tg-emoji> <b>Product Store : all key purchase & instantly delivery</b>\n'
        f'<tg-emoji emoji-id="6071074330324768982">⭐</tg-emoji> <b>My Profile : check your account information</b>\n'
        f'<tg-emoji emoji-id="6071132024620455409">⭐</tg-emoji> <b>Add Balance : deposit balance & secure service</b>\n'
        f'<tg-emoji emoji-id="6070878939377571385">⭐</tg-emoji> <b>Order History : check all key purchase history</b>\n'
        f'<tg-emoji emoji-id="6071132024620455409">⭐</tg-emoji> <b>Deposit History : check all your deposits</b>\n'
        f'<tg-emoji emoji-id="6071126054615913700">⭐</tg-emoji> <b>Tutorial : view tutorial and work this bot</b>\n'
        f'<tg-emoji emoji-id="6071264704750162461">⭐</tg-emoji> <b>Support : bot problem fixed for support admin</b>\n'
        f'<tg-emoji emoji-id="6073116574389113063">⭐</tg-emoji> <b>Download Hack : download latest apk for safety.</b>'
    )
    
    if update.message:
        is_admin = str(user.id) == str(ADMIN_ID)
        await update.message.reply_text(text=welcome_text, reply_markup=get_main_menu_keyboard(is_admin=is_admin), parse_mode="HTML")

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
            "Categories:\n"
            "🤖 ANDROID NON ROOT\n"
            "👑 ANDROID ROOT\n"
            "💻 PC\n"
            "🍎 IOS\n\n"
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
        await update.message.reply_text(
            f"✅ Product Added!\n"
            f"📦 {p['name']}\n"
            f"⏳ {p['plan']}\n"
            f"💰 ₹{p['price']:.2f}\n"
            f"🆔 ID: {p['product_id']}\n"
            f"📂 Category: {p['category']}"
        )
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
    """Wrapper: catches ANY error in button handling and shows it to the user
    directly in Telegram (as a popup alert), instead of failing silently."""
    query = update.callback_query
    try:
        await _handle_callbacks_inner(update, context)
    except Exception as e:
        logger.error(f"handle_callbacks error on data='{query.data}': {e}", exc_info=True)
        # A callback query can only be "answered" once. If _handle_callbacks_inner
        # already called query.answer() before failing later on, this second
        # answer() call itself raises and gets swallowed — meaning the user
        # would see NOTHING at all. So if the alert fails, fall back to a
        # normal chat message, which always works.
        alert_shown = False
        try:
            await query.answer(f"❌ Error: {str(e)[:180]}", show_alert=True)
            alert_shown = True
        except Exception:
            pass
        if not alert_shown:
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ <b>Error:</b> <code>{str(e)[:300]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        if str(update.effective_user.id) == str(ADMIN_ID):
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ <b>Bot Error</b>\n\n🔘 Button: <code>{query.data}</code>\n❌ Error: <code>{str(e)[:500]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

async def _handle_callbacks_inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = str(update.effective_user.id)
    
    await query.answer()
    db.init_user(user_id, update.effective_user.username or "User")
    
    if "kp_amt" not in context.user_data:
        context.user_data["kp_amt"] = ""

    # ✅ CAPTION WITH NORMAL EMOJIS (JO PEHLE THE WAISE HI)
    welcome_text = (
        f'<tg-emoji emoji-id="6071312005224993914">⭐</tg-emoji> <b>Product Store : all key purchase & instantly delivery</b>\n'
        f'<tg-emoji emoji-id="6071074330324768982">⭐</tg-emoji> <b>My Profile : check your account information</b>\n'
        f'<tg-emoji emoji-id="6071132024620455409">⭐</tg-emoji> <b>Add Balance : deposit balance & secure service</b>\n'
        f'<tg-emoji emoji-id="6070878939377571385">⭐</tg-emoji> <b>Order History : check all key purchase history</b>\n'
        f'<tg-emoji emoji-id="6071132024620455409">⭐</tg-emoji> <b>Deposit History : check all your deposits</b>\n'
        f'<tg-emoji emoji-id="6071126054615913700">⭐</tg-emoji> <b>Tutorial : view tutorial and work this bot</b>\n'
        f'<tg-emoji emoji-id="6071264704750162461">⭐</tg-emoji> <b>Support : bot problem fixed for support admin</b>\n'
        f'<tg-emoji emoji-id="6073116574389113063">⭐</tg-emoji> <b>Download Hack : download latest apk for safety.</b>'
    )

    if data == "back_to_menu":
        context.user_data["kp_amt"] = ""
        is_admin = user_id == str(ADMIN_ID)
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.message.chat_id, text=welcome_text, reply_markup=get_main_menu_keyboard(is_admin=is_admin), parse_mode="HTML")
        else:
            await query.message.edit_text(text=welcome_text, reply_markup=get_main_menu_keyboard(is_admin=is_admin), parse_mode="HTML")

    elif data == "menu_shop":
        products = db.get_products()
        text = f"<b>📊 HACK STORE — SHOP 💭</b>\n\n<tg-emoji emoji-id=\"6070873970100409600\">⭐</tg-emoji> <b>Choose your device category:</b>"
        keyboard = []
        
        for cat in products.keys():
            cb = encode_cb("cat", cat)
            keyboard.append([CB(f"{cat}", style="primary", icon=get_category_emoji(cat), callback_data=cb)])
        
        keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="back_to_menu")])
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("cat" + SEP):
        parts = decode_cb(data)
        category = parts[1]
        products = db.get_products()
        text = f"<b>📂 Category: {category}</b>\n\nSelect a product to purchase:"
        keyboard = []
        for prod_name in products.get(category, {}).keys():
            cb = encode_cb("prod", category, prod_name)
            keyboard.append([CB(f"{prod_name}", style="primary", icon=get_button_emoji("star"), callback_data=cb)])
        keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="menu_shop")])
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("prod" + SEP):
        parts = decode_cb(data)
        category = parts[1]
        prod_name = parts[2]
        products = db.get_products()
        plans = products[category][prod_name]["plans"]
        plan_ids = products[category][prod_name]["plan_ids"]
        is_reseller = db.is_reseller(user_id)

        text = f"<b>💎 Product: {prod_name}</b>\n\nChoose expiration pack period below:"
        if is_reseller:
            text += f"\n👑 <b>Reseller Price ({RESELLER_DISCOUNT_PERCENT}% OFF)</b>"
        keyboard = []
        for plan_name, price in plans.items():
            final_price = get_price_for_user(price, user_id)
            if is_reseller:
                label = f"⏳ {plan_name} - ₹{final_price:.0f} (was ₹{price:.0f})"
            else:
                label = f"⏳ {plan_name} - ₹{price:.0f}"
            # Use the short DB row id instead of embedding full category/name/plan text,
            # which can otherwise exceed Telegram's 64-byte callback_data limit for
            # longer product names and silently break the button.
            cb = encode_cb("buy", plan_ids[plan_name])
            keyboard.append([CB(label, style="primary", icon=get_button_emoji("plan"), callback_data=cb)])
        keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data=encode_cb("cat", category))])
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

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
            await query.answer(f"❌ Insufficient Balance! Need ₹{price}, You have ₹{balance}", show_alert=True)
            text = f"""
<tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> <b>INSUFFICIENT BALANCE!</b>

💸 Required: <b>₹{price}</b>
<tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> Your Balance: <b>₹{balance}</b>

Please add balance first.
"""
            keyboard = [
                [CB("Add Balance", style="success", icon=get_button_emoji("add_balance"), callback_data="menu_add_balance")],
                [CB("Back", style="danger", icon=get_button_emoji("back"), callback_data=encode_cb("prod", category, prod_name))]
            ]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return
        
        if db.deduct_balance(user_id, price):
            await query.answer("⏳ Processing your order...")
            
            license_key = fetch_license_key(product_id, plan_name, android_id)
            
            if "Error:" in str(license_key):
                db.update_balance(user_id, price)
                error_msg = str(license_key).replace("Error: ", "")
                await query.answer(f"❌ Purchase Failed: {error_msg}", show_alert=True)
                text = f"❌ <b>PURCHASE FAILED!</b>\n\nError: {error_msg}\n\n💰 Your balance has been refunded."
                keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data=encode_cb("prod", category, prod_name))]]
                await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
                return
            
            db.add_history(user_id, prod_name, plan_name, price, license_key)
            
            text = f"""
<tg-emoji emoji-id="6073308817125282940">⭐</tg-emoji> <b>PURCHASE SUCCESSFUL!</b>

📦 <b>Product:</b> {prod_name}
⏳ <b>Validity:</b> {plan_name}
💰 <b>Price:</b> ₹{price}

<tg-emoji emoji-id="6071312005224993914">⭐</tg-emoji> <b>YOUR LICENSE KEY:</b>
<code>{license_key}</code>

✅ Key saved to history!
"""
            keyboard = [[CB("Main Menu", style="primary", icon=get_button_emoji("shop"), callback_data="back_to_menu")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            await query.answer("❌ Insufficient balance!", show_alert=True)

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
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_history":
        history = db.get_history(user_id, 5)
        if not history:
            text = f"📄 <b>No logs found!</b>"
        else:
            text = f"<tg-emoji emoji-id=\"6070878939377571385\">⭐</tg-emoji> <b>YOUR ORDER HISTORY</b>\n\n"
            for item in history:
                text += f"▪️ {item[2]} ({item[3]}) - ₹{item[4]}\n🔑 Key: <code>{item[5]}</code>\n\n"
        keyboard = [[CB("Back to Menu", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_deposit_history":
        history = db.get_deposit_history(user_id, 10)
        
        if not history:
            text = f"📭 <b>No deposits yet</b>\n\nUse Add Balance to make a deposit."
        else:
            total_deposits = sum(row[1] for row in history)
            text = f"<tg-emoji emoji-id=\"6071132024620455409\">⭐</tg-emoji> <b>DEPOSIT HISTORY</b>\n\n"
            text += f"📊 <b>Total Deposits:</b> ₹{total_deposits:.2f}\n"
            text += f"📝 <b>Recent {len(history)} transactions:</b>\n\n"
            text += "━" * 30 + "\n"
            
            for row in history:
                order_id = row[0]
                amount = row[1]
                utr = row[2] if row[2] else "-"
                sender = row[3] if row[3] else "-"
                status = row[4] if row[4] else "completed"
                timestamp = row[5] if row[5] else ""
                
                status_icon = "✅" if status == "completed" else "⏳"
                date_str = timestamp[:16] if timestamp else ""
                
                text += f"\n{status_icon} <b>₹{amount:.2f}</b>\n"
                text += f"   🆔 {order_id}\n"
                text += f"   📅 {date_str}\n"
                if status == "completed":
                    text += f"   🔑 UTR: <code>{utr}</code>\n"
                    text += f"   👤 {sender}\n"
            
            text += "\n━" * 30
        
        keyboard = [[CB("Back to Menu", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_add_balance":
        context.user_data["kp_amt"] = ""
        text = f"""
<blockquote><tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> ENTER CUSTOM AMOUNT</blockquote>

➡️ <b>Amount: ₹0 💵</b>

👑 <b>Use the keypad below to enter amount.</b>
"""
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=get_numeric_keypad(), parse_mode="HTML")
        else:
            await query.message.edit_text(text=text, reply_markup=get_numeric_keypad(), parse_mode="HTML")

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
                await query.answer("❌ Please enter a valid amount!", show_alert=True)
                return
            
            original_amount = int(current)
            if original_amount < MIN_AMOUNT:
                await query.answer(f"❌ Minimum amount is ₹{MIN_AMOUNT}", show_alert=True)
                return
            
            ref_code = generate_ref_code()

            try:
                qr_img, final_amount = generate_upi_qr(RECEIVER_UPI, original_amount, ref_code)
            except Exception as e:
                logger.error(f"QR generation failed: {e}")
                await query.answer(
                    "❌ QR generate nahi ho paaya. Error: " + str(e),
                    show_alert=True
                )
                return

            expiry_time = (datetime.now() + timedelta(minutes=5)).strftime("%d-%m-%Y %H:%M:%S")

            order_id = f"ADD_{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
            db.create_order(order_id, user_id, final_amount)

            caption_text = f"""
<tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> <b>Amount: ₹{final_amount:.2f}</b>
<tg-emoji emoji-id="6073308817125282940">⭐</tg-emoji> <b>Requested: ₹{original_amount}</b>
⏰ <b>Expires: {expiry_time}</b>

📊 <b>Scan The QR And Complete Payment.</b>
📱 <b>UPI:</b> <code>{RECEIVER_UPI}</code>

⚠️ <b>Important:</b> Pay exact amount <b>₹{final_amount:.2f}</b>
"""
            keyboard = [
                [CB("Verify Payment", style="success", icon=get_button_emoji("confirm"), callback_data=f"verify_{order_id}")],
                [CB("Cancel", style="danger", icon=get_button_emoji("cancel"), callback_data="menu_add_balance")]
            ]

            try:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=qr_img, caption=caption_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send QR photo: {e}")
                await query.answer("❌ QR bhej nahi paya, dobara try karo.", show_alert=True)
                return

            try:
                await query.message.delete()
            except Exception:
                pass
            return

        context.user_data["kp_amt"] = current
        display_amt = current if current else "0"
        text = f"""
<blockquote><tg-emoji emoji-id="6010080962883361959">⭐</tg-emoji> ENTER CUSTOM AMOUNT</blockquote>

➡️ <b>Amount: ₹{display_amt} 💵</b>

👑 <b>Use the keypad below to enter amount.</b>
"""
        try:
            await query.message.edit_text(text=text, reply_markup=get_numeric_keypad(), parse_mode="HTML")
        except:
            pass

    elif data.startswith("verify_"):
        order_id = data.split("verify_")[1]
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ Order not found!", show_alert=True)
            return
        
        if order[3] == "completed":
            await query.answer("✅ Already verified!", show_alert=True)
            msg = f"✅ <b>Already Verified!</b>\n₹{order[2]} added to your wallet."
            await query.message.edit_caption(caption=msg, parse_mode="HTML")
            return
        
        await query.answer("⏳ Checking payment...")
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

    elif data.startswith("admin_"):
        if user_id != str(ADMIN_ID):
            await query.answer("❌ You are not authorized!", show_alert=True)
            return

        if data == "admin_panel":
            text = "🛠 <b>ADMIN PANEL</b>\n\nChoose an action below:"
            await query.message.edit_text(text=text, reply_markup=get_admin_panel_keyboard(), parse_mode="HTML")

        elif data == "admin_broadcast":
            context.user_data["awaiting_broadcast"] = True
            text = (
                "📢 <b>Broadcast Mode ON</b>\n\n"
                "Ab jo bhi message bhejoge (text, photo, video, voice, audio, document, sticker — kuch bhi) "
                "wo sabhi users ko bhej diya jaayega.\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_addproduct":
            context.user_data["awaiting_addproduct"] = True
            text = (
                "➕ <b>ADD PRODUCT</b>\n\n"
                "Reply is format mein ek hi message mein:\n"
                "<code>CATEGORY | NAME | PRODUCT_ID | PLAN | PRICE | ANDROID_ID</code>\n\n"
                "Example:\n"
                "<code>ANDROID NON ROOT | BALA MOD PRO | 133 | 1 Day | 150 | 0b9b969bc2e7997b</code>\n\n"
                "(ANDROID_ID optional hai)\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_removeproduct":
            products = db.get_all_products_flat()
            context.user_data["rm_products"] = products
            if not products:
                text = "📦 <b>Koi product nahi hai.</b>"
                keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
                await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            else:
                text = "🗑 <b>REMOVE PRODUCT</b>\n\nJis product ko delete karna hai use dabao:"
                keyboard = []
                for i, (category, name, plan_count) in enumerate(products):
                    label = f"{name} ({category}) — {plan_count} plan(s)"
                    cb = encode_cb("admin_rmprod_select", i)
                    keyboard.append([CB(label, style="danger", icon=get_button_emoji("remove"), callback_data=cb)])
                keyboard.append([CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")])
                await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data.startswith("admin_rmprod_select" + SEP):
            parts = decode_cb(data)
            idx = int(parts[1])
            products = context.user_data.get("rm_products", [])
            if idx >= len(products):
                await query.answer("❌ List purani ho gayi, dobara kholo.", show_alert=True)
                return
            category, name, plan_count = products[idx]
            text = (
                f"⚠️ <b>Confirm Delete</b>\n\n"
                f"📦 <b>Product:</b> {name}\n"
                f"📂 <b>Category:</b> {category}\n"
                f"⏳ <b>Plans:</b> {plan_count}\n\n"
                f"Yeh product aur iske saare plans permanently delete ho jaayenge. Pakka?"
            )
            keyboard = [
                [CB("Yes, Delete", style="danger", icon=get_button_emoji("confirm"), callback_data=encode_cb("admin_rmprod_confirm", idx)),
                 CB("Cancel", style="primary", icon=get_button_emoji("cancel"), callback_data="admin_removeproduct")]
            ]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data.startswith("admin_rmprod_confirm" + SEP):
            parts = decode_cb(data)
            idx = int(parts[1])
            products = context.user_data.get("rm_products", [])
            if idx >= len(products):
                await query.answer("❌ List purani ho gayi, dobara kholo.", show_alert=True)
                return
            category, name, plan_count = products[idx]
            deleted = db.delete_product(category, name)
            if deleted:
                text = f"✅ <b>Deleted!</b>\n\n📦 {name} ({category}) ke {deleted} plan(s) remove ho gaye."
            else:
                text = "❌ Product nahi mila (shayad pehle hi delete ho chuka hai)."
            keyboard = [[CB("Back to Admin Panel", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

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
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

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
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_users":
            users = db.get_recent_users(20)
            if not users:
                text = "👥 <b>No users yet.</b>"
            else:
                text = "👥 <b>RECENT USERS</b> (latest 20)\n\n"
                for uid, uname, bal in users:
                    text += f"🆔 <code>{uid}</code> — @{uname or 'User'} — ₹{bal:.2f}\n"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_panel")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_resellers":
            text = (
                f"👑 <b>RESELLER MANAGEMENT</b>\n\n"
                f"Resellers ko har purchase par <b>{RESELLER_DISCOUNT_PERCENT}% discount</b> milta hai.\n\n"
                f"Choose an action:"
            )
            await query.message.edit_text(text=text, reply_markup=get_reseller_panel_keyboard(), parse_mode="HTML")

        elif data == "admin_addreseller":
            context.user_data["awaiting_addreseller"] = True
            text = (
                "➕ <b>ADD RESELLER</b>\n\n"
                "Reply karo us user ka <b>USER_ID</b> bhej ke.\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_resellers")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_removereseller":
            context.user_data["awaiting_removereseller"] = True
            text = (
                "➖ <b>REMOVE RESELLER</b>\n\n"
                "Reply karo us user ka <b>USER_ID</b> bhej ke jiska reseller status hatana hai.\n\n"
                "Cancel karne ke liye /cancel bhejo."
            )
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_resellers")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

        elif data == "admin_listresellers":
            resellers = db.get_resellers()
            if not resellers:
                text = "👑 <b>Koi reseller nahi hai abhi.</b>"
            else:
                text = f"👑 <b>RESELLERS</b> ({RESELLER_DISCOUNT_PERCENT}% OFF)\n\n"
                for uid, uname, bal in resellers:
                    text += f"🆔 <code>{uid}</code> — @{uname or 'User'} — ₹{bal:.2f}\n"
            keyboard = [[CB("Back", style="danger", icon=get_button_emoji("back"), callback_data="admin_resellers")]]
            await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_referral":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        stats = db.get_referral_stats(user_id)
        text = f"""
<tg-emoji emoji-id="6071009124131280604">⭐</tg-emoji> <b>REFERRAL PROGRAM</b>

Apna link share karo — jab bhi koi naya user is link se aakar deposit karega, tumhe uske deposit ka <b>{REFERRAL_COMMISSION_PERCENT}% profit</b> turant wallet mein milega!

🔗 <b>Your Referral Link:</b>
<code>{ref_link}</code>

👥 <b>Total Referred Users:</b> {stats['total_referred']}
💰 <b>Total Earned:</b> ₹{stats['total_earned']:.2f}
"""
        keyboard = [[CB("Back", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data in ["menu_tutorial", "menu_support", "menu_download"]:
        texts = {
            "menu_tutorial": f"<tg-emoji emoji-id=\"6071126054615913700\">⭐</tg-emoji> <b>Tutorial</b>\n\n1. Add Balance via UPI\n2. Choose Product\n3. Get Key Instantly!\n\n💳 UPI: <code>{RECEIVER_UPI}</code>",
            "menu_support": f"<tg-emoji emoji-id=\"6071264704750162461\">⭐</tg-emoji> <b>Support</b>\n\nContact: @RANOXAURA",
            "menu_download": f"<tg-emoji emoji-id=\"6073116574389113063\">⭐</tg-emoji> <b>Download</b>\n\n<a href='https://t.me/PAIDGROUPRANO'>Get Latest Apk</a>",
        }
        keyboard = [[CB("Back", style="primary", icon=get_button_emoji("back"), callback_data="back_to_menu")]]
        await query.message.edit_text(text=texts[data], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    else:
        logger.warning(f"⚠️ Unknown callback: {data}")
        await query.answer("⚠️ Unknown action", show_alert=True)

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("="*50)
    print("  BOT - BUTTONS PREMIUM, CAPTION NORMAL")
    print("  RANDOM AMOUNT FEATURE ENABLED")
    print("="*50)
    print(f"  UPI: {RECEIVER_UPI}")
    print(f"  Gmail: {GMAIL_USER}")
    print(f"  Min Amount: ₹{MIN_AMOUNT}")
    print("="*50)
    print("  Buttons = Premium Emojis Only")
    print("  Caption = Normal Emojis (as before)")
    print("  Random Amount = Enabled")
    print("="*50)
    
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
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.User(ADMIN_ID) & ~filters.COMMAND, handle_admin_message))
    
    monitor = EmailMonitor(db, app.bot)
    monitor.start()
    
    print(" Bot is running!")
    print(" Buttons: Premium Emojis")
    print(" Caption: Normal Emojis")
    app.run_polling(drop_pending_updates=True)