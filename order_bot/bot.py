"""
Discord Order Bot - Main File with Integrated Webhook Server
=============================================================
Handles user interface, commands, event handling, and payment webhooks
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import threading
import signal
import sys
import config
from database import (
    get_balance, get_user_stats, get_user_orders, init_database
)
from order_manager import (
    validate_order_request, create_new_order, process_order
)
from payment_gateway import create_payment, get_payment_status
from delivery_handler import smart_delivery
from logger import (
    logger, log_bot_startup, log_bot_ready, log_bot_shutdown,
    log_error_with_context
)

# ==========================================
# WEBHOOK SERVER INTEGRATION
# ==========================================

# Global webhook server reference
webhook_server_thread = None
webhook_server_app = None

def start_webhook_server():
    """Start webhook server in background thread"""
    try:
        # Import Flask app from webhook_server
        from webhook_server import app, run_server
        
        global webhook_server_app
        webhook_server_app = app
        
        # Run server in thread
        logger.info(f"🔔 Starting webhook server on port {config.WEBHOOK_PORT}...")
        run_server()
        
    except Exception as e:
        log_error_with_context(e, "start_webhook_server")
        logger.error("❌ Failed to start webhook server")
        logger.error("Make sure webhook_server.py exists and is properly configured")

def start_webhook_thread():
    """Start webhook server in background thread"""
    global webhook_server_thread
    
    webhook_server_thread = threading.Thread(
        target=start_webhook_server,
        daemon=True,
        name="WebhookServer"
    )
    webhook_server_thread.start()
    logger.info("✅ Webhook server thread started")

# ==========================================
# BOT INITIALIZATION
# ==========================================

class OrderBot(commands.Bot):
    """Extended Bot class with startup tasks"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='/',
            intents=intents,
            help_command=None
        )
    
    async def setup_hook(self):
        """Setup hook - runs before bot is ready"""
        # Initialize database
        try:
            init_database()
            logger.info("✅ Database initialized")
        except Exception as e:
            log_error_with_context(e, "database_init")
            raise
        
        # Start webhook server in background
        try:
            start_webhook_thread()
        except Exception as e:
            log_error_with_context(e, "load_webhook_server")
            logger.warning("⚠️ Webhook server not started - payment notifications won't work")
        
        # Load admin commands
        try:
            await self.load_extension('admin_commands')
            logger.info("✅ Admin commands loaded")
        except Exception as e:
            log_error_with_context(e, "load_admin_commands")
        
        # Sync slash commands
        try:
            await self.tree.sync()
            logger.info("✅ Slash commands synced")
        except Exception as e:
            log_error_with_context(e, "sync_commands")

bot = OrderBot()

# ==========================================
# MAIN MENU VIEW
# ==========================================

