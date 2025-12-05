"""
Enhanced Database Module with Shared Database Support
======================================================
Supports both PostgreSQL (shared) and SQLite (standalone)
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime
import config

# Try import PostgreSQL adapter
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("⚠️ psycopg2 not installed. PostgreSQL support disabled.")

# Import logger
try:
    from logger import logger, log_error_with_context
    try:
        from logger import log_balance_updated
    except ImportError:
        def log_balance_updated(user_id, old_bal, new_bal, reason): 
            logger.info(f"Balance updated: User {user_id} | {old_bal} → {new_bal} | Reason: {reason}")
except ImportError:
    class FallbackLogger:
        def info(self, msg, **kwargs): print(f"ℹ️ {msg}")
        def warning(self, msg, **kwargs): print(f"⚠️ {msg}")
        def error(self, msg, **kwargs): print(f"❌ {msg}")
        def debug(self, msg, **kwargs): pass
    logger = FallbackLogger()
    def log_error_with_context(e, ctx, **kwargs): print(f"❌ Error in {ctx}: {e}")
    def log_balance_updated(user_id, old_bal, new_bal, reason): 
        print(f"ℹ️ Balance updated: User {user_id} | {old_bal} → {new_bal} | Reason: {reason}")

# ==========================================
# GLOBAL VARIABLES
# ==========================================
DATABASE_TYPE = config.DATABASE_TYPE
_pg_pool = None
_sqlite_pool = None

# ==========================================
# CONNECTION POOL (PostgreSQL)
# ==========================================

def get_pg_pool():
    """Get or create PostgreSQL connection pool"""
    global _pg_pool
    
    if _pg_pool is None and DATABASE_TYPE == 'postgresql':
        if not POSTGRES_AVAILABLE:
            raise ImportError("psycopg2 not installed. Install with: pip install psycopg2-binary")
        
        if not config.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured for PostgreSQL")
        
        try:
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=config.DB_MAX_CONNECTIONS,
                dsn=config.DATABASE_URL
            )
            logger.info("✅ PostgreSQL connection pool created")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL pool: {e}")
            raise
    
    return _pg_pool

# ==========================================
# CONNECTION POOL (SQLite)
# ==========================================

class SQLiteConnectionPool:
    """Thread-safe connection pool for SQLite"""
    
    def __init__(self, database, max_connections=10):
        self.database = database
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()
        self._local = threading.local()
    
    def get_connection(self):
        """Get a connection from pool"""
        if hasattr(self._local, 'conn') and self._local.conn:
            return self._local.conn
        
        with self.lock:
            if self.connections:
                conn = self.connections.pop()
            else:
                conn = sqlite3.connect(
                    self.database,
                    timeout=config.DB_TIMEOUT,
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
            
            self._local.conn = conn
            return conn
    
    def return_connection(self, conn):
        """Return connection to pool"""
        if hasattr(self._local, 'conn'):
            self._local.conn = None
        
        with self.lock:
            if len(self.connections) < self.max_connections:
                self.connections.append(conn)
            else:
                conn.close()
    
    def close_all(self):
        """Close all connections"""
        with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()

def get_sqlite_pool():
    """Get or create SQLite connection pool"""
    global _sqlite_pool
    
    if _sqlite_pool is None and DATABASE_TYPE == 'sqlite':
        db_path = config.DATABASE_URL.replace('sqlite:///', '')
        _sqlite_pool = SQLiteConnectionPool(db_path, max_connections=10)
        logger.info(f"✅ SQLite connection pool created: {db_path}")
    
    return _sqlite_pool

# ==========================================
# CONNECTION MANAGER
# ==========================================

@contextmanager
def get_db_connection(commit=True):
    """
    Get database connection (PostgreSQL or SQLite)
    
    Args:
        commit: Auto-commit on success (default: True)
    
    Yields:
        Database connection
    """
    conn = None
    try:
        if DATABASE_TYPE == 'postgresql':
            pool = get_pg_pool()
            conn = pool.getconn()
        else:
            pool = get_sqlite_pool()
            conn = pool.get_connection()
        
        yield conn
        
        if commit:
            conn.commit()
    
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    
    finally:
        if conn:
            if DATABASE_TYPE == 'postgresql':
                pool = get_pg_pool()
                pool.putconn(conn)
            else:
                pool = get_sqlite_pool()
                pool.return_connection(conn)

def dict_cursor(conn):
    """Get cursor that returns dict-like rows"""
    if DATABASE_TYPE == 'postgresql':
        return conn.cursor(cursor_factory=RealDictCursor)
    else:
        # SQLite already returns Row objects (dict-like)
        return conn.cursor()

# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def init_database():
    """Initialize database tables"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if DATABASE_TYPE == 'postgresql':
                # PostgreSQL - tables should exist from shared_db_schema.sql
                # Just verify they exist
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('users', 'orders', 'stock_codes', 'topups')
                """)
                tables = cursor.fetchall()
                
                if len(tables) < 4:
                    logger.warning("⚠️ Some tables missing. Please run shared_db_schema.sql")
                else:
                    logger.info("✅ PostgreSQL tables verified")
            
            else:
                # SQLite - create tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        balance INTEGER DEFAULT 0,
                        total_orders INTEGER DEFAULT 0,
                        total_spent INTEGER DEFAULT 0,
                        total_topup INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_order_at TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_number TEXT UNIQUE NOT NULL,
                        user_id INTEGER NOT NULL,
                        package_type TEXT NOT NULL,
                        code_quantity INTEGER NOT NULL,
                        total_price INTEGER NOT NULL,
                        payment_method TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        delivery_method TEXT,
                        delivery_status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS stock_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code_type TEXT NOT NULL,
                        code_value TEXT NOT NULL UNIQUE,
                        status TEXT DEFAULT 'available',
                        reserved_for_order INTEGER,
                        reserved_at TIMESTAMP,
                        used_at TIMESTAMP,
                        added_by INTEGER,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS topups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        amount INTEGER NOT NULL,
                        order_id TEXT UNIQUE NOT NULL,
                        payment_type TEXT,
                        transaction_id TEXT,
                        status TEXT DEFAULT 'pending',
                        bot_source TEXT DEFAULT 'order_bot',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_status ON stock_codes(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_topups_user ON topups(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_topups_order ON topups(order_id)")
                
                logger.info("✅ SQLite tables created")
        
        logger.info("Database initialized")
        return True
    
    except Exception as e:
        log_error_with_context(e, "init_database")
        raise

# ==========================================
# USER FUNCTIONS
# ==========================================

def ensure_user_exists(user_id):
    """Ensure user exists in database"""
    try:
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO users (user_id, balance)
                    VALUES (%s, 0)
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id,))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, balance)
                    VALUES (?, 0)
                """, (user_id,))
        
        return True
    except Exception as e:
        log_error_with_context(e, "ensure_user_exists", user_id=user_id)
        return False

