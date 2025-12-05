# 🎮 Discord Bot Order Redfinger + Shared Balance System

Bot Discord untuk pemesanan kode Redfinger dengan sistem pembayaran otomatis menggunakan Midtrans QRIS dan **shared balance** dengan Bot Redeem.

## ✨ Key Features

### 🛒 User Features
- **Order Redfinger Codes** - Pesan kode dengan paket (1, 5, 10, 25, 50 codes)
- **Shared Balance** - Saldo dapat digunakan di Bot Redeem dan Bot Order
- **Auto Delivery** - Kode otomatis terkirim setelah pembayaran
- **Order Tracking** - Lacak status pesanan
- **Top Up Balance** - Isi saldo via QRIS (terintegrasi)
- **Order History** - Riwayat pemesanan lengkap

### 👨‍💼 Admin Features
- **Stock Management** - Kelola stock kode
- **Order Management** - Proses pesanan manual
- **Balance Management** - Kelola saldo user (SHARED)
- **Statistics Dashboard** - Laporan penjualan
- **Low Stock Alerts** - Notifikasi stock menipis

## 📊 Shared Database Architecture

```
┌─────────────────────────────────────────────────┐
│         PostgreSQL Cloud Database               │
│   (Supabase / Railway / AWS RDS / DigitalOcean) │
└────────────┬──────────────────┬─────────────────┘
             │                  │
    ┌────────▼────────┐  ┌─────▼──────────┐
    │  Bot Redeem     │  │  Bot Order     │
    │  (Server 1)     │  │  (Server 2)    │
    └─────────────────┘  └────────────────┘
```

### Shared Tables
- `users` - Saldo dan data user (SHARED)
- `topups` - Riwayat top up dari kedua bot (SHARED)

### Bot-Specific Tables
**Bot Redeem:**
- `redeems` - Riwayat redeem

**Bot Order:**
- `orders` - Data pesanan
- `stock` - Stock kode tersedia
- `deliveries` - Tracking pengiriman
- `order_items` - Detail item per order

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL database (untuk shared mode)
- 2 Discord Bot Tokens (satu untuk setiap bot)
- Midtrans account (bisa pakai yang sama untuk kedua bot)

### Installation

```bash
# 1. Clone/copy project
cd order_bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup database (PostgreSQL)
# Import schema ke database
psql -U your_user -d redfinger_db -f shared_db_schema.sql

# 4. Configure environment
cp .env.example .env
nano .env  # Edit configuration

# 5. Run bot
python bot.py
```

## ⚙️ Configuration

### .env File

```env
# Discord
DISCORD_TOKEN=your_order_bot_token_here
ADMIN_ROLE_NAME=Admin
PUBLIC_CHANNEL_ID=123456789

# Database (IMPORTANT)
DATABASE_TYPE=postgresql  # or sqlite for standalone
DATABASE_URL=postgresql://user:pass@host:5432/redfinger_db

# Midtrans
MIDTRANS_SERVER_KEY=your_server_key
MIDTRANS_IS_PRODUCTION=False
WEBHOOK_PORT=8001

# Pricing
PRICE_1_CODE=15000
PRICE_5_CODES=70000
PRICE_10_CODES=130000
PRICE_25_CODES=300000
PRICE_50_CODES=550000
```

## 🗄️ Database Setup

### Option 1: Shared PostgreSQL (RECOMMENDED)

#### 1. Setup PostgreSQL Database

**Using Supabase (FREE tier available):**
1. Sign up at https://supabase.com
2. Create new project
3. Go to SQL Editor
4. Run `shared_db_schema.sql`
5. Copy connection string

**Using Railway (FREE tier available):**
1. Sign up at https://railway.app
2. New Project → Add PostgreSQL
3. Connect and run schema
4. Copy connection string

#### 2. Update Both Bots

**Bot Redeem (.env):**
```env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@host:5432/redfinger_db
```

**Bot Order (.env):**
```env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@host:5432/redfinger_db
```

### Option 2: SQLite Standalone (For Testing)

```env
DATABASE_TYPE=sqlite
DB_FILE=bot_order.db
```

⚠️ **Note:** SQLite mode tidak support shared balance. Hanya gunakan untuk testing.

## 🌐 Midtrans Webhook Setup

### Important: Different Webhook URLs

Karena kedua bot running di port berbeda:

**Bot Redeem:**
- Port: 8000
- Webhook: `https://redeem-bot.yourdomain.com/webhook/midtrans`

**Bot Order:**
- Port: 8001
- Webhook: `https://order-bot.yourdomain.com/webhook/midtrans`

### Setup di Midtrans Dashboard

1. Login ke https://dashboard.midtrans.com
2. Settings → Configuration
3. **Payment Notification URL:**
   - Kedua URL harus didaftarkan
   - Atau gunakan satu URL yang route ke kedua bot

### Using Ngrok for Development

```bash
# Terminal 1 - Bot Redeem
ngrok http 8000

# Terminal 2 - Bot Order
ngrok http 8001
```

Update webhook URLs di .env masing-masing bot.

## 📦 Package Configuration

Edit pricing di `.env`:

```env
# Per code pricing
PRICE_1_CODE=15000     # Rp 15.000/code
PRICE_5_CODES=70000    # Rp 14.000/code (diskon 6.7%)
PRICE_10_CODES=130000  # Rp 13.000/code (diskon 13.3%)
PRICE_25_CODES=300000  # Rp 12.000/code (diskon 20%)
PRICE_50_CODES=550000  # Rp 11.000/code (diskon 26.7%)
```

