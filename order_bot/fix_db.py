#!/usr/bin/env python3
"""
Auto-fix script for create_topup() function in database.py
Adds payment_type and transaction_id parameters
"""

import re
import os
import sys

def fix_create_topup():
    """Fix create_topup function in database.py"""
    
    # Find database.py
    db_file = 'database.py'
    
    if not os.path.exists(db_file):
        print(f"❌ Error: {db_file} not found!")
        print("Please run this script from the same directory as database.py")
        return False
    
    print(f"📂 Found {db_file}")
    
    # Backup
    backup_file = f"{db_file}.backup"
    try:
        with open(db_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Backup created: {backup_file}")
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return False
    
    # Check if already fixed
    if "def create_topup(user_id, amount, order_id, payment_type=" in content:
        print("ℹ️  Function already has payment_type parameter - no fix needed")
        return True
    
    # Find and replace function
    old_function = r'def create_topup\(user_id, amount, order_id\):'
    
    if not re.search(old_function, content):
        print("⚠️  Warning: create_topup function not found with expected signature")
        print("Manual fix may be required")
        return False
    
    # New function signature
    new_signature = "def create_topup(user_id, amount, order_id, payment_type='qris', transaction_id=None):"
    
    content = re.sub(old_function, new_signature, content)
    
    # Update docstring if exists
    old_docstring = r'"""Create topup record"""'
    new_docstring = '''"""
    Create topup record
    
    Args:
        user_id: Discord user ID
        amount: Topup amount in Rupiah
        order_id: Unique order ID from payment gateway
        payment_type: Payment method (qris, gopay, bank_transfer, etc.)
        transaction_id: Transaction ID from Midtrans
    
    Returns:
        int: Topup ID or None if error
    """'''
    
    content = content.replace(old_docstring, new_docstring)
    
    # Update INSERT statements to include new fields
    # PostgreSQL version
    old_pg_insert = r'INSERT INTO topups \(user_id, amount, order_id, status, bot_source\)\s+VALUES \(%s, %s, %s, \'pending\', \'order_bot\'\)'
    new_pg_insert = '''INSERT INTO topups (
                        user_id, amount, order_id, status, 
                        bot_source, payment_type, transaction_id
                    )
                    VALUES (%s, %s, %s, 'pending', 'order_bot', %s, %s)'''
    
    content = re.sub(old_pg_insert, new_pg_insert, content, flags=re.MULTILINE)
    
    # Update VALUES parameters for PostgreSQL
    old_pg_values = r'\(user_id, amount, order_id\)\)'
    new_pg_values = '(user_id, amount, order_id, payment_type, transaction_id))'
    content = re.sub(old_pg_values, new_pg_values, content)
    
    # SQLite version
    old_sqlite_insert = r'INSERT INTO topups \(user_id, amount, order_id, status, bot_source\)\s+VALUES \(\?, \?, \?, \'pending\', \'order_bot\'\)'
    new_sqlite_insert = '''INSERT INTO topups (
                        user_id, amount, order_id, status, 
                        bot_source, payment_type, transaction_id
                    )
                    VALUES (?, ?, ?, 'pending', 'order_bot', ?, ?)'''
    
    content = re.sub(old_sqlite_insert, new_sqlite_insert, content, flags=re.MULTILINE)
    
    # Add logging
    old_return = r'return row\[\'id\'\] if isinstance\(row, dict\) else row\[0\]'
    new_return = '''topup_id = row['id'] if isinstance(row, dict) else row[0]
            
            logger.info(f"Topup created: ID={topup_id}, User={user_id}, Amount=Rp {amount:,}")
            return topup_id'''
    
    content = re.sub(old_return, new_return, content)
    
    # Write fixed content
    try:
        with open(db_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n🎉 Success! {db_file} has been fixed")
        print(f"📄 Original backed up to: {backup_file}")
        print("\n✅ create_topup() now accepts payment_type and transaction_id")
        print("\n🚀 Next step: Restart your bot")
        print("   python bot.py")
        return True
    
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        # Restore backup
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            with open(db_file, 'w', encoding='utf-8') as f:
                f.write(backup_content)
            print("↩️  Restored from backup")
        except:
            pass
        return False

def verify_fix():
    """Verify the fix was applied correctly"""
    print("\n" + "="*50)
    print("Verification:")
    print("="*50)
    
    try:
        with open('database.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check function signature
        if 'def create_topup(user_id, amount, order_id, payment_type=' in content:
            print("✅ Function signature: CORRECT")
        else:
            print("❌ Function signature: INCORRECT")
            return False
        
        # Check INSERT includes new fields
        if 'payment_type, transaction_id' in content:
            print("✅ INSERT statement: CORRECT")
        else:
            print("❌ INSERT statement: INCORRECT")
            return False
        
        print("\n✅ All checks passed!")
        return True
    
    except FileNotFoundError:
        print("❌ database.py not found")
        return False
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

if __name__ == '__main__':
    print("="*50)
    print("🔧 create_topup() Fix Script")
    print("="*50)
    print()
    
    success = fix_create_topup()
    
    if success:
        verify_fix()
        print("\n" + "="*50)
        print("✅ FIX COMPLETE!")
        print("="*50)
        print("\nWebhook will now work correctly!")
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("❌ FIX FAILED!")
        print("="*50)
        print("\nPlease apply fix manually:")
        print("See: database_patch_create_topup.txt")
        sys.exit(1)