def get_balance(user_id):
    """Get user balance"""
    try:
        ensure_user_exists(user_id)
        
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            else:
                cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            
            row = cursor.fetchone()
            
            if row:
                return row['balance'] if isinstance(row, dict) else row[0]
            return 0
    
    except Exception as e:
        log_error_with_context(e, "get_balance", user_id=user_id)
        return 0

def add_balance(user_id, amount):
    """
    Add balance to user account
    
    Args:
        user_id: Discord user ID
        amount: Amount to add (positive integer)
    
    Returns:
        int: New balance or None if error
    """
    try:
        ensure_user_exists(user_id)
        
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            # Get current balance
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            else:
                cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            
            row = cursor.fetchone()
            old_balance = row['balance'] if isinstance(row, dict) else row[0]
            new_balance = old_balance + amount
            
            # Update balance and total_topup
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users 
                    SET balance = %s, 
                        total_topup = total_topup + %s
                    WHERE user_id = %s
                """, (new_balance, amount, user_id))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET balance = ?, 
                        total_topup = total_topup + ?
                    WHERE user_id = ?
                """, (new_balance, amount, user_id))
            
            # Log balance change
            log_balance_updated(user_id, old_balance, new_balance, "topup")
            
            return new_balance
    
    except Exception as e:
        log_error_with_context(e, "add_balance", user_id=user_id, amount=amount)
        return None

