import os
from dotenv import load_dotenv
from datetime import timezone, timedelta

# Load environment variables
load_dotenv()

# ==========================================
# DISCORD CONFIG
# ==========================================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'YOUR_ORDER_BOT_DISCORD_TOKEN')
ADMIN_ROLE_NAME = os.getenv('ADMIN_ROLE_NAME', 'Admin')
PUBLIC_CHANNEL_ID = int(os.getenv('PUBLIC_CHANNEL_ID', '0'))

# ==========================================
# MIDTRANS CONFIG
# ==========================================
MIDTRANS_SERVER_KEY = os.getenv('MIDTRANS_SERVER_KEY', 'YOUR_MIDTRANS_SERVER_KEY')
MIDTRANS_IS_PRODUCTION = os.getenv('MIDTRANS_IS_PRODUCTION', 'False').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'http://localhost:8001/webhook/midtrans')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8001'))

# ==========================================
# DATABASE CONFIGURATION
# ==========================================
DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'postgresql')  # sqlite or postgresql
DB_FILE = os.getenv('DB_FILE', 'bot_order.db')  # for SQLite
DATABASE_URL = os.getenv('DATABASE_URL', '')  # for PostgreSQL

# Connection pool settings
DB_MAX_CONNECTIONS = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
DB_TIMEOUT = int(os.getenv('DB_TIMEOUT', '30'))
DB_MAX_RETRY_ATTEMPTS = int(os.getenv('DB_MAX_RETRY_ATTEMPTS', '5'))
DB_RETRY_DELAY = float(os.getenv('DB_RETRY_DELAY', '0.1'))

# ==========================================
# PACKAGE PRICING
# ==========================================
PACKAGE_PRICES = {
    '1_code': int(os.getenv('PRICE_1_CODE', '15000')),
    '5_codes': int(os.getenv('PRICE_5_CODES', '70000')),
    '10_codes': int(os.getenv('PRICE_10_CODES', '130000')),
    '25_codes': int(os.getenv('PRICE_25_CODES', '300000')),
    '50_codes': int(os.getenv('PRICE_50_CODES', '550000')),
}

# Package configurations
PACKAGE_CONFIG = {
    '1_code': {'quantity': 1, 'price': PACKAGE_PRICES['1_code'], 'label': '1 Code'},
    '5_codes': {'quantity': 5, 'price': PACKAGE_PRICES['5_codes'], 'label': '5 Codes'},
    '10_codes': {'quantity': 10, 'price': PACKAGE_PRICES['10_codes'], 'label': '10 Codes'},
    '25_codes': {'quantity': 25, 'price': PACKAGE_PRICES['25_codes'], 'label': '25 Codes'},
    '50_codes': {'quantity': 50, 'price': PACKAGE_PRICES['50_codes'], 'label': '50 Codes'},
}

# ==========================================
# ORDER SETTINGS
# ==========================================
MAX_CODES_PER_ORDER = int(os.getenv('MAX_CODES_PER_ORDER', '50'))
MIN_ORDER_AMOUNT = int(os.getenv('MIN_ORDER_AMOUNT', '1'))
AUTO_DELIVERY_ENABLED = os.getenv('AUTO_DELIVERY_ENABLED', 'True').lower() == 'true'
MANUAL_APPROVAL_REQUIRED = os.getenv('MANUAL_APPROVAL_REQUIRED', 'False').lower() == 'true'

# ==========================================
# STOCK MANAGEMENT
# ==========================================
LOW_STOCK_THRESHOLD = int(os.getenv('LOW_STOCK_THRESHOLD', '10'))
STOCK_ALERT_ENABLED = os.getenv('STOCK_ALERT_ENABLED', 'True').lower() == 'true'
STOCK_ADMIN_USER_IDS = [
    int(uid.strip()) for uid in os.getenv('STOCK_ADMIN_USER_IDS', '').split(',') if uid.strip()
]

# Code encryption
ENCRYPT_STOCK_CODES = os.getenv('ENCRYPT_STOCK_CODES', 'True').lower() == 'true'
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'default-encryption-key-change-me!')

# ==========================================
# DELIVERY SETTINGS
# ==========================================
DELIVERY_METHOD = os.getenv('DELIVERY_METHOD', 'dm')  # dm, channel, file
DELIVERY_RETRY_ATTEMPTS = int(os.getenv('DELIVERY_RETRY_ATTEMPTS', '3'))
DELIVERY_TIMEOUT = int(os.getenv('DELIVERY_TIMEOUT', '300'))

