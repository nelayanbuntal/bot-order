#!/usr/bin/env python3
"""
Payment Webhook Test Trigger
=============================
Script untuk test webhook server dengan simulate Midtrans notifications

Usage:
    python trigger.py                                    # Test success payment (new order)
    python trigger.py --pending                          # Test pending payment
    python trigger.py --failed                           # Test failed payment
    python trigger.py --existing TOPUP-123-xxx           # Use existing order ID from Discord
    python trigger.py --user 123456                      # Test with specific user ID
"""

import requests
import hashlib
import json
import time
import argparse
from datetime import datetime

# ==========================================
# CONFIGURATION (Module Level)
# ==========================================

# Default values - will be updated in main()
DEFAULT_WEBHOOK_URL = "https://chalkiest-tendenciously-alfredo.ngrok-free.dev/webhook/midtrans"
DEFAULT_SERVER_KEY = "Mid-server-EGnfraulRARFfZbhT86J5zxi"
DEFAULT_USER_ID = 1384584067319730226  # Your Discord user ID

# ==========================================
# GENERATE SIGNATURE
# ==========================================

def generate_signature(order_id, status_code, gross_amount, server_key):
    """
    Generate Midtrans signature untuk webhook
    SHA512(order_id + status_code + gross_amount + server_key)
    """
    hash_string = f"{order_id}{status_code}{gross_amount}{server_key}"
    return hashlib.sha512(hash_string.encode()).hexdigest()

# ==========================================
# CREATE TEST PAYLOADS
# ==========================================

def create_success_payload(user_id, amount, server_key, order_id=None):
    """Create payload untuk successful payment"""
    
    # Generate order ID if not provided
    if not order_id:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        order_id = f"TOPUP-{user_id}-{timestamp}"
    
    # Payment details
    status_code = "200"
    gross_amount = str(amount)
    transaction_status = "settlement"  # atau "capture" untuk credit card
    
    # Generate signature
    signature = generate_signature(order_id, status_code, gross_amount, server_key)
    
    # Create payload
    payload = {
        "transaction_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "transaction_status": transaction_status,
        "transaction_id": f"test-{int(time.time())}",
        "status_message": "midtrans payment notification",
        "status_code": status_code,
        "signature_key": signature,
        "settlement_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "payment_type": "qris",
        "order_id": order_id,
        "merchant_id": "TEST-MERCHANT",
        "gross_amount": gross_amount,
        "fraud_status": "accept",
        "currency": "IDR"
    }
    
    return payload

def create_pending_payload(user_id, amount, server_key, order_id=None):
    """Create payload untuk pending payment"""
    
    if not order_id:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        order_id = f"TOPUP-{user_id}-{timestamp}"
    
    status_code = "201"
    gross_amount = str(amount)
    transaction_status = "pending"
    
    signature = generate_signature(order_id, status_code, gross_amount, server_key)
    
    payload = {
        "transaction_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "transaction_status": transaction_status,
        "transaction_id": f"test-{int(time.time())}",
        "status_message": "midtrans payment notification",
        "status_code": status_code,
        "signature_key": signature,
        "payment_type": "qris",
        "order_id": order_id,
        "merchant_id": "TEST-MERCHANT",
        "gross_amount": gross_amount,
        "currency": "IDR"
    }
    
    return payload

def create_failed_payload(user_id, amount, server_key, order_id=None):
    """Create payload untuk failed payment"""
    
    if not order_id:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        order_id = f"TOPUP-{user_id}-{timestamp}"
    
    status_code = "202"
    gross_amount = str(amount)
    transaction_status = "deny"  # atau "cancel", "expire"
    
    signature = generate_signature(order_id, status_code, gross_amount, server_key)
    
    payload = {
        "transaction_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "transaction_status": transaction_status,
        "transaction_id": f"test-{int(time.time())}",
        "status_message": "Transaction denied by bank",
        "status_code": status_code,
        "signature_key": signature,
        "payment_type": "qris",
        "order_id": order_id,
        "merchant_id": "TEST-MERCHANT",
        "gross_amount": gross_amount,
        "currency": "IDR"
    }
    
    return payload