def deduct_balance(user_id, amount):
    """
    Deduct balance from user account
    
    Args:
        user_id: Discord user ID
        amount: Amount to deduct (positive integer)
    
    Returns:
        int: New balance or None if insufficient funds
    """
    try:
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            # Get current balance
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("SELECT balance FROM users WHERE user_id = %s FOR UPDATE", (user_id,))
            else:
                cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            
            row = cursor.fetchone()
            old_balance = row['balance'] if isinstance(row, dict) else row[0]
            
            if old_balance < amount:
                return None  # Insufficient funds
            
            new_balance = old_balance - amount
            
            # Update balance and stats
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users 
                    SET balance = %s,
                        total_orders = total_orders + 1,
                        total_spent = total_spent + %s,
                        last_order_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (new_balance, amount, user_id))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET balance = ?,
                        total_orders = total_orders + 1,
                        total_spent = total_spent + ?,
                        last_order_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (new_balance, amount, user_id))
            
            # Log balance change
            log_balance_updated(user_id, old_balance, new_balance, "order")
            
            return new_balance
    
    except Exception as e:
        log_error_with_context(e, "deduct_balance", user_id=user_id, amount=amount)
        return None

def get_user_stats(user_id):
    """Get user statistics"""
    try:
        ensure_user_exists(user_id)
        
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT balance, total_orders, total_spent, total_topup
                    FROM users WHERE user_id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT balance, total_orders, total_spent, total_topup
                    FROM users WHERE user_id = ?
                """, (user_id,))
            
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict):
                    return row
                else:
                    return {
                        'balance': row[0],
                        'total_orders': row[1],
                        'total_spent': row[2],
                        'total_topup': row[3]
                    }
            
            return {
                'balance': 0,
                'total_orders': 0,
                'total_spent': 0,
                'total_topup': 0
            }
    
    except Exception as e:
        log_error_with_context(e, "get_user_stats", user_id=user_id)
        return {'balance': 0, 'total_orders': 0, 'total_spent': 0, 'total_topup': 0}

# ==========================================
# TOPUP FUNCTIONS
# ==========================================

def create_topup(user_id, amount, order_id, payment_type='qris', transaction_id=None):
    """
    Create topup record
    
    Args:
        user_id: Discord user ID
        amount: Topup amount in Rupiah
        order_id: Unique order ID from payment gateway
        payment_type: Payment method (qris, gopay, bank_transfer, etc.)
        transaction_id: Transaction ID from Midtrans
    
    Returns:
        int: Topup ID or None if error
    """
    try:
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO topups (
                        user_id, amount, order_id, status, 
                        bot_source, payment_type, transaction_id
                    )
                    VALUES (%s, %s, %s, 'pending', 'order_bot', %s, %s)
                    RETURNING id
                """, (user_id, amount, order_id, payment_type, transaction_id))
            else:
                cursor.execute("""
                    INSERT INTO topups (
                        user_id, amount, order_id, status, 
                        bot_source, payment_type, transaction_id
                    )
                    VALUES (?, ?, ?, 'pending', 'order_bot', ?, ?)
                """, (user_id, amount, order_id, payment_type, transaction_id))
            
            row = cursor.fetchone()
            topup_id = row['id'] if isinstance(row, dict) else row[0]
            
            logger.info(f"Topup created: ID={topup_id}, User={user_id}, Amount=Rp {amount:,}")
            return topup_id
            
    except Exception as e:
        logger.error(f"Error creating topup: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_topup_status(order_id, status):
    """Update topup status"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE topups 
                    SET status = %s,
                        completed_at = CASE WHEN %s = 'success' THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE order_id = %s
                """, (status, status, order_id))
            else:
                cursor.execute("""
                    UPDATE topups 
                    SET status = ?,
                        completed_at = CASE WHEN ? = 'success' THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE order_id = ?
                """, (status, status, order_id))
            
            return True
    
    except Exception as e:
        log_error_with_context(e, "update_topup_status", order_id=order_id)
        return False

def get_topup_by_order_id(order_id):
    """Get topup record by order_id"""
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM topups WHERE order_id = %s", (order_id,))
            else:
                cursor.execute("SELECT * FROM topups WHERE order_id = ?", (order_id,))
            
            return cursor.fetchone()
    
    except Exception as e:
        log_error_with_context(e, "get_topup_by_order_id", order_id=order_id)
        return None