class MainMenuView(discord.ui.View):
    """Main menu with order and balance buttons"""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    @discord.ui.button(
        label="🛒 Order Codes",
        style=discord.ButtonStyle.green,
        custom_id="order_codes"
    )
    async def order_button(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """Handle order button click"""
        try:
            # Check user balance
            balance = get_balance(interaction.user.id)
            
            # Show package selection
            embed = discord.Embed(
                title="🛒 Select Package",
                description=f"Your balance: **Rp {balance:,}**",
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=PackageSelectView(balance),
                ephemeral=True
            )
            
        except Exception as e:
            log_error_with_context(e, "order_button", user_id=interaction.user.id)
            await interaction.response.send_message(
                "❌ Error processing request. Please try again.",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="💰 Check Balance",
        style=discord.ButtonStyle.blurple,
        custom_id="check_balance"
    )
    async def balance_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle balance check"""
        try:
            stats = get_user_stats(interaction.user.id)
            
            embed = discord.Embed(
                title="💰 Your Account",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="Balance",
                value=f"**Rp {stats['balance']:,}**",
                inline=True
            )
            
            embed.add_field(
                name="Total Orders",
                value=str(stats['total_orders']),
                inline=True
            )
            
            embed.add_field(
                name="Total Spent",
                value=f"Rp {stats['total_spent']:,}",
                inline=True
            )
            
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            
        except Exception as e:
            log_error_with_context(e, "balance_button", user_id=interaction.user.id)
            await interaction.response.send_message(
                "❌ Error checking balance.",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="💳 Top Up",
        style=discord.ButtonStyle.gray,
        custom_id="topup"
    )
    async def topup_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle top up button"""
        try:
            embed = discord.Embed(
                title="💳 Top Up Balance",
                description="Select amount to top up:",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=TopUpView(),
                ephemeral=True
            )
            
        except Exception as e:
            log_error_with_context(e, "topup_button", user_id=interaction.user.id)
            await interaction.response.send_message(
                "❌ Error processing request.",
                ephemeral=True
            )

# ==========================================
# PACKAGE SELECTION VIEW
# ==========================================

class PackageSelectView(discord.ui.View):
    """Package selection with dynamic buttons"""
    
    def __init__(self, user_balance):
        super().__init__(timeout=300)  # 5 min timeout
        self.user_balance = user_balance
        
        # Add button for each package
        for package_key, package_info in config.PACKAGE_CONFIG.items():
            self.add_item(PackageButton(
                package_key=package_key,
                label=package_info['label'],
                price=package_info['price'],
                quantity=package_info['quantity'],
                user_balance=user_balance
            ))

class PackageButton(discord.ui.Button):
    """Individual package button"""
    
    def __init__(self, package_key, label, price, quantity, user_balance):
        # Determine if affordable
        can_afford = user_balance >= price
        
        super().__init__(
            label=f"{label} - Rp {price:,}",
            style=discord.ButtonStyle.green if can_afford else discord.ButtonStyle.gray,
            disabled=not can_afford
        )
        
        self.package_key = package_key
        self.price = price
        self.quantity = quantity
    
    async def callback(self, interaction: discord.Interaction):
        """Handle package selection"""
        try:
            # Validate order
            validation = validate_order_request(
                interaction.user.id,
                self.package_key
            )
            
            if not validation['valid']:
                await interaction.response.send_message(
                    f"❌ {validation['error']}",
                    ephemeral=True
                )
                return
            
            # Show confirmation
            embed = discord.Embed(
                title="✅ Confirm Order",
                description="Please confirm your order:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Package",
                value=f"**{self.quantity}** codes",
                inline=True
            )
            
            embed.add_field(
                name="Price",
                value=f"**Rp {self.price:,}**",
                inline=True
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=OrderConfirmView(self.package_key),
                ephemeral=True
            )
            
        except Exception as e:
            log_error_with_context(e, "package_button", user_id=interaction.user.id)
            await interaction.response.send_message(
                "❌ Error processing selection.",
                ephemeral=True
            )

# ==========================================
# ORDER CONFIRMATION VIEW
# ==========================================

class OrderConfirmView(discord.ui.View):
    """Order confirmation buttons"""
    
    def __init__(self, package_key):
        super().__init__(timeout=60)
        self.package_key = package_key
    
    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle order confirmation"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create order
            result = create_new_order(
                user_id=interaction.user.id,
                package_type=self.package_key,
                payment_method='balance'
            )
            
            if not result['success']:
                await interaction.followup.send(
                    f"❌ Order failed: {result['error']}",
                    ephemeral=True
                )
                return
            
            # Process order (auto delivery)
            async def delivery_wrapper(user_id, order_number, codes):
                return await smart_delivery(
                    bot,
                    user_id,
                    order_number,
                    codes
                )
            
            process_result = await process_order(
                result['order_id'],
                delivery_wrapper
            )
            
            if process_result['success']:
                embed = discord.Embed(
                    title="🎉 Order Successful!",
                    description=f"Order: `{result['order_number']}`",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="Codes",
                    value=str(result['details']['quantity']),
                    inline=True
                )
                
                embed.add_field(
                    name="Delivery",
                    value="Check your DM!",
                    inline=True
                )
                
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"⚠️ Order created but delivery pending: {result['order_number']}",
                    ephemeral=True
                )
            
        except Exception as e:
            log_error_with_context(e, "confirm_order", user_id=interaction.user.id)
            await interaction.followup.send(
                "❌ Error creating order.",
                ephemeral=True
            )
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle cancellation"""
        await interaction.response.send_message(
            "Order cancelled.",
            ephemeral=True
        )

# ==========================================
# TOP UP VIEW
# ==========================================

class TopUpView(discord.ui.View):
    """Top up amount selection"""
    
    def __init__(self):
        super().__init__(timeout=300)
        
        # Add buttons for common amounts
        amounts = [10000, 50000, 100000, 500000, 1000000]
        for amount in amounts:
            self.add_item(TopUpButton(amount))

class TopUpButton(discord.ui.Button):
    """Individual top up button"""
    
    def __init__(self, amount):
        super().__init__(
            label=f"Rp {amount:,}",
            style=discord.ButtonStyle.blurple
        )
        self.amount = amount
    
    async def callback(self, interaction: discord.Interaction):
        """Handle top up selection"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create payment
            payment_result = create_payment(
                user_id=interaction.user.id,
                amount=self.amount
            )
            
            if payment_result['success']:
                embed = discord.Embed(
                    title="💳 Payment Created",
                    description="Scan QR code to pay:",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="Amount",
                    value=f"**Rp {self.amount:,}**",
                    inline=True
                )
                
                embed.add_field(
                    name="Order ID",
                    value=f"`{payment_result['order_id']}`",
                    inline=False
                )
                
                if payment_result.get('qr_url'):
                    embed.set_image(url=payment_result['qr_url'])
                
                embed.set_footer(text="Payment expires in 24 hours")
                
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Payment failed: {payment_result.get('error', 'Unknown error')}",
                    ephemeral=True
                )
            
        except Exception as e:
            log_error_with_context(e, "topup_button", user_id=interaction.user.id)
            await interaction.followup.send(
                "❌ Error creating payment.",
                ephemeral=True
            )