# ==========================================
# SEND WEBHOOK
# ==========================================

def send_webhook(payload, webhook_url, test_name="Payment Test"):
    """Send webhook notification to server"""
    
    print("="*60)
    print(f"🔔 {test_name}")
    print("="*60)
    
    # Print payload
    print("\n📦 Payload:")
    print(json.dumps(payload, indent=2))
    
    print(f"\n📤 Sending to: {webhook_url}")
    
    try:
        # Send POST request
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📥 Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("\n✅ Webhook sent successfully!")
            return True
        else:
            print("\n⚠️ Webhook sent but got non-200 status")
            return False
    
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection Error!")
        print("Make sure webhook server is running:")
        print("  python bot.py")
        print("  or")
        print("  python webhook_server.py")
        return False
    
    except requests.exceptions.Timeout:
        print("\n❌ Request timeout!")
        return False
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

# ==========================================
# EXTRACT INFO FROM ORDER ID
# ==========================================

def extract_info_from_order_id(order_id):
    """Extract user_id and amount from order_id if possible"""
    parts = order_id.split('-')
    
    info = {
        'user_id': None,
        'timestamp': None,
        'valid': False
    }
    
    if len(parts) >= 3:
        try:
            info['user_id'] = int(parts[1])
            info['timestamp'] = parts[2]
            info['valid'] = True
        except ValueError:
            pass
    
    return info

# ==========================================
# TEST SCENARIOS
# ==========================================

def test_success_payment(user_id, amount, server_key, webhook_url, order_id=None):
    """Test successful payment"""
    payload = create_success_payload(user_id, amount, server_key, order_id)
    result = send_webhook(payload, webhook_url, "Test: Successful Payment")
    
    if result:
        print("\n✅ Expected result:")
        print(f"   - User {user_id} balance should increase by Rp {amount:,}")
        print(f"   - Topup record created with status 'success'")
        print(f"   - Order ID: {payload['order_id']}")
        print("\n🔍 Verify in database:")
        print(f"   SELECT * FROM users WHERE user_id = {user_id};")
        print(f"   SELECT * FROM topups WHERE order_id = '{payload['order_id']}';")
        print("\n💡 Check in Discord:")
        print(f"   /balance")
    
    return result

def test_pending_payment(user_id, amount, server_key, webhook_url, order_id=None):
    """Test pending payment"""
    payload = create_pending_payload(user_id, amount, server_key, order_id)
    result = send_webhook(payload, webhook_url, "Test: Pending Payment")
    
    if result:
        print("\n✅ Expected result:")
        print(f"   - Topup record created with status 'pending'")
        print(f"   - User balance NOT changed")
        print(f"   - Order ID: {payload['order_id']}")
        print("\n🔍 Verify in database:")
        print(f"   SELECT * FROM topups WHERE order_id = '{payload['order_id']}';")
    
    return result

def test_failed_payment(user_id, amount, server_key, webhook_url, order_id=None):
    """Test failed payment"""
    payload = create_failed_payload(user_id, amount, server_key, order_id)
    result = send_webhook(payload, webhook_url, "Test: Failed Payment")
    
    if result:
        print("\n✅ Expected result:")
        print(f"   - Topup record created/updated with status 'failed'")
        print(f"   - User balance NOT changed")
        print(f"   - Order ID: {payload['order_id']}")
        print("\n🔍 Verify in database:")
        print(f"   SELECT * FROM topups WHERE order_id = '{payload['order_id']}';")
    
    return result