# ==========================================
# ORDER FUNCTIONS
# ==========================================

def create_order(order_data):
    """Create new order"""
    try:
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO orders (
                        order_number, user_id, package_type, code_quantity,
                        total_price, payment_method, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    order_data['order_number'],
                    order_data['user_id'],
                    order_data['package_type'],
                    order_data['code_quantity'],
                    order_data['total_price'],
                    order_data['payment_method'],
                    order_data.get('status', 'pending')
                ))
            else:
                cursor.execute("""
                    INSERT INTO orders (
                        order_number, user_id, package_type, code_quantity,
                        total_price, payment_method, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_data['order_number'],
                    order_data['user_id'],
                    order_data['package_type'],
                    order_data['code_quantity'],
                    order_data['total_price'],
                    order_data['payment_method'],
                    order_data.get('status', 'pending')
                ))
            
            row = cursor.fetchone()
            return row['id'] if isinstance(row, dict) else row[0]
    
    except Exception as e:
        log_error_with_context(e, "create_order", order_data=order_data)
        return None

def get_order_by_id(order_id):
    """Get order by ID"""
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            else:
                cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            
            return cursor.fetchone()
    
    except Exception as e:
        log_error_with_context(e, "get_order_by_id", order_id=order_id)
        return None

def get_order_by_number(order_number):
    """Get order by order number"""
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM orders WHERE order_number = %s", (order_number,))
            else:
                cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
            
            return cursor.fetchone()
    
    except Exception as e:
        log_error_with_context(e, "get_order_by_number", order_number=order_number)
        return None

def get_user_orders(user_id, limit=10):
    """Get user's recent orders"""
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT * FROM orders 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM orders 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (user_id, limit))
            
            return cursor.fetchall()
    
    except Exception as e:
        log_error_with_context(e, "get_user_orders", user_id=user_id)
        return []

def update_order_status(order_id, status):
    """Update order status"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE orders 
                    SET status = %s,
                        completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE id = %s
                """, (status, status, order_id))
            else:
                cursor.execute("""
                    UPDATE orders 
                    SET status = ?,
                        completed_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE id = ?
                """, (status, status, order_id))
            
            return True
    
    except Exception as e:
        log_error_with_context(e, "update_order_status", order_id=order_id)
        return False

# ==========================================
# STOCK FUNCTIONS
# ==========================================

def add_stock_code(code_type, code_value, added_by=None):
    """Add single stock code"""
    try:
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO stock_codes (code_type, code_value, status, added_by)
                    VALUES (%s, %s, 'available', %s)
                    ON CONFLICT (code_value) DO NOTHING
                    RETURNING id
                """, (code_type, code_value, added_by))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO stock_codes (code_type, code_value, status, added_by)
                    VALUES (?, ?, 'available', ?)
                """, (code_type, code_value, added_by))
            
            row = cursor.fetchone()
            return row['id'] if row and isinstance(row, dict) else (row[0] if row else None)
    
    except Exception as e:
        log_error_with_context(e, "add_stock_code", code_type=code_type)
        return None

