"""
Admin Commands
==============
Discord slash commands for administrators
"""

import discord
from discord import app_commands
from discord.ext import commands
import io
from datetime import datetime
import config
from database import (
    get_balance, add_balance, deduct_balance, get_user_stats,
    get_available_stock_count, get_user_orders, get_order_by_number,
    get_database_stats, update_order_status
)
from stock_manager import (
    add_codes_from_text, get_stock_summary, get_detailed_stock_stats,
    check_stock_alert, get_available_codes
)
from order_manager import get_order_statistics, process_order
from delivery_handler import deliver_with_retry
from logger import logger, log_admin_action, log_error_with_context

# ==========================================
# ADMIN CHECK
# ==========================================

def is_admin():
    """Decorator to check if user is admin"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Check if user has admin role
        if interaction.guild:
            admin_role = discord.utils.get(interaction.guild.roles, name=config.ADMIN_ROLE_NAME)
            if admin_role in interaction.user.roles:
                return True
        
        # Check if user is in STOCK_ADMIN_USER_IDS
        if interaction.user.id in config.STOCK_ADMIN_USER_IDS:
            return True
        
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
        return False
    
    return app_commands.check(predicate)

# ==========================================
# ADMIN COMMAND GROUP
# ==========================================

class AdminCommands(commands.GroupCog, name="admin"):
    """Admin commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
        super().__init__()
    
    # ==========================================
    # STOCK MANAGEMENT
    # ==========================================
    
    @app_commands.command(name="addstock", description="Add codes to stock (upload .txt file)")
    @is_admin()
    async def addstock(self, interaction: discord.Interaction, file: discord.Attachment):
        """Add codes from uploaded file"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check file extension
            if not file.filename.endswith('.txt'):
                await interaction.followup.send(
                    "❌ Please upload a .txt file with one code per line.",
                    ephemeral=True
                )
                return
            
            # Check file size (max 1MB)
            if file.size > 1048576:
                await interaction.followup.send(
                    "❌ File too large. Maximum size: 1MB",
                    ephemeral=True
                )
                return
            
            # Download and read file
            content = await file.read()
            text_content = content.decode('utf-8')
            
            # Add codes
            result = add_codes_from_text(
                text_content=text_content,
                code_type='redfinger',
                added_by=interaction.user.id
            )
            
            # Create response embed
            embed = discord.Embed(
                title="📥 Stock Addition Results",
                color=discord.Color.green() if result['success'] else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="✅ Added",
                value=f"**{result['added']}** codes",
                inline=True
            )
            
            embed.add_field(
                name="❌ Failed",
                value=f"**{result['failed']}** codes",
                inline=True
            )
            
            # Show available stock
            available = get_available_stock_count()
            embed.add_field(
                name="📊 Total Available",
                value=f"**{available}** codes",
                inline=True
            )
            
            # Show errors if any
            if result['errors']:
                error_text = "\n".join([
                    f"Line {err['line']}: {err['error']}"
                    for err in result['errors'][:5]  # Show first 5 errors
                ])
                if len(result['errors']) > 5:
                    error_text += f"\n... and {len(result['errors']) - 5} more errors"
                
                embed.add_field(
                    name="⚠️ Errors",
                    value=f"```{error_text}```",
                    inline=False
                )
            
            embed.set_footer(text=f"Added by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log action
            log_admin_action(
                interaction.user.id,
                "addstock",
                f"Added {result['added']} codes"
            )
            
            # Check stock alert
            alert = check_stock_alert()
            if alert['alert']:
                await interaction.followup.send(
                    f"⚠️ **Low Stock Alert**: Only {alert['available']} codes left!",
                    ephemeral=True
                )
            
        except Exception as e:
            log_error_with_context(e, "admin_addstock", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error adding stock: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="viewstock", description="View current stock status")
    @is_admin()
    async def viewstock(self, interaction: discord.Interaction):
        """View stock statistics"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            stats = get_detailed_stock_stats()
            
            embed = discord.Embed(
                title="📊 Stock Status",
                color=discord.Color.green() if stats['status'] == 'healthy' else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            # Overall stats
            totals = stats['totals']
            embed.add_field(
                name="📦 Total Codes",
                value=f"**{totals['total']:,}**",
                inline=True
            )
            
            embed.add_field(
                name="✅ Available",
                value=f"**{totals['available']:,}**",
                inline=True
            )
            
            embed.add_field(
                name="🔒 Reserved",
                value=f"**{totals['reserved']:,}**",
                inline=True
            )
            
            embed.add_field(
                name="✔️ Used",
                value=f"**{totals['used']:,}**",
                inline=True
            )
            
            embed.add_field(
                name="📈 Utilization",
                value=f"**{totals['utilization_rate']:.1f}%**",
                inline=True
            )
            
            embed.add_field(
                name="🚦 Status",
                value=f"**{stats['status'].upper()}**",
                inline=True
            )
            
            # By type breakdown
            if stats['by_type']:
                type_text = ""
                for code_type, type_stats in stats['by_type'].items():
                    type_text += f"**{code_type}**:\n"
                    type_text += f"  Total: {type_stats['total']:,} | "
                    type_text += f"Available: {type_stats['available']:,}\n"
                
                embed.add_field(
                    name="📋 By Type",
                    value=type_text,
                    inline=False
                )
            
            # Low stock warning
            if stats['low_stock']:
                embed.add_field(
                    name="⚠️ Warning",
                    value=f"Stock is below threshold ({config.LOW_STOCK_THRESHOLD} codes)",
                    inline=False
                )
            
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            log_error_with_context(e, "admin_viewstock", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error viewing stock: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="exportstock", description="Export available codes to file")
    @is_admin()
    async def exportstock(self, interaction: discord.Interaction, limit: int = 100):
        """Export stock codes"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get codes
            codes = get_available_codes(limit=limit)
            
            if not codes:
                await interaction.followup.send(
                    "❌ No codes available to export.",
                    ephemeral=True
                )
                return
            
            # Create file content
            code_text = f"Redfinger Stock Export\n"
            code_text += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            code_text += f"Count: {len(codes)} codes\n"
            code_text += "="*50 + "\n\n"
            
            for idx, code in enumerate(codes, 1):
                code_text += f"{code['code']}\n"
            
            # Create file
            file = discord.File(
                io.StringIO(code_text),
                filename=f"stock_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            
            embed = discord.Embed(
                title="📥 Stock Export",
                description=f"Exported **{len(codes)}** codes",
                color=discord.Color.blue()
            )
            
            embed.set_footer(text=f"Exported by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
            log_admin_action(interaction.user.id, "exportstock", f"Exported {len(codes)} codes")
            
        except Exception as e:
            log_error_with_context(e, "admin_exportstock", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error exporting stock: {str(e)}",
                ephemeral=True
            )
    
    # ==========================================
    # ORDER MANAGEMENT
    # ==========================================
    
    @app_commands.command(name="vieworders", description="View recent orders")
    @is_admin()
    async def vieworders(
        self, 
        interaction: discord.Interaction,
        status: str = None,
        limit: int = 10
    ):
        """View orders with optional status filter"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from database import get_db_connection, dict_cursor
            
            with get_db_connection(commit=False) as conn:
                cursor = dict_cursor(conn)
                
                if status:
                    if config.DATABASE_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT order_number, user_id, code_quantity, total_price, status, created_at
                            FROM orders
                            WHERE status = %s
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (status, limit))
                    else:
                        cursor.execute("""
                            SELECT order_number, user_id, code_quantity, total_price, status, created_at
                            FROM orders
                            WHERE status = ?
                            ORDER BY created_at DESC
                            LIMIT ?
                        """, (status, limit))
                else:
                    if config.DATABASE_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT order_number, user_id, code_quantity, total_price, status, created_at
                            FROM orders
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (limit,))
                    else:
                        cursor.execute("""
                            SELECT order_number, user_id, code_quantity, total_price, status, created_at
                            FROM orders
                            ORDER BY created_at DESC
                            LIMIT ?
                        """, (limit,))
                
                rows = cursor.fetchall()
            
            if not rows:
                await interaction.followup.send(
                    f"❌ No orders found{' with status: ' + status if status else ''}.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"📦 Recent Orders{' (' + status + ')' if status else ''}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for row in rows[:10]:  # Show max 10
                if isinstance(row, dict):
                    order_data = row
                else:
                    order_data = dict(zip([d[0] for d in cursor.description], row))
                
                status_emoji = {
                    'pending': '⏳',
                    'completed': '✅',
                    'failed': '❌',
                    'cancelled': '🚫'
                }.get(order_data['status'], '❓')
                
                embed.add_field(
                    name=f"{status_emoji} {order_data['order_number']}",
                    value=(
                        f"User: <@{order_data['user_id']}>\n"
                        f"Codes: {order_data['code_quantity']} | "
                        f"Price: Rp {order_data['total_price']:,}\n"
                        f"Status: **{order_data['status']}**"
                    ),
                    inline=False
                )
            
            if len(rows) > 10:
                embed.set_footer(text=f"Showing 10 of {len(rows)} orders")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            log_error_with_context(e, "admin_vieworders", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error viewing orders: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="processorder", description="Manually process/deliver order")
    @is_admin()
    async def processorder(self, interaction: discord.Interaction, order_number: str):
        """Manually process an order"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get order
            order = get_order_by_number(order_number)
            if not order:
                await interaction.followup.send(
                    f"❌ Order not found: `{order_number}`",
                    ephemeral=True
                )
                return
            
            # Check if already completed
            if order['status'] == 'completed':
                await interaction.followup.send(
                    f"✅ Order already completed: `{order_number}`",
                    ephemeral=True
                )
                return
            
            await interaction.followup.send(
                f"⏳ Processing order `{order_number}`...",
                ephemeral=True
            )
            
            # Process order with delivery
            from delivery_handler import smart_delivery
            
            async def delivery_wrapper(user_id, order_number, codes):
                return await smart_delivery(self.bot, user_id, order_number, codes)
            
            result = await process_order(order['id'], delivery_wrapper)
            
            if result['success'] and result.get('delivered'):
                embed = discord.Embed(
                    title="✅ Order Processed Successfully",
                    description=f"Order: `{order_number}`",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="User", value=f"<@{order['user_id']}>", inline=True)
                embed.add_field(name="Codes", value=str(order['code_quantity']), inline=True)
                embed.add_field(name="Method", value=result.get('method', 'N/A'), inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                log_admin_action(
                    interaction.user.id,
                    "processorder",
                    f"Processed {order_number}"
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to process order: {result.get('error', 'Unknown error')}",
                    ephemeral=True
                )
            
        except Exception as e:
            log_error_with_context(e, "admin_processorder", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error processing order: {str(e)}",
                ephemeral=True
            )
    
    # ==========================================
    # USER MANAGEMENT
    # ==========================================
    
    @app_commands.command(name="checkuser", description="Check user details and balance")
    @is_admin()
    async def checkuser(self, interaction: discord.Interaction, user: discord.User):
        """Check user information"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            stats = get_user_stats(user.id)
            
            embed = discord.Embed(
                title=f"👤 User Information",
                description=f"{user.mention} ({user.name})",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            # Balance
            embed.add_field(
                name="💰 Balance",
                value=f"**Rp {stats['balance']:,}**",
                inline=True
            )
            
            embed.add_field(
                name="📥 Total Top Up",
                value=f"Rp {stats['total_topup']:,}",
                inline=True
            )
            
            embed.add_field(
                name="📤 Total Spent",
                value=f"Rp {stats['total_spent']:,}",
                inline=True
            )
            
            # Orders
            embed.add_field(
                name="📦 Total Orders",
                value=str(stats['total_orders']),
                inline=True
            )
            
            embed.add_field(
                name="✅ Completed",
                value=str(stats['completed_orders']),
                inline=True
            )
            
            embed.add_field(
                name="⏳ Pending",
                value=str(stats['pending_orders']),
                inline=True
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            log_error_with_context(e, "admin_checkuser", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error checking user: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="addbalance", description="Add balance to user")
    @is_admin()
    async def addbalance(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        amount: int
    ):
        """Add balance to user account"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if amount <= 0:
                await interaction.followup.send(
                    "❌ Amount must be positive.",
                    ephemeral=True
                )
                return
            
            old_balance = get_balance(user.id)
            new_balance = add_balance(user.id, amount)
            
            embed = discord.Embed(
                title="✅ Balance Added",
                description=f"Added Rp {amount:,} to {user.mention}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Previous Balance",
                value=f"Rp {old_balance:,}",
                inline=True
            )
            
            embed.add_field(
                name="New Balance",
                value=f"Rp {new_balance:,}",
                inline=True
            )
            
            embed.set_footer(text=f"Added by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            log_admin_action(
                interaction.user.id,
                "addbalance",
                f"Added Rp {amount:,} to user {user.id}"
            )
            
        except Exception as e:
            log_error_with_context(e, "admin_addbalance", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error adding balance: {str(e)}",
                ephemeral=True
            )
    
    # ==========================================
    # STATISTICS
    # ==========================================
    
    @app_commands.command(name="botstats", description="View bot statistics")
    @is_admin()
    async def botstats(self, interaction: discord.Interaction, days: int = 7):
        """View comprehensive bot statistics"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get database stats
            db_stats = get_database_stats()
            
            # Get order stats
            order_stats = get_order_statistics(days=days)
            
            embed = discord.Embed(
                title="📊 Bot Statistics",
                description=f"Last {days} days",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            # Users
            embed.add_field(
                name="👥 Users",
                value=f"**{db_stats['total_users']:,}**",
                inline=True
            )
            
            # Balance
            embed.add_field(
                name="💰 Total Balance",
                value=f"Rp {db_stats['total_balance']:,}",
                inline=True
            )
            
            # Stock
            embed.add_field(
                name="📦 Available Stock",
                value=f"**{db_stats['available_stock']:,}** codes",
                inline=True
            )
            
            # Orders
            embed.add_field(
                name=f"📋 Orders ({days}d)",
                value=(
                    f"Total: **{order_stats['total_orders']}**\n"
                    f"✅ Completed: {order_stats['completed']}\n"
                    f"⏳ Pending: {order_stats['pending']}\n"
                    f"❌ Failed: {order_stats['failed']}"
                ),
                inline=False
            )
            
            # Revenue
            embed.add_field(
                name=f"💵 Revenue ({days}d)",
                value=f"**Rp {order_stats.get('total_revenue', 0):,}**",
                inline=True
            )
            
            # Codes sold
            embed.add_field(
                name=f"🎯 Codes Sold ({days}d)",
                value=f"**{order_stats['total_codes']:,}** codes",
                inline=True
            )
            
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            log_error_with_context(e, "admin_botstats", admin=interaction.user.id)
            await interaction.followup.send(
                f"❌ Error getting stats: {str(e)}",
                ephemeral=True
            )

# ==========================================
# SETUP FUNCTION
# ==========================================

async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(AdminCommands(bot))