def test_existing_order(order_id, amount, server_key, webhook_url):
    """Test with existing order ID from Discord"""
    
    # Extract info from order ID
    info = extract_info_from_order_id(order_id)
    
    if not info['valid']:
        print(f"⚠️ Warning: Order ID format may be invalid: {order_id}")
        print("Expected format: TOPUP-{user_id}-{timestamp}")
        print("Continuing anyway...\n")
    
    user_id = info['user_id'] if info['user_id'] else DEFAULT_USER_ID
    
    print("="*60)
    print("📝 Using Existing Order ID from Discord")
    print("="*60)
    print(f"Order ID: {order_id}")
    print(f"User ID: {user_id}")
    print(f"Amount: Rp {amount:,}")
    print("="*60 + "\n")
    
    # Create success payload with existing order ID
    payload = create_success_payload(user_id, amount, server_key, order_id)
    result = send_webhook(payload, webhook_url, "Test: Existing Order Payment")
    
    if result:
        print("\n✅ Expected result:")
        print(f"   - User {user_id} balance should increase by Rp {amount:,}")
        print(f"   - Topup record updated to 'success'")
        print(f"   - Order ID: {order_id}")
        print("\n🔍 Verify in database:")
        print(f"   SELECT * FROM users WHERE user_id = {user_id};")
        print(f"   SELECT * FROM topups WHERE order_id = '{order_id}';")
        print("\n💡 Check in Discord:")
        print(f"   /balance - Should show +Rp {amount:,}")
    
    return result

def test_double_credit_prevention(user_id, amount, server_key, webhook_url):
    """Test that same payment can't credit twice"""
    print("\n" + "="*60)
    print("🧪 Test: Double Credit Prevention")
    print("="*60)
    print("\nThis test sends the SAME webhook twice to verify")
    print("that balance is only credited once.\n")
    
    # Create payload
    payload = create_success_payload(user_id, amount, server_key)
    order_id = payload['order_id']
    
    # Send first time
    print("\n📤 Sending webhook (1st time)...")
    result1 = send_webhook(payload, webhook_url, "First Payment Notification")
    
    if not result1:
        return False
    
    # Wait a bit
    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Send second time (same payload)
    print("\n📤 Sending webhook (2nd time - DUPLICATE)...")
    result2 = send_webhook(payload, webhook_url, "Duplicate Payment Notification")
    
    print("\n✅ Expected result:")
    print(f"   - First webhook: Balance credited")
    print(f"   - Second webhook: Ignored (already processed)")
    print(f"   - User balance should only increase ONCE")
    print(f"   - Order ID: {order_id}")
    print("\n🔍 Check webhook logs:")
    print("   tail -f logs/bot_order.log | grep 'already processed'")
    
    return result1 and result2

# ==========================================
# HEALTH CHECK
# ==========================================

def check_webhook_health(webhook_url):
    """Check if webhook server is running"""
    health_url = webhook_url.replace('/webhook/midtrans', '/health')
    
    print("="*60)
    print("🏥 Health Check")
    print("="*60)
    print(f"\n📤 Checking: {health_url}")
    
    try:
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            print("\n✅ Webhook server is running!")
            print(f"📥 Response:")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"\n⚠️ Got status code: {response.status_code}")
            return False
    
    except requests.exceptions.ConnectionError:
        print("\n❌ Webhook server is NOT running!")
        print("\nStart the server with:")
        print("  python bot.py")
        print("  or")
        print("  python webhook_server.py")
        return False
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

# ==========================================
# MAIN
# ==========================================