def get_available_stock_count(code_type=None):
    """Get count of available stock codes"""
    try:
        with get_db_connection(commit=False) as conn:
            cursor = conn.cursor()
            
            if code_type:
                if DATABASE_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT COUNT(*) FROM stock_codes 
                        WHERE status = 'available' AND code_type = %s
                    """, (code_type,))
                else:
                    cursor.execute("""
                        SELECT COUNT(*) FROM stock_codes 
                        WHERE status = 'available' AND code_type = ?
                    """, (code_type,))
            else:
                cursor.execute("SELECT COUNT(*) FROM stock_codes WHERE status = 'available'")
            
            return cursor.fetchone()[0]
    
    except Exception as e:
        log_error_with_context(e, "get_available_stock_count")
        return 0

def reserve_stock_codes(code_type, quantity, order_id):
    """Reserve stock codes for an order"""
    try:
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            # Get available codes
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id FROM stock_codes
                    WHERE status = 'available' AND code_type = %s
                    LIMIT %s
                    FOR UPDATE
                """, (code_type, quantity))
            else:
                cursor.execute("""
                    SELECT id FROM stock_codes
                    WHERE status = 'available' AND code_type = ?
                    LIMIT ?
                """, (code_type, quantity))
            
            codes = cursor.fetchall()
            
            if len(codes) < quantity:
                return None  # Not enough stock
            
            code_ids = [row['id'] if isinstance(row, dict) else row[0] for row in codes]
            
            # Reserve codes
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE stock_codes
                    SET status = 'reserved',
                        reserved_for_order = %s,
                        reserved_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                """, (order_id, code_ids))
            else:
                placeholders = ','.join('?' * len(code_ids))
                cursor.execute(f"""
                    UPDATE stock_codes
                    SET status = 'reserved',
                        reserved_for_order = ?,
                        reserved_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                """, [order_id] + code_ids)
            
            return code_ids
    
    except Exception as e:
        log_error_with_context(e, "reserve_stock_codes", code_type=code_type)
        return None

def get_reserved_codes(order_id):
    """Get codes reserved for an order"""
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, code_value FROM stock_codes
                    WHERE reserved_for_order = %s AND status = 'reserved'
                """, (order_id,))
            else:
                cursor.execute("""
                    SELECT id, code_value FROM stock_codes
                    WHERE reserved_for_order = ? AND status = 'reserved'
                """, (order_id,))
            
            return cursor.fetchall()
    
    except Exception as e:
        log_error_with_context(e, "get_reserved_codes", order_id=order_id)
        return []

def mark_codes_as_used(code_ids):
    """Mark codes as used"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE stock_codes
                    SET status = 'used', used_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                """, (code_ids,))
            else:
                placeholders = ','.join('?' * len(code_ids))
                cursor.execute(f"""
                    UPDATE stock_codes
                    SET status = 'used', used_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                """, code_ids)
            
            return True
    
    except Exception as e:
        log_error_with_context(e, "mark_codes_as_used")
        return False

# ==========================================
# ADMIN STATISTICS
# ==========================================

def get_database_stats():
    """
    Get database statistics for admin panel
    
    Returns:
        dict: Statistics including user count, order count, stock count, etc.
    """
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            stats = {
                'total_users': 0,
                'total_orders': 0,
                'pending_orders': 0,
                'completed_orders': 0,
                'total_revenue': 0,
                'total_topups': 0,
                'total_topup_amount': 0,
                'available_stock': {},
                'total_stock_all': 0,
                'recent_orders': []
            }
            
            # Count total users
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("SELECT COUNT(*) as count FROM users")
            else:
                cursor.execute("SELECT COUNT(*) as count FROM users")
            
            row = cursor.fetchone()
            stats['total_users'] = row['count'] if isinstance(row, dict) else row[0]
            
            # Count orders by status
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN total_price ELSE 0 END), 0) as revenue
                    FROM orders
                """)
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN total_price ELSE 0 END), 0) as revenue
                    FROM orders
                """)
            
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    stats['total_orders'] = row['total']
                    stats['pending_orders'] = row['pending'] or 0
                    stats['completed_orders'] = row['completed'] or 0
                    stats['total_revenue'] = row['revenue'] or 0
                else:
                    stats['total_orders'] = row[0]
                    stats['pending_orders'] = row[1] or 0
                    stats['completed_orders'] = row[2] or 0
                    stats['total_revenue'] = row[3] or 0
            
            # Count topups
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT 
                        COUNT(*) as count,
                        COALESCE(SUM(amount), 0) as total_amount
                    FROM topups
                    WHERE status = 'success'
                """)
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as count,
                        COALESCE(SUM(amount), 0) as total_amount
                    FROM topups
                    WHERE status = 'success'
                """)
            
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    stats['total_topups'] = row['count']
                    stats['total_topup_amount'] = row['total_amount']
                else:
                    stats['total_topups'] = row[0]
                    stats['total_topup_amount'] = row[1]
            
            # Count available stock by type
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT code_type, COUNT(*) as count
                    FROM stock_codes
                    WHERE status = 'available'
                    GROUP BY code_type
                """)
            else:
                cursor.execute("""
                    SELECT code_type, COUNT(*) as count
                    FROM stock_codes
                    WHERE status = 'available'
                    GROUP BY code_type
                """)
            
            rows = cursor.fetchall()
            for row in rows:
                if isinstance(row, dict):
                    code_type = row['code_type']
                    count = row['count']
                else:
                    code_type = row[0]
                    count = row[1]
                
                stats['available_stock'][code_type] = count
                stats['total_stock_all'] += count
            
            # Get recent orders (last 5)
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT order_number, user_id, package_type, total_price, status, created_at
                    FROM orders
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
            else:
                cursor.execute("""
                    SELECT order_number, user_id, package_type, total_price, status, created_at
                    FROM orders
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
            
            rows = cursor.fetchall()
            for row in rows:
                if isinstance(row, dict):
                    stats['recent_orders'].append({
                        'order_number': row['order_number'],
                        'user_id': row['user_id'],
                        'package_type': row['package_type'],
                        'total_price': row['total_price'],
                        'status': row['status'],
                        'created_at': row['created_at']
                    })
                else:
                    stats['recent_orders'].append({
                        'order_number': row[0],
                        'user_id': row[1],
                        'package_type': row[2],
                        'total_price': row[3],
                        'status': row[4],
                        'created_at': row[5]
                    })
            
            return stats
    
    except Exception as e:
        log_error_with_context(e, "get_database_stats")
        return {
            'total_users': 0,
            'total_orders': 0,
            'pending_orders': 0,
            'completed_orders': 0,
            'total_revenue': 0,
            'total_topups': 0,
            'total_topup_amount': 0,
            'available_stock': {},
            'total_stock_all': 0,
            'recent_orders': []
        }

