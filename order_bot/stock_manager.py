"""
Stock Manager
=============
Handles stock management, encryption, and bulk operations
"""

import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import config
from database import (
    add_stock_code, get_available_stock_count, get_db_connection, dict_cursor
)
from logger import (
    logger, log_error_with_context, log_stock_added, log_stock_alert, PerformanceLogger
)

# ==========================================
# ENCRYPTION
# ==========================================

class StockEncryption:
    """Handle stock code encryption/decryption"""
    
    def __init__(self):
        self.fernet = None
        if config.ENCRYPT_STOCK_CODES:
            self.fernet = self._get_fernet()
    
    def _get_fernet(self):
        """Initialize Fernet cipher"""
        try:
            # Generate key from config encryption key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'redfinger_order_salt',  # In production, use random salt stored securely
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(config.ENCRYPTION_KEY.encode()))
            return Fernet(key)
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            return None
    
    def encrypt(self, code):
        """Encrypt a code"""
        if not self.fernet or not config.ENCRYPT_STOCK_CODES:
            return code
        
        try:
            encrypted = self.fernet.encrypt(code.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return code
    
    def decrypt(self, encrypted_code):
        """Decrypt a code"""
        if not self.fernet or not config.ENCRYPT_STOCK_CODES:
            return encrypted_code
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_code.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_code

# Global encryptor instance
_encryptor = StockEncryption()

# ==========================================
# STOCK ADDITION
# ==========================================

def add_single_code(code, code_type='redfinger', added_by=None):
    """
    Add single code to stock
    
    Returns:
        dict: {'success': bool, 'stock_id': int or None, 'error': str or None}
    """
    try:
        # Validate code format (basic)
        code = code.strip()
        if not code:
            return {
                'success': False,
                'stock_id': None,
                'error': "Empty code"
            }
        
        if len(code) < 5:
            return {
                'success': False,
                'stock_id': None,
                'error': "Code too short"
            }
        
        # Encrypt if enabled
        original_code = code
        is_encrypted = False
        
        if config.ENCRYPT_STOCK_CODES:
            code = _encryptor.encrypt(code)
            is_encrypted = True
        
        # Add to database
        stock_id = add_stock_code(
            code=code,
            code_type=code_type,
            added_by=added_by,
            is_encrypted=is_encrypted
        )
        
        if stock_id:
            return {
                'success': True,
                'stock_id': stock_id,
                'error': None
            }
        else:
            return {
                'success': False,
                'stock_id': None,
                'error': "Failed to add code to database"
            }
            
    except Exception as e:
        log_error_with_context(e, "add_single_code")
        return {
            'success': False,
            'stock_id': None,
            'error': str(e)
        }

def add_bulk_codes(codes, code_type='redfinger', added_by=None):
    """
    Add multiple codes to stock
    
    Args:
        codes: List of code strings
        code_type: Type of codes
        added_by: User ID who added the codes
    
    Returns:
        dict: {
            'success': bool,
            'added': int,
            'failed': int,
            'errors': list,
            'stock_ids': list
        }
    """
    try:
        with PerformanceLogger(f"Bulk Add {len(codes)} Codes"):
            added = 0
            failed = 0
            errors = []
            stock_ids = []
            
            for idx, code in enumerate(codes, 1):
                result = add_single_code(code, code_type, added_by)
                
                if result['success']:
                    added += 1
                    stock_ids.append(result['stock_id'])
                else:
                    failed += 1
                    errors.append({
                        'line': idx,
                        'code': config.mask_sensitive(code),
                        'error': result['error']
                    })
                
                # Log progress every 100 codes
                if idx % 100 == 0:
                    logger.info(f"Progress: {idx}/{len(codes)} codes processed")
            
            # Log summary
            log_stock_added(added_by, added, code_type)
            
            if failed > 0:
                logger.warning(f"Failed to add {failed}/{len(codes)} codes")
            
            # Check low stock alert
            check_stock_alert()
            
            return {
                'success': failed == 0,
                'added': added,
                'failed': failed,
                'errors': errors,
                'stock_ids': stock_ids
            }
            
    except Exception as e:
        log_error_with_context(e, "add_bulk_codes")
        return {
            'success': False,
            'added': 0,
            'failed': len(codes),
            'errors': [str(e)],
            'stock_ids': []
        }

def add_codes_from_text(text_content, code_type='redfinger', added_by=None):
    """
    Parse and add codes from text content
    
    Args:
        text_content: String with codes (one per line)
        code_type: Type of codes
        added_by: User ID who added the codes
    
    Returns:
        dict: Same as add_bulk_codes
    """
    try:
        # Parse lines
        lines = text_content.strip().split('\n')
        codes = []
        
        for line in lines:
            code = line.strip()
            
            # Skip empty lines and comments
            if not code or code.startswith('#'):
                continue
            
            codes.append(code)
        
        if not codes:
            return {
                'success': False,
                'added': 0,
                'failed': 0,
                'errors': ["No valid codes found"],
                'stock_ids': []
            }
        
        # Add codes
        return add_bulk_codes(codes, code_type, added_by)
        
    except Exception as e:
        log_error_with_context(e, "add_codes_from_text")
        return {
            'success': False,
            'added': 0,
            'failed': 0,
            'errors': [str(e)],
            'stock_ids': []
        }

# ==========================================
# STOCK RETRIEVAL
# ==========================================

def get_stock_codes(stock_ids, decrypt=True):
    """
    Get codes by stock IDs
    
    Returns:
        list: List of dicts with code info
    """
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            # Build query with IN clause
            placeholders = ','.join(['%s' if config.DATABASE_TYPE == 'postgresql' else '?'] * len(stock_ids))
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute(f"""
                    SELECT id, code, is_encrypted
                    FROM stock
                    WHERE id IN ({placeholders})
                """, tuple(stock_ids))
            else:
                cursor.execute(f"""
                    SELECT id, code, is_encrypted
                    FROM stock
                    WHERE id IN ({placeholders})
                """, tuple(stock_ids))
            
            rows = cursor.fetchall()
            
            codes = []
            for row in rows:
                if isinstance(row, dict):
                    code = row['code']
                    is_encrypted = row['is_encrypted']
                else:
                    code = row[1]
                    is_encrypted = row[2]
                
                # Decrypt if needed
                if decrypt and is_encrypted:
                    code = _encryptor.decrypt(code)
                
                codes.append({
                    'id': row['id'] if isinstance(row, dict) else row[0],
                    'code': code,
                    'is_encrypted': is_encrypted
                })
            
            return codes
            
    except Exception as e:
        log_error_with_context(e, "get_stock_codes")
        return []

def get_available_codes(limit=None, code_type='redfinger'):
    """
    Get available codes from stock
    
    Returns:
        list: List of available code dicts
    """
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if limit:
                if config.DATABASE_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id, code, is_encrypted
                        FROM stock
                        WHERE is_available = TRUE 
                        AND code_type = %s
                        AND reserved_for_order IS NULL
                        LIMIT %s
                    """, (code_type, limit))
                else:
                    cursor.execute("""
                        SELECT id, code, is_encrypted
                        FROM stock
                        WHERE is_available = 1 
                        AND code_type = ?
                        AND reserved_for_order IS NULL
                        LIMIT ?
                    """, (code_type, limit))
            else:
                if config.DATABASE_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id, code, is_encrypted
                        FROM stock
                        WHERE is_available = TRUE 
                        AND code_type = %s
                        AND reserved_for_order IS NULL
                    """, (code_type,))
                else:
                    cursor.execute("""
                        SELECT id, code, is_encrypted
                        FROM stock
                        WHERE is_available = 1 
                        AND code_type = ?
                        AND reserved_for_order IS NULL
                    """, (code_type,))
            
            rows = cursor.fetchall()
            
            codes = []
            for row in rows:
                if isinstance(row, dict):
                    code = row['code']
                    is_encrypted = row['is_encrypted']
                else:
                    code = row[1]
                    is_encrypted = row[2]
                
                # Decrypt if encrypted
                if is_encrypted:
                    code = _encryptor.decrypt(code)
                
                codes.append({
                    'id': row['id'] if isinstance(row, dict) else row[0],
                    'code': code,
                    'is_encrypted': is_encrypted
                })
            
            return codes
            
    except Exception as e:
        log_error_with_context(e, "get_available_codes")
        return []