# ==========================================
# AUTO-CLOSE CHANNEL
# ==========================================
AUTO_CLOSE_AFTER_COMPLETION = int(os.getenv('AUTO_CLOSE_AFTER_COMPLETION', '7200'))
AUTO_CLOSE_AFTER_INACTIVITY = int(os.getenv('AUTO_CLOSE_AFTER_INACTIVITY', '7200'))
AUTO_CLOSE_WARNING_BEFORE = int(os.getenv('AUTO_CLOSE_WARNING_BEFORE', '600'))
AUTO_CLOSE_CHECK_INTERVAL = int(os.getenv('AUTO_CLOSE_CHECK_INTERVAL', '300'))

# ==========================================
# FEATURES
# ==========================================
ENABLE_ORDER_TRACKING = os.getenv('ENABLE_ORDER_TRACKING', 'True').lower() == 'true'
ENABLE_ORDER_CANCELLATION = os.getenv('ENABLE_ORDER_CANCELLATION', 'True').lower() == 'true'
ENABLE_REFUND = os.getenv('ENABLE_REFUND', 'True').lower() == 'true'
ENABLE_STOCK_NOTIFICATIONS = os.getenv('ENABLE_STOCK_NOTIFICATIONS', 'True').lower() == 'true'

# ==========================================
# LOGGING
# ==========================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'True').lower() == 'true'
LOG_FILE = os.getenv('LOG_FILE', 'bot_order.log')
LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', '10485760'))
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))

# ==========================================
# SECURITY
# ==========================================
ENABLE_SENSITIVE_DATA_MASKING = os.getenv('ENABLE_SENSITIVE_DATA_MASKING', 'True').lower() == 'true'
MASK_SHOW_CHARACTERS = int(os.getenv('MASK_SHOW_CHARACTERS', '4'))

# ==========================================
# RATE LIMITING
# ==========================================
MAX_ORDERS_PER_USER_PER_DAY = int(os.getenv('MAX_ORDERS_PER_USER_PER_DAY', '10'))
ORDER_COOLDOWN_SECONDS = int(os.getenv('ORDER_COOLDOWN_SECONDS', '60'))

# ==========================================
# NOTIFICATIONS
# ==========================================
NOTIFY_ADMIN_ON_ORDER = os.getenv('NOTIFY_ADMIN_ON_ORDER', 'True').lower() == 'true'
NOTIFY_USER_ON_DELIVERY = os.getenv('NOTIFY_USER_ON_DELIVERY', 'True').lower() == 'true'
NOTIFY_USER_ON_LOW_BALANCE = os.getenv('NOTIFY_USER_ON_LOW_BALANCE', 'True').lower() == 'true'

# ==========================================
# DEFAULT VALUES
# ==========================================
DEFAULT_ORDER_STATUS = os.getenv('DEFAULT_ORDER_STATUS', 'pending')
DEFAULT_DELIVERY_FORMAT = os.getenv('DEFAULT_DELIVERY_FORMAT', 'text')

# ==========================================
# TIMEZONE (WIB - Indonesia)
# ==========================================
WIB = timezone(timedelta(hours=7))

def get_wib_time():
    """Get current datetime in WIB timezone"""
    from datetime import datetime
    return datetime.now(WIB)

def format_wib_datetime(dt=None, include_seconds=False):
    """Format datetime as WIB string"""
    from datetime import datetime
    if dt is None:
        dt = get_wib_time()
    
    if include_seconds:
        return dt.strftime('%d/%m/%Y %H:%M:%S WIB')
    else:
        return dt.strftime('%d/%m/%Y %H:%M WIB')

def format_wib_time_only(dt=None):
    """Format time only (HH:MM WIB)"""
    from datetime import datetime
    if dt is None:
        dt = get_wib_time()
    return dt.strftime('%H:%M WIB')

# ==========================================
# VALIDATION FUNCTIONS
# ==========================================

def validate_config():
    """Validate configuration"""
    errors = []
    warnings = []

    # Check Discord Token
    if DISCORD_TOKEN == 'YOUR_ORDER_BOT_DISCORD_TOKEN':
        errors.append("❌ DISCORD_TOKEN belum di-set di .env")

    # Check Midtrans Key
    if MIDTRANS_SERVER_KEY == 'YOUR_MIDTRANS_SERVER_KEY':
        errors.append("❌ MIDTRANS_SERVER_KEY belum di-set di .env")

    # Check database configuration
    if DATABASE_TYPE == 'postgresql' and not DATABASE_URL:
        errors.append("❌ DATABASE_URL required for PostgreSQL")
    
    if DATABASE_TYPE not in ['sqlite', 'postgresql']:
        errors.append("❌ DATABASE_TYPE must be 'sqlite' or 'postgresql'")

    # Check Public Channel ID
    if PUBLIC_CHANNEL_ID == 0:
        errors.append("⚠️ PUBLIC_CHANNEL_ID tidak valid")

    # Check prices
    for package, price in PACKAGE_PRICES.items():
        if price <= 0:
            warnings.append(f"⚠️ Invalid price for {package}: {price}")

    # Check encryption key
    if ENCRYPT_STOCK_CODES and len(ENCRYPTION_KEY) < 16:
        warnings.append("⚠️ ENCRYPTION_KEY too short (min 16 chars)")

    # Print errors and warnings
    if errors or warnings:
        print("\n" + "="*50)
        print("⚠️ CONFIGURATION:")
        print("="*50)
        
        for error in errors:
            print(error)
        
        for warning in warnings:
            print(warning)
        
        print("="*50 + "\n")

        if any("❌" in e for e in errors):
            print("🛑 Bot tidak bisa jalan! Perbaiki .env terlebih dahulu.\n")
            return False

    return True

