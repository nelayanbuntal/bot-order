"""
Webhook Server for Midtrans Payment Notifications
==================================================
Handles payment notifications and updates user balance automatically
"""

from flask import Flask, request, jsonify
import config
from database import add_balance, create_topup, update_topup_status, get_db_connection, dict_cursor
from payment_gateway import parse_webhook_notification, verify_signature
from logger import (
    logger, log_payment_received, log_webhook_received, 
    log_error_with_context
)

# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)

# Disable Flask's default logging (use our logger instead)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==========================================
# WEBHOOK ENDPOINT
# ==========================================

@app.route('/webhook/midtrans', methods=['POST'])
def midtrans_webhook():
    """
    Handle Midtrans payment notification webhook
    
    Midtrans will POST to this endpoint when payment status changes
    """
    try:
        # Get JSON data from request
        notification = request.get_json()
        
        if not notification:
            logger.warning("⚠️ Webhook received with no JSON data")
            return jsonify({
                'status': 'error',
                'message': 'No JSON data received'
            }), 400
        
        # Log webhook receipt
        order_id = notification.get('order_id', 'unknown')
        transaction_status = notification.get('transaction_status', 'unknown')
        payment_type = notification.get('payment_type', 'unknown')
        
        log_webhook_received(order_id, transaction_status, payment_type)
        
        # Parse and validate notification
        parsed = parse_webhook_notification(
            notification_json=notification,
            server_key=config.MIDTRANS_SERVER_KEY
        )
        
        if not parsed['valid']:
            logger.error(f"❌ Invalid webhook notification: {parsed.get('error')}")
            return jsonify({
                'status': 'error',
                'message': 'Invalid signature or missing fields'
            }), 400
        
        # Extract data
        order_id = parsed['order_id']
        status = parsed['status']  # 'success', 'failed', or 'pending'
        gross_amount = int(parsed['gross_amount'])
        transaction_status = parsed['transaction_status']
        
        logger.info(f"📥 Webhook: {order_id} | Status: {status} | Amount: Rp {gross_amount:,}")
        
        # Handle based on status
        if status == 'success':
            # Payment successful - credit user balance
            handle_payment_success(order_id, gross_amount, parsed)
        
        elif status == 'pending':
            # Payment still pending - just log
            logger.info(f"⏳ Payment pending: {order_id}")
            # Update topup status to pending (if exists)
            update_topup_status(order_id, 'pending')
        
        elif status == 'failed':
            # Payment failed - mark as failed
            logger.warning(f"❌ Payment failed: {order_id}")
            update_topup_status(order_id, 'failed')
        
        # Return success response to Midtrans
        return jsonify({
            'status': 'success',
            'message': 'Notification processed'
        }), 200
    
    except Exception as e:
        log_error_with_context(e, "midtrans_webhook")
        
        # Still return 200 to Midtrans to avoid retries
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 200