# ==========================================
# STOCK STATISTICS
# ==========================================

def get_stock_summary():
    """
    Get stock summary statistics
    
    Returns:
        dict: Stock statistics by type
    """
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT 
                        code_type,
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE is_available = TRUE AND reserved_for_order IS NULL) as available,
                        COUNT(*) FILTER (WHERE reserved_for_order IS NOT NULL) as reserved,
                        COUNT(*) FILTER (WHERE is_available = FALSE) as used
                    FROM stock
                    GROUP BY code_type
                """)
            else:
                cursor.execute("""
                    SELECT 
                        code_type,
                        COUNT(*) as total,
                        SUM(CASE WHEN is_available = 1 AND reserved_for_order IS NULL THEN 1 ELSE 0 END) as available,
                        SUM(CASE WHEN reserved_for_order IS NOT NULL THEN 1 ELSE 0 END) as reserved,
                        SUM(CASE WHEN is_available = 0 THEN 1 ELSE 0 END) as used
                    FROM stock
                    GROUP BY code_type
                """)
            
            rows = cursor.fetchall()
            
            summary = {}
            for row in rows:
                if isinstance(row, dict):
                    summary[row['code_type']] = {
                        'total': row['total'],
                        'available': row['available'],
                        'reserved': row['reserved'],
                        'used': row['used']
                    }
                else:
                    summary[row[0]] = {
                        'total': row[1],
                        'available': row[2],
                        'reserved': row[3],
                        'used': row[4]
                    }
            
            return summary
            
    except Exception as e:
        log_error_with_context(e, "get_stock_summary")
        return {}

def get_detailed_stock_stats():
    """
    Get detailed stock statistics
    
    Returns:
        dict: Comprehensive stock statistics
    """
    try:
        summary = get_stock_summary()
        
        total_codes = sum(s['total'] for s in summary.values())
        total_available = sum(s['available'] for s in summary.values())
        total_used = sum(s['used'] for s in summary.values())
        total_reserved = sum(s['reserved'] for s in summary.values())
        
        return {
            'by_type': summary,
            'totals': {
                'total': total_codes,
                'available': total_available,
                'reserved': total_reserved,
                'used': total_used,
                'utilization_rate': (total_used / total_codes * 100) if total_codes > 0 else 0
            },
            'status': 'healthy' if total_available > config.LOW_STOCK_THRESHOLD else 'low',
            'low_stock': total_available < config.LOW_STOCK_THRESHOLD
        }
        
    except Exception as e:
        log_error_with_context(e, "get_detailed_stock_stats")
        return {
            'by_type': {},
            'totals': {
                'total': 0,
                'available': 0,
                'reserved': 0,
                'used': 0,
                'utilization_rate': 0
            },
            'status': 'error',
            'low_stock': True
        }

# ==========================================
# STOCK ALERTS
# ==========================================

def check_stock_alert(code_type='redfinger'):
    """
    Check if stock is low and should trigger alert
    
    Returns:
        dict: {'alert': bool, 'available': int, 'threshold': int}
    """
    try:
        available = get_available_stock_count(code_type)
        
        if config.STOCK_ALERT_ENABLED and available < config.LOW_STOCK_THRESHOLD:
            log_stock_alert(code_type, available, config.LOW_STOCK_THRESHOLD)
            
            return {
                'alert': True,
                'available': available,
                'threshold': config.LOW_STOCK_THRESHOLD,
                'message': f"Low stock: Only {available} {code_type} codes left!"
            }
        
        return {
            'alert': False,
            'available': available,
            'threshold': config.LOW_STOCK_THRESHOLD
        }
        
    except Exception as e:
        log_error_with_context(e, "check_stock_alert")
        return {
            'alert': False,
            'available': 0,
            'threshold': config.LOW_STOCK_THRESHOLD
        }

# ==========================================
# STOCK CLEANUP
# ==========================================

def cleanup_unreserved_old_codes(days=30):
    """
    Remove unreserved codes older than specified days
    (Only for codes that were never used)
    
    Returns:
        dict: {'removed': int, 'error': str or None}
    """
    try:
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    DELETE FROM stock
                    WHERE is_available = TRUE
                    AND reserved_for_order IS NULL
                    AND used_at IS NULL
                    AND added_at < NOW() - INTERVAL '%s days'
                """, (days,))
            else:
                cursor.execute("""
                    DELETE FROM stock
                    WHERE is_available = 1
                    AND reserved_for_order IS NULL
                    AND used_at IS NULL
                    AND added_at < datetime('now', '-' || ? || ' days')
                """, (days,))
            
            removed = cursor.rowcount
            
            if removed > 0:
                logger.info(f"Cleaned up {removed} old unreserved codes")
            
            return {
                'removed': removed,
                'error': None
            }
            
    except Exception as e:
        log_error_with_context(e, "cleanup_unreserved_old_codes")
        return {
            'removed': 0,
            'error': str(e)
        }

