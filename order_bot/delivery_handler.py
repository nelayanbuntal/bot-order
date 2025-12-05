"""
Delivery Handler
================
Handles code delivery via DM, channel, or file with retry logic
"""

import discord
import asyncio
from datetime import datetime
import io
import config
from database import get_db_connection, dict_cursor
from logger import (
    logger, log_error_with_context, log_delivery_success, log_delivery_failed
)

# ==========================================
# DELIVERY METHODS
# ==========================================

async def deliver_via_dm(bot, user_id, order_number, codes):
    """
    Deliver codes via Direct Message
    
    Args:
        bot: Discord bot instance
        user_id: User ID to send to
        order_number: Order number
        codes: List of code dicts with 'code' key
    
    Returns:
        dict: {'success': bool, 'method': 'dm', 'error': str or None}
    """
    try:
        # Get user
        user = await bot.fetch_user(user_id)
        if not user:
            return {
                'success': False,
                'method': 'dm',
                'error': "User not found"
            }
        
        # Create embed
        embed = discord.Embed(
            title="🎉 Your Redfinger Codes",
            description=f"Order: `{order_number}`\nQuantity: **{len(codes)}** codes",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.set_footer(text="Thank you for your order!")
        
        # Send codes
        code_list = "\n".join([f"`{code['code']}`" for code in codes])
        
        # Split if too long (Discord limit: 4096 chars per field)
        if len(code_list) > 4000:
            # Send as file instead
            return await deliver_via_file(bot, user_id, order_number, codes, channel=None)
        
        embed.add_field(
            name="Your Codes:",
            value=code_list,
            inline=False
        )
        
        embed.add_field(
            name="📝 How to Use:",
            value="1. Copy the code\n2. Open Redfinger app\n3. Go to Redeem section\n4. Paste and redeem",
            inline=False
        )
        
        # Try to send
        try:
            await user.send(embed=embed)
            
            # Record delivery
            record_delivery(order_number, user_id, 'dm', 'success')
            log_delivery_success(order_number, user_id, 'dm', len(codes))
            
            return {
                'success': True,
                'method': 'dm',
                'error': None
            }
            
        except discord.Forbidden:
            # User has DMs closed
            return {
                'success': False,
                'method': 'dm',
                'error': "User has DMs disabled. Cannot send codes."
            }
        
    except Exception as e:
        log_error_with_context(e, "deliver_via_dm", user_id=user_id, order=order_number)
        return {
            'success': False,
            'method': 'dm',
            'error': str(e)
        }

async def deliver_via_channel(bot, user_id, order_number, codes, channel_id=None):
    """
    Deliver codes via channel (ephemeral or in dedicated channel)
    
    Args:
        bot: Discord bot instance
        user_id: User ID
        order_number: Order number
        codes: List of code dicts
        channel_id: Channel ID to send to (optional)
    
    Returns:
        dict: {'success': bool, 'method': 'channel', 'error': str or None}
    """
    try:
        # Use public channel if not specified
        if not channel_id:
            channel_id = config.PUBLIC_CHANNEL_ID
        
        channel = bot.get_channel(channel_id)
        if not channel:
            return {
                'success': False,
                'method': 'channel',
                'error': "Channel not found"
            }
        
        # Create embed (mention user)
        embed = discord.Embed(
            title="🎉 Order Completed",
            description=f"Order for <@{user_id}>: `{order_number}`\nQuantity: **{len(codes)}** codes",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Send codes as file (for privacy in public channel)
        code_text = "\n".join([code['code'] for code in codes])
        file = discord.File(
            io.StringIO(code_text),
            filename=f"codes_{order_number}.txt"
        )
        
        embed.add_field(
            name="📥 Download",
            value="Your codes are in the attached file.",
            inline=False
        )
        
        embed.set_footer(text="Codes will be deleted after 10 minutes")
        
        # Send message
        msg = await channel.send(
            content=f"<@{user_id}>",
            embed=embed,
            file=file
        )
        
        # Delete after 10 minutes
        if config.AUTO_CLOSE_AFTER_COMPLETION:
            await asyncio.sleep(600)  # 10 minutes
            try:
                await msg.delete()
            except:
                pass
        
        # Record delivery
        record_delivery(order_number, user_id, 'channel', 'success')
        log_delivery_success(order_number, user_id, 'channel', len(codes))
        
        return {
            'success': True,
            'method': 'channel',
            'error': None
        }
        
    except Exception as e:
        log_error_with_context(e, "deliver_via_channel", user_id=user_id, order=order_number)
        return {
            'success': False,
            'method': 'channel',
            'error': str(e)
        }

async def deliver_via_file(bot, user_id, order_number, codes, channel=None):
    """
    Deliver codes as downloadable file
    
    Args:
        bot: Discord bot instance
        user_id: User ID
        order_number: Order number
        codes: List of code dicts
        channel: Channel to send to (if None, send via DM)
    
    Returns:
        dict: {'success': bool, 'method': 'file', 'error': str or None}
    """
    try:
        # Create file content
        code_text = f"Redfinger Codes - Order: {order_number}\n"
        code_text += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        code_text += f"Quantity: {len(codes)} codes\n"
        code_text += "="*50 + "\n\n"
        
        for idx, code in enumerate(codes, 1):
            code_text += f"{idx}. {code['code']}\n"
        
        code_text += "\n" + "="*50 + "\n"
        code_text += "How to use:\n"
        code_text += "1. Copy a code from above\n"
        code_text += "2. Open Redfinger app\n"
        code_text += "3. Go to Redeem section\n"
        code_text += "4. Paste and redeem the code\n"
        
        # Create file
        file = discord.File(
            io.StringIO(code_text),
            filename=f"redfinger_codes_{order_number}.txt"
        )
        
        # Create embed
        embed = discord.Embed(
            title="🎉 Your Redfinger Codes",
            description=f"Order: `{order_number}`\nQuantity: **{len(codes)}** codes",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📥 File Attached",
            value="Download the file to view your codes.",
            inline=False
        )
        
        embed.set_footer(text="Keep your codes safe!")
        
        # Send to channel or DM
        if channel:
            await channel.send(
                content=f"<@{user_id}>",
                embed=embed,
                file=file
            )
        else:
            user = await bot.fetch_user(user_id)
            await user.send(embed=embed, file=file)
        
        # Record delivery
        record_delivery(order_number, user_id, 'file', 'success')
        log_delivery_success(order_number, user_id, 'file', len(codes))
        
        return {
            'success': True,
            'method': 'file',
            'error': None
        }
        
    except Exception as e:
        log_error_with_context(e, "deliver_via_file", user_id=user_id, order=order_number)
        return {
            'success': False,
            'method': 'file',
            'error': str(e)
        }

# ==========================================
# SMART DELIVERY (Auto-select best method)
# ==========================================

async def smart_delivery(bot, user_id, order_number, codes):
    """
    Automatically choose best delivery method
    
    Priority:
    1. DM (if user has DMs open and codes fit)
    2. File via DM (if codes are too many)
    3. Channel (if DM fails)
    
    Returns:
        dict: {'success': bool, 'method': str, 'error': str or None}
    """
    try:
        # Try DM first
        if len(codes) <= 10:  # Small order, try direct DM
            result = await deliver_via_dm(bot, user_id, order_number, codes)
            if result['success']:
                return result
        
        # Try file via DM
        try:
            result = await deliver_via_file(bot, user_id, order_number, codes, channel=None)
            if result['success']:
                return result
        except discord.Forbidden:
            pass  # DMs closed, try channel
        
        # Fallback to channel
        result = await deliver_via_channel(bot, user_id, order_number, codes)
        return result
        
    except Exception as e:
        log_error_with_context(e, "smart_delivery", user_id=user_id, order=order_number)
        return {
            'success': False,
            'method': 'auto',
            'error': str(e)
        }

# ==========================================
# DELIVERY WITH RETRY
# ==========================================

async def deliver_with_retry(bot, user_id, order_number, codes, max_attempts=None):
    """
    Deliver codes with retry logic
    
    Args:
        bot: Discord bot instance
        user_id: User ID
        order_number: Order number
        codes: List of code dicts
        max_attempts: Max retry attempts (default from config)
    
    Returns:
        dict: {'success': bool, 'attempts': int, 'method': str, 'error': str or None}
    """
    if max_attempts is None:
        max_attempts = config.DELIVERY_RETRY_ATTEMPTS
    
    attempts = 0
    last_error = None
    
    while attempts < max_attempts:
        attempts += 1
        
        logger.info(f"Delivery attempt {attempts}/{max_attempts} for order {order_number}")
        
        # Get delivery method from config
        method = config.DELIVERY_METHOD
        
        # Try delivery
        if method == 'dm':
            result = await deliver_via_dm(bot, user_id, order_number, codes)
        elif method == 'channel':
            result = await deliver_via_channel(bot, user_id, order_number, codes)
        elif method == 'file':
            result = await deliver_via_file(bot, user_id, order_number, codes)
        else:
            # Auto/smart delivery
            result = await smart_delivery(bot, user_id, order_number, codes)
        
        if result['success']:
            return {
                'success': True,
                'attempts': attempts,
                'method': result['method'],
                'error': None
            }
        
        last_error = result['error']
        
        # Wait before retry
        if attempts < max_attempts:
            wait_time = attempts * 5  # Progressive delay
            logger.warning(f"Delivery failed, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
    
    # All attempts failed
    log_delivery_failed(order_number, user_id, method, last_error)
    record_delivery(order_number, user_id, method, 'failed', last_error)
    
    return {
        'success': False,
        'attempts': attempts,
        'method': method,
        'error': last_error
    }

# ==========================================
# DELIVERY TRACKING
# ==========================================

def record_delivery(order_number, user_id, method, status, error_message=None):
    """
    Record delivery attempt in database
    
    Args:
        order_number: Order number
        user_id: User ID
        method: Delivery method used
        status: 'success' or 'failed'
        error_message: Error message if failed
    """
    try:
        from database import get_order_by_number
        
        # Get order ID
        order = get_order_by_number(order_number)
        if not order:
            logger.warning(f"Order not found for delivery record: {order_number}")
            return
        
        order_id = order['id']
        
        # Insert delivery record
        with get_db_connection() as conn:
            cursor = dict_cursor(conn)
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO deliveries (order_id, user_id, delivery_method, status, error_message)
                    VALUES (%s, %s, %s, %s, %s)
                """, (order_id, user_id, method, status, error_message))
            else:
                cursor.execute("""
                    INSERT INTO deliveries (order_id, user_id, delivery_method, status, error_message)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, user_id, method, status, error_message))
        
    except Exception as e:
        log_error_with_context(e, "record_delivery", order=order_number)

def get_delivery_history(order_id):
    """
    Get delivery history for an order
    
    Returns:
        list: List of delivery attempt dicts
    """
    try:
        with get_db_connection(commit=False) as conn:
            cursor = dict_cursor(conn)
            
            if config.DATABASE_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT * FROM deliveries
                    WHERE order_id = %s
                    ORDER BY created_at DESC
                """, (order_id,))
            else:
                cursor.execute("""
                    SELECT * FROM deliveries
                    WHERE order_id = ?
                    ORDER BY created_at DESC
                """, (order_id,))
            
            rows = cursor.fetchall()
            
            if isinstance(rows[0], dict) if rows else False:
                return [dict(row) for row in rows]
            else:
                # Convert to dict
                return [
                    dict(zip([d[0] for d in cursor.description], row))
                    for row in rows
                ]
        
    except Exception as e:
        log_error_with_context(e, "get_delivery_history", order_id=order_id)
        return []

# ==========================================
# NOTIFICATION HELPERS
# ==========================================

async def notify_delivery_success(bot, user_id, order_number, code_count):
    """
    Send delivery success notification
    """
    try:
        if not config.NOTIFY_USER_ON_DELIVERY:
            return
        
        user = await bot.fetch_user(user_id)
        
        embed = discord.Embed(
            title="✅ Delivery Successful",
            description=f"Your order `{order_number}` has been delivered!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Codes Delivered",
            value=f"**{code_count}** codes",
            inline=True
        )
        
        embed.add_field(
            name="Check Your",
            value="Direct Messages",
            inline=True
        )
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass  # User has DMs closed
        
    except Exception as e:
        log_error_with_context(e, "notify_delivery_success")

async def notify_delivery_failed(bot, user_id, order_number, reason):
    """
    Send delivery failure notification
    """
    try:
        user = await bot.fetch_user(user_id)
        
        embed = discord.Embed(
            title="⚠️ Delivery Issue",
            description=f"There was a problem delivering your order `{order_number}`",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )
        
        embed.add_field(
            name="What to do?",
            value="Please contact an admin for manual delivery.",
            inline=False
        )
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass
        
    except Exception as e:
        log_error_with_context(e, "notify_delivery_failed")

# ==========================================
# ADMIN NOTIFICATIONS
# ==========================================

async def notify_admin_delivery_failed(bot, order_number, user_id, reason):
    """
    Notify admin about delivery failure
    """
    try:
        if not config.NOTIFY_ADMIN_ON_ORDER:
            return
        
        for admin_id in config.STOCK_ADMIN_USER_IDS:
            try:
                admin = await bot.fetch_user(admin_id)
                
                embed = discord.Embed(
                    title="🚨 Delivery Failed",
                    description=f"Manual intervention required",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(name="Order", value=f"`{order_number}`", inline=True)
                embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
                embed.add_field(name="Reason", value=reason, inline=False)
                
                embed.add_field(
                    name="Action Required",
                    value="Please deliver codes manually using `/admin processorder`",
                    inline=False
                )
                
                await admin.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
    except Exception as e:
        log_error_with_context(e, "notify_admin_delivery_failed")

# ==========================================
# EXPORT
# ==========================================

__all__ = [
    'deliver_via_dm',
    'deliver_via_channel',
    'deliver_via_file',
    'smart_delivery',
    'deliver_with_retry',
    'record_delivery',
    'get_delivery_history',
    'notify_delivery_success',
    'notify_delivery_failed',
    'notify_admin_delivery_failed',
]
