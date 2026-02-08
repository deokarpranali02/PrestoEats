import sqlite3
from werkzeug.security import generate_password_hash

DB = "canteen.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # enforce foreign keys
    c.execute("PRAGMA foreign_keys = ON;")

    # ---------------- DROP OLD TABLES ----------------
    tables = [
        "payments", "order_items", "orders", "cart", "menu",
        "vendors", "admins", "users", "visitors",
        "sales_day_summary", "sales_month_summary"
    ]
    for t in tables:
        c.execute(f"DROP TABLE IF EXISTS {t}")

    # ---------------- USERS (Students) ----------------
    c.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # ---------------- VISITORS ----------------
    c.execute("""
    CREATE TABLE visitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- ADMINS ----------------
    c.execute("""
    CREATE TABLE admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # ---------------- VENDORS ----------------
    c.execute("""
    CREATE TABLE vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # ---------------- MENU ----------------
    c.execute("""
    CREATE TABLE menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        price REAL NOT NULL,
        image TEXT
    )
    """)

    # ---------------- CART ----------------
    c.execute("""
    CREATE TABLE cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        cart_key TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES menu(id) ON DELETE CASCADE
    )
    """)

    # ---------------- ORDERS ----------------
    c.execute("""
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'Pending',
        pickup_time TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- ORDER ITEMS ----------------
    c.execute("""
    CREATE TABLE order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        item_id INTEGER,
        quantity INTEGER,
        price REAL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES menu(id) ON DELETE CASCADE
    )
    """)

    # ---------------- PAYMENTS ----------------
    c.execute("""
    CREATE TABLE payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        payment_method TEXT NOT NULL,
        upi_id TEXT,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'Success',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- SALES SUMMARY TABLES ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS sales_day_summary (
        day TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        total_quantity INTEGER DEFAULT 0,
        total_sales REAL DEFAULT 0,
        PRIMARY KEY(day, item_id),
        FOREIGN KEY(item_id) REFERENCES menu(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales_month_summary (
        month TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        total_quantity INTEGER DEFAULT 0,
        total_sales REAL DEFAULT 0,
        PRIMARY KEY(month, item_id),
        FOREIGN KEY(item_id) REFERENCES menu(id) ON DELETE CASCADE
    )
    """)

    # ---------------- DEFAULT ADMIN ----------------
    admin_username = "myadmin"
    admin_password = generate_password_hash("mypassword123")
    c.execute("INSERT INTO admins (name, username, password) VALUES (?, ?, ?)",
              ("Super Admin", admin_username, admin_password))

    # ---------------- DEFAULT VENDOR ----------------
    vendor_username = "vendor1"
    vendor_password = generate_password_hash("vendorpass")
    c.execute("INSERT INTO vendors (name, username, password) VALUES (?, ?, ?)",
              ("Canteen Vendor", vendor_username, vendor_password))

    conn.commit()
    conn.close()
    print("✅ Database & tables created successfully with ON DELETE CASCADE.")

if __name__ == "__main__":
    init_db()
