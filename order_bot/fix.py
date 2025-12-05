#!/usr/bin/env python3
"""
Auto-fix script for PBKDF2 import error in stock_manager.py
Usage: python fix_pbkdf2_error.py
"""

import os
import sys
import re
from pathlib import Path

def fix_stock_manager():
    """Fix PBKDF2 import error in stock_manager.py"""
    
    # Find stock_manager.py
    possible_paths = [
        'stock_manager.py',
        'order_bot/stock_manager.py',
        '../stock_manager.py',
        './stock_manager.py'
    ]
    
    stock_manager_path = None
    for path in possible_paths:
        if os.path.exists(path):
            stock_manager_path = path
            break
    
    if not stock_manager_path:
        print("❌ Error: stock_manager.py not found!")
        print("Please run this script from the same directory as stock_manager.py")
        return False
    
    print(f"📂 Found stock_manager.py at: {stock_manager_path}")
    
    # Backup original
    backup_path = f"{stock_manager_path}.backup"
    try:
        with open(stock_manager_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        
        print(f"✅ Backup created: {backup_path}")
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return False
    
    # Apply fixes
    content = original_content
    changes_made = 0
    
    # Fix 1: Import statement
    old_import = r'from cryptography\.hazmat\.primitives\.kdf\.pbkdf2 import PBKDF2\b'
    new_import = 'from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC'
    
    if re.search(old_import, content):
        content = re.sub(old_import, new_import, content)
        changes_made += 1
        print("✅ Fixed import statement: PBKDF2 → PBKDF2HMAC")
    else:
        print("ℹ️  Import already correct or not found")
    
    # Fix 2: Class usage
    old_class = r'\bPBKDF2\('
    new_class = 'PBKDF2HMAC('
    
    matches = re.findall(old_class, content)
    if matches:
        content = re.sub(old_class, new_class, content)
        changes_made += len(matches)
        print(f"✅ Fixed {len(matches)} class usage(s): PBKDF2( → PBKDF2HMAC(")
    else:
        print("ℹ️  Class usage already correct or not found")
    
    # Write fixed content
    if changes_made > 0:
        try:
            with open(stock_manager_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"\n🎉 Success! Made {changes_made} fix(es)")
            print(f"📄 Original backed up to: {backup_path}")
            print("\n✅ stock_manager.py is now fixed!")
            print("\n🚀 Next step: Restart your bot")
            print("   python bot.py")
            return True
        except Exception as e:
            print(f"❌ Error writing file: {e}")
            # Restore backup
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                with open(stock_manager_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)
                print("↩️  Restored from backup")
            except:
                pass
            return False
    else:
        print("\nℹ️  No changes needed - file already correct!")
        return True

def verify_fix():
    """Verify the fix was applied correctly"""
    print("\n" + "="*50)
    print("Verification:")
    print("="*50)
    
    try:
        with open('stock_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check import
        if 'from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC' in content:
            print("✅ Import statement: CORRECT")
        else:
            print("❌ Import statement: INCORRECT")
            return False
        
        # Check class usage
        if 'kdf = PBKDF2HMAC(' in content:
            print("✅ Class usage: CORRECT")
        else:
            print("❌ Class usage: INCORRECT")
            return False
        
        # Check no old references remain
        old_refs = re.findall(r'\bPBKDF2\(', content)
        if old_refs:
            print(f"⚠️  Warning: Found {len(old_refs)} old PBKDF2( reference(s)")
            print("    These should be PBKDF2HMAC(")
            return False
        
        print("\n✅ All checks passed!")
        return True
    
    except FileNotFoundError:
        print("❌ stock_manager.py not found")
        return False
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

if __name__ == '__main__':
    print("="*50)
    print("🔧 PBKDF2 Import Error Fix Script")
    print("="*50)
    print()
    
    # Run fix
    success = fix_stock_manager()
    
    if success:
        # Verify
        verify_fix()
        print("\n" + "="*50)
        print("✅ FIX COMPLETE!")
        print("="*50)
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("❌ FIX FAILED!")
        print("="*50)
        print("\nPlease fix manually:")
        print("1. Open stock_manager.py")
        print("2. Change: import PBKDF2 → import PBKDF2HMAC")
        print("3. Change: kdf = PBKDF2( → kdf = PBKDF2HMAC(")
        sys.exit(1)