# ==========================================
# STOCK VALIDATION
# ==========================================

def validate_stock_code(code):
    """
    Validate code format (basic validation)
    
    Returns:
        dict: {'valid': bool, 'error': str or None}
    """
    code = code.strip()
    
    if not code:
        return {'valid': False, 'error': "Empty code"}
    
    if len(code) < 5:
        return {'valid': False, 'error': "Code too short (min 5 characters)"}
    
    if len(code) > 500:
        return {'valid': False, 'error': "Code too long (max 500 characters)"}
    
    # Add more validation rules as needed
    # Example: Check format, allowed characters, etc.
    
    return {'valid': True, 'error': None}

def check_duplicate_code(code, code_type='redfinger'):
    """
    Check if code already exists in stock
    
    Returns:
        bool: True if duplicate, False if unique
    """
    try:
        # Encrypt code if needed for comparison
        if config.ENCRYPT_STOCK_CODES:
            code = _encryptor.encrypt(code)
        
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM stock
                    WHERE code = %s AND code_type = %s
                """, (code, code_type))
            else:
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM stock
                    WHERE code = ? AND code_type = ?
                """, (code, code_type))
            
            row = cursor.fetchone()
            count = row['count'] if isinstance(row, dict) else row[0]
            
            return count > 0
            
    except Exception as e:
        log_error_with_context(e, "check_duplicate_code")
        return False

