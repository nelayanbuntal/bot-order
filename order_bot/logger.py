"""
Logger Module
=============
Comprehensive logging system for Discord Bot Order
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
import traceback
import config

# Create logs directory if not exists
os.makedirs('logs', exist_ok=True)

# Configure logger
logger = logging.getLogger('OrderBot')
logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

# Prevent duplicate handlers
if not logger.handlers:
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler (if enabled)
    if config.LOG_TO_FILE:
        file_handler = RotatingFileHandler(
            f'logs/{config.LOG_FILE}',
            maxBytes=config.LOG_MAX_SIZE,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def log_info(message, **kwargs):
    """Log info message with optional context"""
    context = _format_context(kwargs)
    logger.info(f"{message}{context}")

def log_warning(message, **kwargs):
    """Log warning message with optional context"""
    context = _format_context(kwargs)
    logger.warning(f"{message}{context}")

def log_error(message, **kwargs):
    """Log error message with optional context"""
    context = _format_context(kwargs)
    logger.error(f"{message}{context}")

def log_debug(message, **kwargs):
    """Log debug message with optional context"""
    context = _format_context(kwargs)
    logger.debug(f"{message}{context}")

def log_critical(message, **kwargs):
    """Log critical message with optional context"""
    context = _format_context(kwargs)
    logger.critical(f"{message}{context}")

def _format_context(kwargs):
    """Format context dict into readable string"""
    if not kwargs:
        return ""
    
    # Apply masking if enabled
    if config.ENABLE_SENSITIVE_DATA_MASKING:
        for key in ['code', 'token', 'key', 'password', 'secret']:
            if key in kwargs:
                kwargs[key] = config.mask_sensitive(str(kwargs[key]))
    
    context_parts = [f"{k}={v}" for k, v in kwargs.items()]
    return f" | {', '.join(context_parts)}"

# ==========================================
# ERROR LOGGING WITH TRACEBACK
# ==========================================

def log_error_with_context(exception, context, **kwargs):
    """
    Log error with full context and traceback
    
    Args:
        exception: The exception object
        context: String describing where error occurred
        **kwargs: Additional context information
    """
    error_msg = f"Error in {context}: {str(exception)}"
    
    # Add context
    context_str = _format_context(kwargs)
    if context_str:
        error_msg += context_str
    
    # Log error
    logger.error(error_msg)
    
    # Log traceback at debug level
    if logger.level <= logging.DEBUG:
        logger.debug(f"Traceback:\n{traceback.format_exc()}")

# ==========================================
# SPECIALIZED LOGGING
# ==========================================

def log_order_created(order_number, user_id, package_type, total_price):
    """Log order creation"""
    logger.info(
        f"📦 Order Created",
        extra={
            'order_number': order_number,
            'user_id': user_id,
            'package': package_type,
            'price': f"Rp {total_price:,}"
        }
    )
    print(f"📦 Order Created: {order_number} | User: {user_id} | {package_type} | Rp {total_price:,}")

def log_order_completed(order_number, user_id, code_quantity):
    """Log order completion"""
    logger.info(
        f"✅ Order Completed",
        extra={
            'order_number': order_number,
            'user_id': user_id,
            'quantity': code_quantity
        }
    )
    print(f"✅ Order Completed: {order_number} | User: {user_id} | {code_quantity} codes delivered")

def log_order_failed(order_number, user_id, reason):
    """Log order failure"""
    logger.error(
        f"❌ Order Failed",
        extra={
            'order_number': order_number,
            'user_id': user_id,
            'reason': reason
        }
    )
    print(f"❌ Order Failed: {order_number} | User: {user_id} | Reason: {reason}")

def log_payment_received(order_id, user_id, amount, payment_type):
    """Log payment received"""
    logger.info(
        f"💰 Payment Received",
        extra={
            'order_id': order_id,
            'user_id': user_id,
            'amount': f"Rp {amount:,}",
            'type': payment_type
        }
    )
    print(f"💰 Payment Received: {order_id} | User: {user_id} | Rp {amount:,} ({payment_type})")

def log_balance_updated(user_id, old_balance, new_balance, action):
    """Log balance update"""
    diff = new_balance - old_balance
    symbol = "+" if diff > 0 else ""
    logger.info(
        f"💳 Balance Updated",
        extra={
            'user_id': user_id,
            'action': action,
            'old': f"Rp {old_balance:,}",
            'new': f"Rp {new_balance:,}",
            'diff': f"{symbol}Rp {abs(diff):,}"
        }
    )
    print(f"💳 Balance Updated: User {user_id} | {action} | {symbol}Rp {abs(diff):,} | New: Rp {new_balance:,}")

def log_stock_added(admin_id, count, code_type='redfinger'):
    """Log stock addition"""
    logger.info(
        f"📥 Stock Added",
        extra={
            'admin_id': admin_id,
            'count': count,
            'type': code_type
        }
    )
    print(f"📥 Stock Added: {count} {code_type} codes by Admin {admin_id}")

def log_stock_alert(code_type, available_count, threshold):
    """Log low stock alert"""
    logger.warning(
        f"⚠️ Low Stock Alert",
        extra={
            'type': code_type,
            'available': available_count,
            'threshold': threshold
        }
    )
    print(f"⚠️ Low Stock Alert: {code_type} - Only {available_count} codes left (threshold: {threshold})")

def log_delivery_success(order_number, user_id, method, code_count):
    """Log successful delivery"""
    logger.info(
        f"📮 Delivery Success",
        extra={
            'order_number': order_number,
            'user_id': user_id,
            'method': method,
            'count': code_count
        }
    )
    print(f"📮 Delivery Success: {order_number} | {code_count} codes via {method} to User {user_id}")

def log_delivery_failed(order_number, user_id, method, error):
    """Log delivery failure"""
    logger.error(
        f"📮 Delivery Failed",
        extra={
            'order_number': order_number,
            'user_id': user_id,
            'method': method,
            'error': error
        }
    )
    print(f"📮 Delivery Failed: {order_number} | Method: {method} | Error: {error}")

def log_webhook_received(order_id, status, payment_type):
    """Log webhook notification"""
    logger.info(
        f"🔔 Webhook Received",
        extra={
            'order_id': order_id,
            'status': status,
            'payment_type': payment_type
        }
    )
    print(f"🔔 Webhook: {order_id} | Status: {status} | Type: {payment_type}")

def log_admin_action(admin_id, action, details=""):
    """Log admin action"""
    logger.info(
        f"👨‍💼 Admin Action",
        extra={
            'admin_id': admin_id,
            'action': action,
            'details': details
        }
    )
    print(f"👨‍💼 Admin: {admin_id} | Action: {action} | {details}")

def log_bot_startup():
    """Log bot startup"""
    logger.info("="*50)
    logger.info("🚀 Discord Order Bot Starting...")
    logger.info(f"Environment: {'🔴 PRODUCTION' if config.MIDTRANS_IS_PRODUCTION else '🟡 SANDBOX'}")
    logger.info(f"Database: {config.DATABASE_TYPE.upper()}")
    logger.info(f"Webhook Port: {config.WEBHOOK_PORT}")
    logger.info(f"Auto Delivery: {'✅ Enabled' if config.AUTO_DELIVERY_ENABLED else '❌ Disabled'}")
    logger.info("="*50)
    print("\n" + "="*50)
    print("🚀 Discord Order Bot Starting...")
    print(f"Environment: {'🔴 PRODUCTION' if config.MIDTRANS_IS_PRODUCTION else '🟡 SANDBOX'}")
    print(f"Database: {config.DATABASE_TYPE.upper()}")
    print(f"Webhook Port: {config.WEBHOOK_PORT}")
    print(f"Auto Delivery: {'✅ Enabled' if config.AUTO_DELIVERY_ENABLED else '❌ Disabled'}")
    print("="*50 + "\n")

def log_bot_ready(bot_user):
    """Log bot ready"""
    logger.info(f"✅ Bot Ready: {bot_user}")
    print(f"✅ Bot Ready: {bot_user}")

def log_bot_shutdown():
    """Log bot shutdown"""
    logger.info("="*50)
    logger.info("🛑 Discord Order Bot Shutting Down...")
    logger.info("="*50)
    print("\n" + "="*50)
    print("🛑 Discord Order Bot Shutting Down...")
    print("="*50 + "\n")

# ==========================================
# PERFORMANCE LOGGING
# ==========================================

class PerformanceLogger:
    """Context manager for logging execution time"""
    
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is not None:
            logger.error(f"⏱️ {self.operation_name} failed after {duration:.2f}s")
        else:
            if duration > 5:
                logger.warning(f"⏱️ {self.operation_name} took {duration:.2f}s (slow)")
            else:
                logger.debug(f"⏱️ {self.operation_name} took {duration:.2f}s")

# Usage example:
# with PerformanceLogger("Order Processing"):
#     process_order()

# ==========================================
# STATISTICS LOGGING
# ==========================================

def log_daily_stats(stats):
    """Log daily statistics"""
    logger.info("="*50)
    logger.info("📊 Daily Statistics")
    logger.info(f"Total Orders: {stats.get('total_orders', 0)}")
    logger.info(f"Completed: {stats.get('completed_orders', 0)}")
    logger.info(f"Revenue: Rp {stats.get('total_revenue', 0):,}")
    logger.info(f"Available Stock: {stats.get('available_stock', 0)}")
    logger.info("="*50)

# ==========================================
# DEBUG HELPERS
# ==========================================

def debug_log_dict(title, data_dict):
    """Log dictionary data for debugging"""
    if logger.level <= logging.DEBUG:
        logger.debug(f"\n{title}:")
        for key, value in data_dict.items():
            logger.debug(f"  {key}: {value}")

def debug_log_list(title, data_list):
    """Log list data for debugging"""
    if logger.level <= logging.DEBUG:
        logger.debug(f"\n{title} ({len(data_list)} items):")
        for idx, item in enumerate(data_list, 1):
            logger.debug(f"  {idx}. {item}")

# ==========================================
# EXPORT
# ==========================================

__all__ = [
    'logger',
    'log_info',
    'log_warning',
    'log_error',
    'log_debug',
    'log_critical',
    'log_error_with_context',
    'log_order_created',
    'log_order_completed',
    'log_order_failed',
    'log_payment_received',
    'log_balance_updated',
    'log_stock_added',
    'log_stock_alert',
    'log_delivery_success',
    'log_delivery_failed',
    'log_webhook_received',
    'log_admin_action',
    'log_bot_startup',
    'log_bot_ready',
    'log_bot_shutdown',
    'log_daily_stats',
    'PerformanceLogger',
    'debug_log_dict',
    'debug_log_list',
]
