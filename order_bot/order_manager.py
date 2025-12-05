"""
Order Manager
=============
Handles order creation, processing, and management
"""

import asyncio
from datetime import datetime
import config
from database import (
    get_balance, deduct_balance, create_order, get_order_by_id,
    update_order_status, reserve_stock_codes, get_available_stock_count,
    get_reserved_codes, mark_codes_as_used
)
from logger import (
    logger, log_error_with_context, log_order_created, log_order_completed,
    log_order_failed, PerformanceLogger
)

# ==========================================
# ORDER VALIDATION
# ==========================================

def validate_order_request(user_id, package_type):
    """
    Validate order request
    
    Returns:
        dict: {'valid': bool, 'error': str or None, 'details': dict}
    """
    try:
        # Check package exists
        package_info = config.get_package_info(package_type)
        if not package_info:
            return {
                'valid': False,
                'error': f"Invalid package type: {package_type}",
                'details': {}
            }
        
        quantity = package_info['quantity']
        price = package_info['price']
        
        # Check quantity limits
        if quantity > config.MAX_CODES_PER_ORDER:
            return {
                'valid': False,
                'error': f"Maximum {config.MAX_CODES_PER_ORDER} codes per order",
                'details': {'quantity': quantity}
            }
        
        # Check user balance
        balance = get_balance(user_id)
        if balance < price:
            return {
                'valid': False,
                'error': f"Insufficient balance. Need: Rp {price:,}, Have: Rp {balance:,}",
                'details': {
                    'required': price,
                    'current': balance,
                    'shortfall': price - balance
                }
            }
        
        # Check stock availability
        available_stock = get_available_stock_count()
        if available_stock < quantity:
            return {
                'valid': False,
                'error': f"Insufficient stock. Need: {quantity}, Available: {available_stock}",
                'details': {
                    'required': quantity,
                    'available': available_stock
                }
            }
        
        return {
            'valid': True,
            'error': None,
            'details': {
                'quantity': quantity,
                'price': price,
                'balance': balance,
                'available_stock': available_stock
            }
        }
        
    except Exception as e:
        log_error_with_context(e, "validate_order_request", user_id=user_id, package=package_type)
        return {
            'valid': False,
            'error': f"Validation error: {str(e)}",
            'details': {}
        }

# ==========================================
# ORDER CREATION
# ==========================================

def create_new_order(user_id, package_type, payment_method='balance'):
    """
    Create new order
    
    Returns:
        dict: {
            'success': bool,
            'order_id': int or None,
            'order_number': str or None,
            'error': str or None
        }
    """
    try:
        with PerformanceLogger("Create Order"):
            # Validate order
            validation = validate_order_request(user_id, package_type)
            if not validation['valid']:
                return {
                    'success': False,
                    'order_id': None,
                    'order_number': None,
                    'error': validation['error'],
                    'details': validation['details']
                }
            
            package_info = config.get_package_info(package_type)
            quantity = package_info['quantity']
            price = package_info['price']
            
            # Deduct balance (atomic)
            balance_deducted = deduct_balance(user_id, price)
            if not balance_deducted:
                return {
                    'success': False,
                    'order_id': None,
                    'order_number': None,
                    'error': "Failed to deduct balance",
                    'details': {}
                }
            
            # Create order record
            order_id, order_number = create_order(
                user_id=user_id,
                package_type=package_type,
                code_quantity=quantity,
                total_price=price,
                payment_method=payment_method
            )
            
            if not order_id:
                # Rollback balance if order creation failed
                from database import add_balance
                add_balance(user_id, price)
                return {
                    'success': False,
                    'order_id': None,
                    'order_number': None,
                    'error': "Failed to create order record",
                    'details': {}
                }
            
            # Reserve stock
            stock_ids = reserve_stock_codes(order_id, quantity)
            if len(stock_ids) < quantity:
                # Rollback
                from database import add_balance
                add_balance(user_id, price)
                update_order_status(order_id, 'failed', 'stock_unavailable')
                return {
                    'success': False,
                    'order_id': order_id,
                    'order_number': order_number,
                    'error': f"Failed to reserve stock. Got {len(stock_ids)}/{quantity} codes",
                    'details': {}
                }
            
            # Log success
            log_order_created(order_number, user_id, package_type, price)
            
            return {
                'success': True,
                'order_id': order_id,
                'order_number': order_number,
                'error': None,
                'details': {
                    'quantity': quantity,
                    'price': price,
                    'stock_reserved': len(stock_ids)
                }
            }
            
    except Exception as e:
        log_error_with_context(e, "create_new_order", user_id=user_id, package=package_type)
        return {
            'success': False,
            'order_id': None,
            'order_number': None,
            'error': f"Order creation failed: {str(e)}",
            'details': {}
        }

# ==========================================
# ORDER PROCESSING
# ==========================================