# ==========================================
# EXPORT FUNCTIONS
# ==========================================

def export_available_codes(code_type='redfinger', output_file='stock_export.txt'):
    """
    Export available codes to text file
    
    Returns:
        dict: {'success': bool, 'file': str, 'count': int}
    """
    try:
        codes = get_available_codes(code_type=code_type)
        
        if not codes:
            return {
                'success': False,
                'file': None,
                'count': 0,
                'error': "No codes available"
            }
        
        # Write to file
        with open(output_file, 'w') as f:
            for code_info in codes:
                f.write(f"{code_info['code']}\n")
        
        logger.info(f"Exported {len(codes)} codes to {output_file}")
        
        return {
            'success': True,
            'file': output_file,
            'count': len(codes),
            'error': None
        }
        
    except Exception as e:
        log_error_with_context(e, "export_available_codes")
        return {
            'success': False,
            'file': None,
            'count': 0,
            'error': str(e)
        }

# ==========================================
# EXPORT
# ==========================================

__all__ = [
    'add_single_code',
    'add_bulk_codes',
    'add_codes_from_text',
    'get_stock_codes',
    'get_available_codes',
    'get_stock_summary',
    'get_detailed_stock_stats',
    'check_stock_alert',
    'cleanup_unreserved_old_codes',
    'validate_stock_code',
    'check_duplicate_code',
    'export_available_codes',
]