def print_config():
    """Print configuration on startup"""
    print("\n" + "="*50)
    print("⚙️ ORDER BOT CONFIGURATION")
    print("="*50)
    
    # Discord Config
    print(f"\n📱 DISCORD:")
    print(f"  Token: {'✅ Set' if DISCORD_TOKEN != 'YOUR_ORDER_BOT_DISCORD_TOKEN' else '❌ Not Set'}")
    print(f"  Admin Role: {ADMIN_ROLE_NAME}")
    print(f"  Public Channel ID: {PUBLIC_CHANNEL_ID}")
    
    # Database Config
    print(f"\n💾 DATABASE:")
    print(f"  Type: {DATABASE_TYPE.upper()}")
    if DATABASE_TYPE == 'postgresql':
        db_host = DATABASE_URL.split('@')[-1].split('/')[0] if DATABASE_URL else 'Not Set'
        print(f"  Host: {db_host}")
    else:
        print(f"  File: {DB_FILE}")
    print(f"  Max Connections: {DB_MAX_CONNECTIONS}")
    
    # Midtrans Config
    print(f"\n💳 MIDTRANS:")
    print(f"  Server Key: {'✅ Set' if MIDTRANS_SERVER_KEY != 'YOUR_MIDTRANS_SERVER_KEY' else '❌ Not Set'}")
    print(f"  Environment: {'🔴 PRODUCTION' if MIDTRANS_IS_PRODUCTION else '🟡 SANDBOX'}")
    print(f"  Webhook Port: {WEBHOOK_PORT}")
    
    # Package Prices
    print(f"\n💰 PACKAGES:")
    for key, config in PACKAGE_CONFIG.items():
        qty = config['quantity']
        price = config['price']
        per_code = price // qty
        print(f"  {config['label']:10} - Rp {price:>8,} (Rp {per_code:>6,}/code)")
    
    # Order Settings
    print(f"\n📦 ORDER SETTINGS:")
    print(f"  Max Codes: {MAX_CODES_PER_ORDER}")
    print(f"  Auto Delivery: {'✅ Enabled' if AUTO_DELIVERY_ENABLED else '❌ Disabled'}")
    print(f"  Manual Approval: {'✅ Required' if MANUAL_APPROVAL_REQUIRED else '❌ Not Required'}")
    
    # Stock Settings
    print(f"\n📊 STOCK:")
    print(f"  Low Stock Alert: {LOW_STOCK_THRESHOLD} codes")
    print(f"  Encryption: {'✅ Enabled' if ENCRYPT_STOCK_CODES else '❌ Disabled'}")
    print(f"  Admin Alerts: {'✅ Enabled' if STOCK_ALERT_ENABLED else '❌ Disabled'}")
    
    # Features
    print(f"\n⚙️ FEATURES:")
    print(f"  Order Tracking: {'✅' if ENABLE_ORDER_TRACKING else '❌'}")
    print(f"  Cancellation: {'✅' if ENABLE_ORDER_CANCELLATION else '❌'}")
    print(f"  Refund: {'✅' if ENABLE_REFUND else '❌'}")
    
    # Logging
    print(f"\n📝 LOGGING:")
    print(f"  Level: {LOG_LEVEL}")
    print(f"  To File: {'✅ Enabled' if LOG_TO_FILE else '❌ Disabled'}")
    if LOG_TO_FILE:
        print(f"  File: logs/{LOG_FILE}")
    
    print("="*50 + "\n")

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_package_info(package_key):
    """Get package information"""
    return PACKAGE_CONFIG.get(package_key)

def calculate_price(quantity):
    """Calculate price for given quantity"""
    # Find best matching package
    for key, config in sorted(PACKAGE_CONFIG.items(), key=lambda x: x[1]['quantity'], reverse=True):
        if quantity >= config['quantity']:
            return config['price']
    
    # Default to 1 code price
    return PACKAGE_PRICES['1_code'] * quantity

def mask_sensitive(text, show=None):
    """Mask sensitive data"""
    if not ENABLE_SENSITIVE_DATA_MASKING:
        return text
    
    if show is None:
        show = MASK_SHOW_CHARACTERS
    
    if len(text) <= show * 2:
        return text
    
    return f"{text[:show]}****{text[-show:]}"