## 🔐 Stock Management

### Add Stock via Admin Command

```
/admin addstock
```

Upload `.txt` file dengan format:
```
CODE1-HERE-ABC1
CODE2-HERE-DEF2
CODE3-HERE-GHI3
```

### Stock Encryption (Optional)

Enable di `.env`:
```env
ENCRYPT_STOCK_CODES=True
ENCRYPTION_KEY=your-32-character-secret-key-here
```

### Low Stock Alerts

```env
LOW_STOCK_THRESHOLD=10
STOCK_ALERT_ENABLED=True
STOCK_ADMIN_USER_IDS=123456789,987654321
```

## 🚢 Deployment

### Deployment Strategy

#### Same Server (2 Processes)

```bash
# Terminal 1 - Bot Redeem
cd /path/to/redeem_bot
python bot.py

# Terminal 2 - Bot Order
cd /path/to/order_bot
python bot.py
```

#### Different Servers (RECOMMENDED)

**Server 1 (Redeem Bot):**
```bash
git clone <your-redeem-bot-repo>
cd redeem_bot
pip install -r requirements.txt
# Configure .env
python bot.py
```

**Server 2 (Order Bot):**
```bash
git clone <your-order-bot-repo>
cd order_bot
pip install -r requirements.txt
# Configure .env
python bot.py
```

### Using PM2 (Process Manager)

```bash
# Install PM2
npm install -g pm2

# Start bots
pm2 start bot.py --name "order-bot" --interpreter python3

# Monitor
pm2 monit

# Auto-start on reboot
pm2 startup
pm2 save
```

### Using Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  order-bot:
    build: .
    env_file: .env
    restart: always
    ports:
      - "8001:8001"
```

## 🔄 Migration from SQLite to PostgreSQL

Jika sudah running dengan SQLite dan ingin migrate:

```bash
# 1. Backup SQLite data
sqlite3 bot_order.db .dump > backup.sql

# 2. Setup PostgreSQL
# (import shared_db_schema.sql)

# 3. Convert and import data
# (use migration script or manual import)

# 4. Update .env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://...

# 5. Restart bot
```

## 📝 Admin Commands

```
/admin addstock          - Upload stock codes
/admin viewstock         - View current stock
/admin vieworders        - View all orders
/admin processorder      - Process order manually
/admin addbalance        - Add balance to user
/admin checkuser         - Check user details
/admin botstats          - View statistics
```

## 🧪 Testing

### Test Configuration

```bash
python -c "import config; config.print_config()"
```

### Test Database Connection

```bash
python -c "from database import init_database; init_database()"
```

### Test Shared Balance

1. Top up di Bot Redeem
2. Check balance di Bot Order
3. Harus sama

## 🐛 Troubleshooting

### Balance Not Syncing

- Check DATABASE_URL sama di kedua bot
- Check database connection
- Check `bot_source` column di tabel topups

### Stock Not Delivered

- Check `DELIVERY_METHOD` di .env
- Check user's DM is open
- Check stock availability

### Webhook Not Working

- Check firewall/port open
- Check Midtrans webhook URL
- Check webhook server running

## 📈 Monitoring

### Check Bot Status

```bash
# View logs
tail -f logs/bot_order.log

# Check database stats
psql -U user -d redfinger_db -c "SELECT * FROM v_stock_summary;"
```

### Monitor Balance Sync

```sql
-- Check latest topups from both bots
SELECT order_id, amount, bot_source, created_at 
FROM topups 
ORDER BY created_at DESC 
LIMIT 10;
```

## 🔒 Security Best Practices

1. **Never commit .env** - Use .gitignore
2. **Use strong ENCRYPTION_KEY** - Min 32 characters
3. **Enable SSL** for PostgreSQL connection
4. **Rotate API keys** regularly
5. **Monitor unusual activity** in logs
6. **Backup database** regularly

## 📚 File Structure

```
order_bot/
├── .env                     # Configuration
├── requirements.txt         # Dependencies
├── shared_db_schema.sql     # Database schema
├── config.py               # Config management
├── database.py             # Database operations
├── logger.py               # Logging system
├── payment_gateway.py      # Midtrans integration
├── webhook_server.py       # Webhook handler
├── bot.py                  # Main Discord bot
├── order_manager.py        # Order processing
├── stock_manager.py        # Stock management
├── delivery_handler.py     # Delivery system
└── admin_commands.py       # Admin commands
```

## 🤝 Integration with Bot Redeem

### Shared Components

1. **Balance System**
   - Same users table
   - Same topups table
   - Real-time sync

2. **Payment Gateway**
   - Same Midtrans account
   - Different webhook URLs
   - Same payment flow

3. **User Management**
   - Same user IDs
   - Same admin roles
   - Unified user experience

## 💡 Tips & Best Practices

1. **Start with SQLite** for development
2. **Migrate to PostgreSQL** for production
3. **Monitor stock levels** regularly
4. **Set up alerts** for low stock
5. **Backup database** daily
6. **Test webhook** after every deployment
7. **Use PM2/systemd** for production
8. **Monitor logs** for errors
9. **Keep pricing** competitive
10. **Regular updates** to dependencies

## 📞 Support

For issues or questions:
1. Check logs first: `tail -f logs/bot_order.log`
2. Verify configuration: Check .env file
3. Test database: Run test script
4. Check Discord permissions

## 📄 License

This project is for personal/commercial use.

---

**Made with ❤️ for Redfinger Code Business**
