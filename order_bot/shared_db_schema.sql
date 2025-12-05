-- ==========================================
-- SHARED DATABASE SCHEMA
-- For both Redeem Bot and Order Bot
-- ==========================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- SHARED TABLES (Used by both bots)
-- ==========================================

-- Users table (SHARED)
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    balance BIGINT DEFAULT 0,
    total_topup BIGINT DEFAULT 0,
    total_spent BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Topups table (SHARED)
CREATE TABLE IF NOT EXISTS topups (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    payment_type VARCHAR(50),
    bot_source VARCHAR(20) DEFAULT 'redeem',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ==========================================
-- BOT REDEEM SPECIFIC TABLES
-- ==========================================

-- Redeems table (Bot Redeem only)
CREATE TABLE IF NOT EXISTS redeems (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    code_count INTEGER NOT NULL,
    total_cost BIGINT NOT NULL,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ==========================================
-- BOT ORDER SPECIFIC TABLES
-- ==========================================

-- Orders table (Bot Order only)
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    user_id BIGINT NOT NULL,
    package_type VARCHAR(20) NOT NULL,
    code_quantity INTEGER NOT NULL,
    total_price BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    payment_method VARCHAR(20) DEFAULT 'balance',
    delivery_status VARCHAR(20) DEFAULT 'pending',
    delivery_method VARCHAR(20) DEFAULT 'dm',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Stock table (Bot Order only)
CREATE TABLE IF NOT EXISTS stock (
    id SERIAL PRIMARY KEY,
    code VARCHAR(500) NOT NULL,
    code_type VARCHAR(50) DEFAULT 'redfinger',
    is_available BOOLEAN DEFAULT TRUE,
    is_encrypted BOOLEAN DEFAULT FALSE,
    added_by BIGINT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reserved_for_order INTEGER,
    used_at TIMESTAMP,
    used_by BIGINT,
    FOREIGN KEY (reserved_for_order) REFERENCES orders(id) ON DELETE SET NULL,
    FOREIGN KEY (used_by) REFERENCES users(user_id) ON DELETE SET NULL
);

-- Deliveries table (Bot Order only)
CREATE TABLE IF NOT EXISTS deliveries (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    user_id BIGINT NOT NULL,
    delivery_method VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    attempt_count INTEGER DEFAULT 0,
    delivered_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Order items table (Bot Order only) - untuk tracking kode per order
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stock(id) ON DELETE CASCADE
);

-- ==========================================
-- INDEXES FOR PERFORMANCE
-- ==========================================

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance);

-- Topups indexes
CREATE INDEX IF NOT EXISTS idx_topups_user_id ON topups(user_id);
CREATE INDEX IF NOT EXISTS idx_topups_order_id ON topups(order_id);
CREATE INDEX IF NOT EXISTS idx_topups_status ON topups(status);
CREATE INDEX IF NOT EXISTS idx_topups_bot_source ON topups(bot_source);

-- Redeems indexes
CREATE INDEX IF NOT EXISTS idx_redeems_user_id ON redeems(user_id);
CREATE INDEX IF NOT EXISTS idx_redeems_status ON redeems(status);

-- Orders indexes
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_number ON orders(order_number);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_delivery_status ON orders(delivery_status);

-- Stock indexes
CREATE INDEX IF NOT EXISTS idx_stock_is_available ON stock(is_available);
CREATE INDEX IF NOT EXISTS idx_stock_code_type ON stock(code_type);
CREATE INDEX IF NOT EXISTS idx_stock_reserved ON stock(reserved_for_order);

-- Deliveries indexes
CREATE INDEX IF NOT EXISTS idx_deliveries_order_id ON deliveries(order_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status);

-- Order items indexes
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_stock_id ON order_items(stock_id);

-- ==========================================
-- FUNCTIONS & TRIGGERS
-- ==========================================

-- Auto update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for topups table
CREATE TRIGGER update_topups_updated_at BEFORE UPDATE ON topups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- VIEWS FOR REPORTING
-- ==========================================

-- Active users view
CREATE OR REPLACE VIEW v_active_users AS
SELECT 
    u.user_id,
    u.balance,
    u.total_topup,
    u.total_spent,
    COUNT(DISTINCT o.id) as total_orders,
    COUNT(DISTINCT r.id) as total_redeems,
    u.created_at,
    u.updated_at
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id
LEFT JOIN redeems r ON u.user_id = r.user_id
GROUP BY u.user_id;

-- Stock summary view
CREATE OR REPLACE VIEW v_stock_summary AS
SELECT 
    code_type,
    COUNT(*) as total_codes,
    COUNT(*) FILTER (WHERE is_available = TRUE) as available_codes,
    COUNT(*) FILTER (WHERE is_available = FALSE) as used_codes,
    COUNT(*) FILTER (WHERE reserved_for_order IS NOT NULL) as reserved_codes
FROM stock
GROUP BY code_type;

-- Order statistics view
CREATE OR REPLACE VIEW v_order_stats AS
SELECT 
    DATE(created_at) as order_date,
    COUNT(*) as total_orders,
    SUM(code_quantity) as total_codes_ordered,
    SUM(total_price) as total_revenue,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_orders,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_orders,
    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_orders
FROM orders
GROUP BY DATE(created_at)
ORDER BY order_date DESC;

-- ==========================================
-- SAMPLE DATA (for testing)
-- ==========================================

-- Insert test user
INSERT INTO users (user_id, balance) 
VALUES (123456789, 100000) 
ON CONFLICT (user_id) DO NOTHING;

-- ==========================================
-- GRANTS (adjust based on your setup)
-- ==========================================

-- Example: Grant all privileges to application user
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