async def process_order(order_id, delivery_handler=None):
    """
    Process order: reserve stock, deliver codes, mark complete
    
    Args:
        order_id: Order ID to process
        delivery_handler: Function to handle delivery (async)
    
    Returns:
        dict: {
            'success': bool,
            'delivered': bool,
            'error': str or None
        }
    """
    try:
        with PerformanceLogger("Process Order"):
            # Get order details
            order = get_order_by_id(order_id)
            if not order:
                return {
                    'success': False,
                    'delivered': False,
                    'error': "Order not found"
                }
            
            # Check if already processed
            if order['status'] == 'completed':
                return {
                    'success': True,
                    'delivered': True,
                    'error': None
                }
            
            # Get reserved codes
            codes = get_reserved_codes(order_id)
            if not codes:
                log_order_failed(order['order_number'], order['user_id'], "No codes reserved")
                update_order_status(order_id, 'failed', 'no_codes')
                return {
                    'success': False,
                    'delivered': False,
                    'error': "No codes reserved for this order"
                }
            
            # Check quantity matches
            if len(codes) != order['code_quantity']:
                logger.warning(
                    f"Code quantity mismatch: expected {order['code_quantity']}, got {len(codes)}",
                    order_id=order_id
                )
            
            # Deliver codes if handler provided
            delivery_success = False
            if delivery_handler and config.AUTO_DELIVERY_ENABLED:
                try:
                    delivery_result = await delivery_handler(
                        user_id=order['user_id'],
                        order_number=order['order_number'],
                        codes=codes
                    )
                    delivery_success = delivery_result.get('success', False)
                except Exception as e:
                    log_error_with_context(e, "delivery_handler", order_id=order_id)
                    delivery_success = False
            else:
                # Manual delivery required
                update_order_status(order_id, 'pending', 'pending_manual_delivery')
                return {
                    'success': True,
                    'delivered': False,
                    'error': None,
                    'manual_delivery_required': True
                }
            
            if delivery_success:
                # Mark codes as used
                stock_ids = [code['id'] for code in codes]
                mark_codes_as_used(stock_ids, order['user_id'])
                
                # Update order status
                update_order_status(order_id, 'completed', 'delivered')
                
                log_order_completed(order['order_number'], order['user_id'], len(codes))
                
                return {
                    'success': True,
                    'delivered': True,
                    'error': None
                }
            else:
                # Delivery failed
                update_order_status(order_id, 'pending', 'delivery_failed')
                log_order_failed(order['order_number'], order['user_id'], "Delivery failed")
                
                return {
                    'success': False,
                    'delivered': False,
                    'error': "Delivery failed",
                    'retry_possible': True
                }
            
    except Exception as e:
        log_error_with_context(e, "process_order", order_id=order_id)
        return {
            'success': False,
            'delivered': False,
            'error': f"Processing failed: {str(e)}"
        }

# ==========================================
# ORDER CANCELLATION
# ==========================================