def get_all_orders(limit=50):
    """
    Get all orders (for admin)
    
    Args:
        limit: Maximum number of orders to return
    
    Returns:
        list: List of order records
    """
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT * FROM orders
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT * FROM orders
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            return cursor.fetchall()
    
    except Exception as e:
        log_error_with_context(e, "get_all_orders")
        return []

def get_all_stock_codes(code_type=None, status=None, limit=100):
    """
    Get all stock codes (for admin)
    
    Args:
        code_type: Filter by code type (optional)
        status: Filter by status (optional)
        limit: Maximum number of codes to return
    
    Returns:
        list: List of stock code records
    """
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            query = "SELECT * FROM stock_codes WHERE 1=1"
            params = []
            
            if code_type:
                if DATABASE_TYPE == 'postgresql':
                    query += " AND code_type = %s"
                else:
                    query += " AND code_type = ?"
                params.append(code_type)
            
            if status:
                if DATABASE_TYPE == 'postgresql':
                    query += " AND status = %s"
                else:
                    query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY added_at DESC"
            
            if DATABASE_TYPE == 'postgresql':
                query += " LIMIT %s"
            else:
                query += " LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return cursor.fetchall()
    
    except Exception as e:
        log_error_with_context(e, "get_all_stock_codes")
        return []

# ==========================================
# CLEANUP
# ==========================================

def close_pools():
    """Close all connection pools"""
    global _pg_pool, _sqlite_pool
    
    try:
        if _pg_pool:
            _pg_pool.closeall()
            _pg_pool = None
            logger.info("PostgreSQL pool closed")
        
        if _sqlite_pool:
            _sqlite_pool.close_all()
            _sqlite_pool = None
            logger.info("SQLite pool closed")
    
    except Exception as e:
        log_error_with_context(e, "close_pools")

# ==========================================
# EXPORT
# ==========================================

__all__ = [
    'init_database',
    'get_db_connection',
    'dict_cursor',
    'ensure_user_exists',
    'get_balance',
    'add_balance',
    'deduct_balance',
    'get_user_stats',
    'create_topup',
    'update_topup_status',
    'get_topup_by_order_id',
    'create_order',
    'get_order_by_id',
    'get_order_by_number',
    'get_user_orders',
    'update_order_status',
    'add_stock_code',
    'get_available_stock_count',
    'reserve_stock_codes',
    'get_reserved_codes',
    'mark_codes_as_used',
    'get_database_stats',
    'get_all_orders',
    'get_all_stock_codes',
    'close_pools'
]