def handle_payment_success(order_id, amount, parsed_data):
    """
    Handle successful payment
    
    Args:
        order_id: Order ID from Midtrans (e.g., TOPUP-123456-20241205...)
        amount: Payment amount in Rupiah
        parsed_data: Parsed webhook data
    """
    try:
        # Extract user ID from order_id
        # Format: TOPUP-{user_id}-{timestamp} or ORDER-{user_id}-{timestamp}
        parts = order_id.split('-')
        
        if len(parts) < 3:
            logger.error(f"❌ Invalid order_id format: {order_id}")
            return False
        
        try:
            user_id = int(parts[1])
        except ValueError:
            logger.error(f"❌ Cannot extract user_id from: {order_id}")
            return False
        
        # Check if this is a top-up (not an order)
        is_topup = order_id.startswith('TOPUP-')
        
        if is_topup:
            # This is a balance top-up
            
            # Check if already processed (avoid double crediting)
            with get_db_connection(commit=False) as conn:
                cursor = dict_cursor(conn)
                
                if config.DATABASE_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT status FROM topups 
                        WHERE order_id = %s
                    """, (order_id,))
                else:
                    cursor.execute("""
                        SELECT status FROM topups 
                        WHERE order_id = ?
                    """, (order_id,))
                
                row = cursor.fetchone()
                
                if row:
                    existing_status = row['status'] if isinstance(row, dict) else row[0]
                    if existing_status == 'success':
                        logger.warning(f"⚠️ Payment already processed: {order_id}")
                        return True  # Already processed, skip
            
            # Create or update topup record
            create_topup(
                user_id=user_id,
                amount=amount,
                order_id=order_id,
                payment_type=parsed_data.get('payment_type', 'qris'),
                transaction_id=parsed_data.get('transaction_id')
            )
            
            # Credit user balance
            new_balance = add_balance(user_id, amount)
            
            if new_balance is not None:
                # Update topup status
                update_topup_status(order_id, 'success')
                
                # Log success
                log_payment_received(
                    order_id, 
                    user_id, 
                    amount, 
                    parsed_data.get('payment_type', 'qris')
                )
                
                logger.info(
                    f"✅ Balance credited: User {user_id} | "
                    f"+Rp {amount:,} | New balance: Rp {new_balance:,}"
                )
                
                # Notify user (optional - via Discord DM)
                try:
                    notify_user_payment_success(user_id, amount, order_id)
                except Exception as e:
                    logger.warning(f"Failed to notify user: {e}")
                
                return True
            else:
                logger.error(f"❌ Failed to credit balance: User {user_id}")
                update_topup_status(order_id, 'failed')
                return False
        
        else:
            # This is an order payment (ORDER-xxx)
            logger.info(f"📦 Order payment detected: {order_id}")
            # Order payments are handled differently - just update status
            update_topup_status(order_id, 'success')
            return True
    
    except Exception as e:
        log_error_with_context(e, "handle_payment_success", order_id=order_id)
        return False

def notify_user_payment_success(user_id, amount, order_id):
    """
    Notify user via Discord DM that payment was successful
    
    Note: This requires bot instance which may not be available in webhook thread
    So we'll just log for now - actual notification happens when bot checks
    """
    logger.info(f"💬 User {user_id} should be notified of payment success")
    # Actual notification will be handled by bot when user checks balance
    # or via a background task

# ==========================================
# HEALTH CHECK ENDPOINT
# ==========================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'webhook-server',
        'port': config.WEBHOOK_PORT
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'Midtrans Webhook Server',
        'status': 'running',
        'endpoints': {
            'webhook': '/webhook/midtrans',
            'health': '/health'
        }
    }), 200

# ==========================================
# RUN SERVER
# ==========================================

def run_server():
    """Run Flask server"""
    try:
        logger.info(f"🌐 Webhook server starting on 0.0.0.0:{config.WEBHOOK_PORT}")
        
        app.run(
            host='0.0.0.0',
            port=config.WEBHOOK_PORT,
            debug=False,  # Disable debug in production
            use_reloader=False  # Disable reloader when run in thread
        )
    except Exception as e:
        log_error_with_context(e, "run_server")
        raise

# ==========================================
# STANDALONE MODE
# ==========================================

if __name__ == '__main__':
    """
    Run webhook server standalone (not integrated with bot)
    
    Usage: python webhook_server.py
    """
    print("="*50)
    print("🔔 Midtrans Webhook Server")
    print("="*50)
    print(f"Port: {config.WEBHOOK_PORT}")
    print(f"Environment: {'🔴 PRODUCTION' if config.MIDTRANS_IS_PRODUCTION else '🟡 SANDBOX'}")
    print("="*50)
    print()
    
    # Validate config
    if not config.MIDTRANS_SERVER_KEY or config.MIDTRANS_SERVER_KEY == 'YOUR_MIDTRANS_SERVER_KEY':
        logger.error("❌ MIDTRANS_SERVER_KEY not configured!")
        logger.error("Please set MIDTRANS_SERVER_KEY in .env file")
        exit(1)
    
    # Initialize database
    try:
        from database import init_database
        init_database()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        exit(1)
    
    # Start server
    try:
        run_server()
    except KeyboardInterrupt:
        logger.info("\n🛑 Webhook server stopped")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        exit(1)