def cancel_order(order_id, reason="User cancelled", refund=True):
    """
    Cancel order and optionally refund
    
    Returns:
        dict: {'success': bool, 'refunded': bool, 'error': str or None}
    """
    try:
        if not config.ENABLE_ORDER_CANCELLATION:
            return {
                'success': False,
                'refunded': False,
                'error': "Order cancellation is disabled"
            }
        
        # Get order
        order = get_order_by_id(order_id)
        if not order:
            return {
                'success': False,
                'refunded': False,
                'error': "Order not found"
            }
        
        # Check if can be cancelled
        if order['status'] == 'completed':
            return {
                'success': False,
                'refunded': False,
                'error': "Cannot cancel completed order"
            }
        
        if order['status'] == 'cancelled':
            return {
                'success': False,
                'refunded': False,
                'error': "Order already cancelled"
            }
        
        # Release reserved stock
        from database import get_db_connection, dict_cursor
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE stock 
                    SET reserved_for_order = NULL 
                    WHERE reserved_for_order = %s
                """, (order_id,))
            else:
                cursor.execute("""
                    UPDATE stock 
                    SET reserved_for_order = NULL 
                    WHERE reserved_for_order = ?
                """, (order_id,))
        
        # Refund if requested and enabled
        refunded = False
        if refund and config.ENABLE_REFUND and order['payment_method'] == 'balance':
            from database import add_balance
            new_balance = add_balance(order['user_id'], order['total_price'])
            if new_balance is not None:
                refunded = True
                logger.info(f"Refunded Rp {order['total_price']:,} to user {order['user_id']}")
        
        # Update order status
        update_order_status(order_id, 'cancelled')
        
        logger.info(
            f"Order cancelled: {order['order_number']}",
            reason=reason,
            refunded=refunded
        )
        
        return {
            'success': True,
            'refunded': refunded,
            'error': None
        }
        
    except Exception as e:
        log_error_with_context(e, "cancel_order", order_id=order_id)
        return {
            'success': False,
            'refunded': False,
            'error': f"Cancellation failed: {str(e)}"
        }

# ==========================================
# ORDER RETRY
# ==========================================

async def retry_order_delivery(order_id, delivery_handler):
    """
    Retry delivery for failed order
    
    Returns:
        dict: {'success': bool, 'error': str or None}
    """
    try:
        order = get_order_by_id(order_id)
        if not order:
            return {
                'success': False,
                'error': "Order not found"
            }
        
        if order['status'] == 'completed':
            return {
                'success': True,
                'error': None,
                'message': "Order already completed"
            }
        
        # Process order
        result = await process_order(order_id, delivery_handler)
        return result
        
    except Exception as e:
        log_error_with_context(e, "retry_order_delivery", order_id=order_id)
        return {
            'success': False,
            'error': f"Retry failed: {str(e)}"
        }

# ==========================================
# ORDER STATISTICS
# ==========================================

def get_order_statistics(user_id=None, days=30):
    """
    Get order statistics
    
    Args:
        user_id: Specific user or None for all users
        days: Number of days to analyze
    
    Returns:
        dict: Statistics data
    """
    try:
        from database import get_db_connection, dict_cursor
        
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if user_id:
                # User-specific stats
                if config.DATABASE_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_orders,
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status = 'pending') as pending,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed,
                            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                            SUM(total_price) as total_spent,
                            SUM(code_quantity) as total_codes
                        FROM orders
                        WHERE user_id = %s
                        AND created_at >= NOW() - INTERVAL '%s days'
                    """, (user_id, days))
                else:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_orders,
                            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                            SUM(total_price) as total_spent,
                            SUM(code_quantity) as total_codes
                        FROM orders
                        WHERE user_id = ?
                        AND created_at >= datetime('now', '-' || ? || ' days')
                    """, (user_id, days))
            else:
                # Global stats
                if config.DATABASE_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_orders,
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status = 'pending') as pending,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed,
                            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                            SUM(total_price) as total_revenue,
                            SUM(code_quantity) as total_codes,
                            COUNT(DISTINCT user_id) as unique_users
                        FROM orders
                        WHERE created_at >= NOW() - INTERVAL '%s days'
                    """, (days,))
                else:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_orders,
                            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                            SUM(total_price) as total_revenue,
                            SUM(code_quantity) as total_codes,
                            COUNT(DISTINCT user_id) as unique_users
                        FROM orders
                        WHERE created_at >= datetime('now', '-' || ? || ' days')
                    """, (days,))
            
            row = cursor.fetchone()
            
            if isinstance(row, dict):
                return dict(row)
            else:
                # Convert to dict
                return {
                    'total_orders': row[0] or 0,
                    'completed': row[1] or 0,
                    'pending': row[2] or 0,
                    'failed': row[3] or 0,
                    'cancelled': row[4] or 0,
                    'total_spent' if user_id else 'total_revenue': row[5] or 0,
                    'total_codes': row[6] or 0,
                    'unique_users': row[7] if not user_id else None
                }
        
    except Exception as e:
        log_error_with_context(e, "get_order_statistics", user_id=user_id, days=days)
        return {
            'total_orders': 0,
            'completed': 0,
            'pending': 0,
            'failed': 0,
            'cancelled': 0,
            'total_spent' if user_id else 'total_revenue': 0,
            'total_codes': 0
        }

# ==========================================
# BULK ORDER OPERATIONS
# ==========================================

async def process_pending_orders(delivery_handler, max_orders=10):
    """
    Process all pending orders
    
    Returns:
        dict: {'processed': int, 'success': int, 'failed': int}
    """
    try:
        from database import get_db_connection, dict_cursor
        
        # Get pending orders
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id FROM orders 
                    WHERE status = 'pending' 
                    AND delivery_status != 'delivered'
                    ORDER BY created_at ASC
                    LIMIT %s
                """, (max_orders,))
            else:
                cursor.execute("""
                    SELECT id FROM orders 
                    WHERE status = 'pending' 
                    AND delivery_status != 'delivered'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (max_orders,))
            
            rows = cursor.fetchall()
            order_ids = [row['id'] if isinstance(row, dict) else row[0] for row in rows]
        
        # Process each order
        processed = 0
        success = 0
        failed = 0
        
        for order_id in order_ids:
            result = await process_order(order_id, delivery_handler)
            processed += 1
            
            if result['success'] and result.get('delivered'):
                success += 1
            else:
                failed += 1
            
            # Small delay between orders
            await asyncio.sleep(1)
        
        logger.info(f"Bulk processing: {processed} orders ({success} success, {failed} failed)")
        
        return {
            'processed': processed,
            'success': success,
            'failed': failed
        }
        
    except Exception as e:
        log_error_with_context(e, "process_pending_orders")
        return {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'error': str(e)
        }

# ==========================================
# EXPORT
# ==========================================

__all__ = [
    'validate_order_request',
    'create_new_order',
    'process_order',
    'cancel_order',
    'retry_order_delivery',
    'get_order_statistics',
    'process_pending_orders',
]