# ==========================================
# SLASH COMMANDS
# ==========================================

@bot.tree.command(name="menu", description="Show main menu")
async def menu_command(interaction: discord.Interaction):
    """Show main menu"""
    try:
        embed = discord.Embed(
            title="🎮 Redfinger Order Bot",
            description="Order Redfinger codes with ease!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🛒 Order Codes",
            value="Purchase Redfinger codes instantly",
            inline=False
        )
        
        embed.add_field(
            name="💰 Balance",
            value="Check your account balance",
            inline=False
        )
        
        embed.add_field(
            name="💳 Top Up",
            value="Add balance to your account",
            inline=False
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=MainMenuView(),
            ephemeral=True
        )
        
    except Exception as e:
        log_error_with_context(e, "menu_command", user_id=interaction.user.id)
        await interaction.response.send_message(
            "❌ Error showing menu.",
            ephemeral=True
        )

@bot.tree.command(name="balance", description="Check your balance")
async def balance_command(interaction: discord.Interaction):
    """Quick balance check"""
    try:
        stats = get_user_stats(interaction.user.id)
        
        await interaction.response.send_message(
            f"💰 Your balance: **Rp {stats['balance']:,}**",
            ephemeral=True
        )
        
    except Exception as e:
        log_error_with_context(e, "balance_command", user_id=interaction.user.id)
        await interaction.response.send_message(
            "❌ Error checking balance.",
            ephemeral=True
        )

@bot.tree.command(name="history", description="View your order history")
async def history_command(interaction: discord.Interaction, limit: int = 5):
    """Show order history"""
    try:
        orders = get_user_orders(interaction.user.id, limit=limit)
        
        if not orders:
            await interaction.response.send_message(
                "📋 You have no orders yet.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📋 Your Order History",
            color=discord.Color.blue()
        )
        
        for order in orders:
            status_emoji = {
                'pending': '⏳',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(order['status'], '❓')
            
            embed.add_field(
                name=f"{status_emoji} {order['order_number']}",
                value=(
                    f"Codes: {order['code_quantity']} | "
                    f"Price: Rp {order['total_price']:,}\n"
                    f"Status: **{order['status']}**"
                ),
                inline=False
            )
        
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )
        
    except Exception as e:
        log_error_with_context(e, "history_command", user_id=interaction.user.id)
        await interaction.response.send_message(
            "❌ Error getting history.",
            ephemeral=True
        )

# ==========================================
# EVENT HANDLERS
# ==========================================

@bot.event
async def on_ready():
    """Bot is ready"""
    log_bot_ready(bot.user)
    
    # Start background tasks
    check_pending_orders.start()
    
    # Send startup message to public channel
    if config.PUBLIC_CHANNEL_ID:
        try:
            channel = bot.get_channel(config.PUBLIC_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="✅ Bot Online",
                    description="Order bot is now ready!",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed)
        except:
            pass

@bot.event
async def on_error(event, *args, **kwargs):
    """Handle errors"""
    import traceback
    
    logger.error(f"Error in {event}")
    traceback.print_exc()

# ==========================================
# BACKGROUND TASKS
# ==========================================

@tasks.loop(minutes=5)
async def check_pending_orders():
    """Check and process pending orders"""
    try:
        from order_manager import process_pending_orders
        
        async def delivery_wrapper(user_id, order_number, codes):
            return await smart_delivery(bot, user_id, order_number, codes)
        
        result = await process_pending_orders(delivery_wrapper, max_orders=5)
        
        if result['processed'] > 0:
            logger.info(
                f"Processed {result['processed']} pending orders "
                f"({result['success']} success, {result['failed']} failed)"
            )
        
    except Exception as e:
        log_error_with_context(e, "check_pending_orders")

# ==========================================
# SHUTDOWN HANDLER
# ==========================================

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("\n🛑 Shutdown signal received...")
    log_bot_shutdown()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ==========================================
# MAIN
# ==========================================

def main():
    """Main entry point"""
    try:
        # Validate config
        if not config.validate_config():
            logger.error("Configuration invalid. Please fix .env file.")
            return
        
        # Print config
        config.print_config()
        
        # Start bot
        log_bot_startup()
        logger.info("🔔 Webhook server will start automatically...")
        bot.run(config.DISCORD_TOKEN)
        
    except KeyboardInterrupt:
        log_bot_shutdown()
    except Exception as e:
        log_error_with_context(e, "main")
        raise

if __name__ == '__main__':
    main()