def main():
    parser = argparse.ArgumentParser(description='Test Midtrans webhook notifications')
    
    parser.add_argument('--user', type=int, default=DEFAULT_USER_ID,
                        help=f'Discord user ID (default: {DEFAULT_USER_ID})')
    
    parser.add_argument('--amount', type=int, default=10000,
                        help='Payment amount in Rupiah (default: 10000)')
    
    parser.add_argument('--existing', type=str,
                        help='Use existing order ID from Discord (e.g., TOPUP-123-20241205...)')
    
    parser.add_argument('--success', action='store_true',
                        help='Test successful payment')
    
    parser.add_argument('--pending', action='store_true',
                        help='Test pending payment')
    
    parser.add_argument('--failed', action='store_true',
                        help='Test failed payment')
    
    parser.add_argument('--double', action='store_true',
                        help='Test double credit prevention')
    
    parser.add_argument('--all', action='store_true',
                        help='Run all tests')
    
    parser.add_argument('--health', action='store_true',
                        help='Check webhook server health')
    
    parser.add_argument('--url', type=str, default=DEFAULT_WEBHOOK_URL,
                        help=f'Webhook URL (default: {DEFAULT_WEBHOOK_URL})')
    
    parser.add_argument('--key', type=str,
                        help='Midtrans server key (overrides default)')
    
    args = parser.parse_args()
    
    # Set configuration
    webhook_url = args.url
    server_key = args.key if args.key else DEFAULT_SERVER_KEY
    
    # Validate server key
    if server_key == "SB-Mid-server-YOUR_KEY_HERE":
        print("\n" + "="*60)
        print("⚠️ WARNING: Using default server key!")
        print("="*60)
        print("Please set your actual Midtrans server key:")
        print("  python trigger.py --key SB-Mid-server-YOUR_ACTUAL_KEY")
        print("\nOr edit trigger.py and change DEFAULT_SERVER_KEY variable")
        print("\nContinuing with default key...")
        print("(Signature will be invalid, but you can test webhook flow)")
        print("="*60 + "\n")
        time.sleep(2)
    
    # Print configuration
    print("\n" + "="*60)
    print("⚙️  Configuration")
    print("="*60)
    print(f"Webhook URL: {webhook_url}")
    print(f"Server Key: {server_key[:20]}... (masked)")
    print(f"User ID: {args.user}")
    print(f"Amount: Rp {args.amount:,}")
    if args.existing:
        print(f"Order ID: {args.existing}")
    print("="*60 + "\n")
    
    # Run tests
    success_count = 0
    total_count = 0
    
    # Test existing order ID
    if args.existing:
        if test_existing_order(args.existing, args.amount, server_key, webhook_url):
            success_count += 1
        total_count += 1
        
        # If only existing order test, exit here
        if not any([args.success, args.pending, args.failed, args.double, args.all, args.health]):
            print("\n" + "="*60)
            print("✅ Test Complete!")
            print("="*60)
            return
    
    # Health check
    if args.health or not any([args.success, args.pending, args.failed, args.double, args.all, args.existing]):
        if check_webhook_health(webhook_url):
            success_count += 1
        total_count += 1
        
        if not any([args.success, args.pending, args.failed, args.double, args.all]):
            return
    
    # Run specific tests
    if args.all:
        # Run all tests
        print("\n🧪 Running all tests...\n")
        
        tests = [
            ('Success Payment', lambda: test_success_payment(args.user, args.amount, server_key, webhook_url)),
            ('Pending Payment', lambda: test_pending_payment(args.user, args.amount, server_key, webhook_url)),
            ('Failed Payment', lambda: test_failed_payment(args.user, args.amount, server_key, webhook_url)),
            ('Double Credit Prevention', lambda: test_double_credit_prevention(args.user, args.amount, server_key, webhook_url))
        ]
        
        for test_name, test_func in tests:
            print(f"\n{'='*60}")
            print(f"Running: {test_name}")
            print('='*60)
            
            if test_func():
                success_count += 1
            total_count += 1
            
            # Wait between tests
            if test_name != tests[-1][0]:
                print("\n⏳ Waiting 3 seconds before next test...")
                time.sleep(3)
    
    else:
        # Run individual tests
        if args.success:
            if test_success_payment(args.user, args.amount, server_key, webhook_url):
                success_count += 1
            total_count += 1
        
        if args.pending:
            if test_pending_payment(args.user, args.amount, server_key, webhook_url):
                success_count += 1
            total_count += 1
        
        if args.failed:
            if test_failed_payment(args.user, args.amount, server_key, webhook_url):
                success_count += 1
            total_count += 1
        
        if args.double:
            if test_double_credit_prevention(args.user, args.amount, server_key, webhook_url):
                success_count += 1
            total_count += 1
        
        # If no test specified, run success test by default
        if not any([args.success, args.pending, args.failed, args.double]):
            print("ℹ️  No test specified, running success payment test...\n")
            if test_success_payment(args.user, args.amount, server_key, webhook_url):
                success_count += 1
            total_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    print(f"Total tests: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_count - success_count}")
    
    if success_count == total_count:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed")
    
    print("\n💡 Tips:")
    print("  - Check logs: tail -f logs/bot_order.log")
    print("  - Verify database: SELECT * FROM users; SELECT * FROM topups;")
    print("  - Test in Discord: /balance")
    print("="*60 + "\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()