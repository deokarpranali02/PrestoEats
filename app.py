from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
from flask import make_response
from flask import send_file

app = Flask(__name__)
app.secret_key = "canteen_secret"

# ---------- DB Connection ----------
def get_db_connection():
    conn = sqlite3.connect("canteen.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

#  Initialize Tables
def init_db():
   
    return

# ---------- Homepage ----------
@app.route("/")
def index():
    conn = get_db_connection()
    c = conn.cursor()

    ip = request.remote_addr

    # Check if IP already exists
    c.execute("SELECT id FROM visitors WHERE ip = ?", (ip,))
    row = c.fetchone()

    if row:
        # Update timestamp if visitor exists
        c.execute("UPDATE visitors SET timestamp = CURRENT_TIMESTAMP WHERE id = ?", (row[0],))
    else:
        # Insert new visitor
        c.execute("INSERT INTO visitors (ip) VALUES (?)", (ip,))

    conn.commit()

    # Count only visitors active in last 5 minutes
    c.execute("""
        SELECT COUNT(*) 
        FROM visitors 
        WHERE timestamp >= datetime('now', '-5 minutes')
    """)
    total_visitors = c.fetchone()[0]

    conn.close()
    return render_template("index.html", total_visitors=total_visitors)

@app.route("/get_visitors")
def get_visitors():
    conn = sqlite3.connect("canteen.db")
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) 
        FROM visitors 
        WHERE timestamp >= datetime('now', '-5 minutes')
    """)
    count = c.fetchone()[0]
    conn.close()
    return {"count": count}

@app.route("/menu", methods=["GET", "POST"])
def menu():
    conn = get_db_connection()
    c = conn.cursor()

    if request.method == "POST":
        if "user_id" not in session:
            flash("Please login to add items to cart.", "warning")
            conn.close()
            return redirect(url_for("student_account"))

        item_id = request.form.get("item_id")
        user_id = session["user_id"]
        if item_id:
            row = c.execute("SELECT * FROM cart WHERE item_id=? AND user_id=?", (item_id, user_id)).fetchone()
            if row:
                c.execute("UPDATE cart SET quantity = quantity + 1 WHERE id=?", (row["id"],))
            else:
                c.execute("INSERT INTO cart (user_id, item_id, quantity) VALUES (?, ?, ?)", (user_id, item_id, 1))
            conn.commit()
            flash("Item added to cart.", "success")
            conn.close()
            
            return redirect(url_for("order"))

    items = c.execute("SELECT * FROM menu").fetchall()
    conn.close()
    return render_template("menu.html", items=items)

#  Order (Cart) 
@app.route("/order", methods=["GET", "POST"])
def order():
    if "user_id" not in session:
        flash("Please login to view your cart.", "warning")
        return redirect(url_for("student_account"))

    conn = get_db_connection()
    c = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")
        cart_id = request.form.get("cart_id")

        if action == "increase":
            c.execute(
                "UPDATE cart SET quantity = quantity + 1 WHERE id=? AND user_id=?",
                (cart_id, session["user_id"])
            )
        elif action == "decrease":
            row = c.execute(
                "SELECT quantity FROM cart WHERE id=? AND user_id=?",
                (cart_id, session["user_id"])
            ).fetchone()
            if row and row["quantity"] > 1:
                c.execute(
                    "UPDATE cart SET quantity = quantity - 1 WHERE id=? AND user_id=?",
                    (cart_id, session["user_id"])
                )
            else:
                c.execute(
                    "DELETE FROM cart WHERE id=? AND user_id=?",
                    (cart_id, session["user_id"])
                )
        elif action == "remove":
            c.execute(
                "DELETE FROM cart WHERE id=? AND user_id=?",
                (cart_id, session["user_id"])
            )
        conn.commit()

    # join menu with cart to fetch item details including image
    cart_items = c.execute("""
        SELECT cart.id as cart_id, menu.id as item_id, menu.name, menu.price, menu.image,
               cart.quantity, (menu.price * cart.quantity) as total_price
        FROM cart
        JOIN menu ON cart.item_id = menu.id
        WHERE cart.user_id = ?
    """, (session["user_id"],)).fetchall()

    # total calculation
    total_amount = sum(item["total_price"] for item in cart_items)

    
    cart_data = []
    for item in cart_items:
        cart_data.append({
            "cart_id": item["cart_id"],
            "item_id": item["item_id"],
            "name": item["name"],
            "price": item["price"],
            "quantity": item["quantity"],
            "total_price": item["total_price"],
            "image": item["image"] if item["image"] else "placeholder.jpg"
        })

    conn.close()
    return render_template("order.html", cart_items=cart_data, total_amount=total_amount)

# Payment
@app.route("/payment", methods=["GET", "POST"])
def payment():
    if "user_id" not in session:
        flash("Please login to continue.", "warning")
        return redirect(url_for("student_account"))

    conn = get_db_connection()
    c = conn.cursor()

    # fetch cart items
    cart_items = c.execute("""
        SELECT cart.id as cart_id, menu.id as item_id, menu.name, menu.price, menu.image, cart.quantity
        FROM cart
        JOIN menu ON cart.item_id = menu.id
        WHERE cart.user_id = ?
    """, (session["user_id"],)).fetchall()

    total_amount = sum(item["price"] * item["quantity"] for item in cart_items)

    if request.method == "POST":
        payment_method = request.form.get("payment")
        upi_id = request.form.get("upi_id")

        if payment_method == "upi":
            if not upi_id or "@" not in upi_id:
                flash("Enter a valid UPI ID.", "danger")
                conn.close()
                return render_template("payment.html", total_amount=total_amount)
            payment_status = "Success"
            message = f"✅ Payment successful via UPI ({upi_id})!"
        elif payment_method == "cash":
            payment_status = "Pending"
            message = "✅ Cash on Delivery selected. Please pay at pickup!"
        else:
            flash("Select a valid payment method.", "danger")
            conn.close()
            return render_template("payment.html", total_amount=total_amount)

        user_id = session["user_id"]

        # create order
        c.execute("INSERT INTO orders (user_id, total_amount, status) VALUES (?, ?, ?)",
                  (user_id, total_amount, "Pending"))
        order_id = c.lastrowid

        ordered_items = []
        for it in cart_items:
            c.execute("INSERT INTO order_items (order_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
                      (order_id, it["item_id"], it["quantity"], it["price"]))
            ordered_items.append({
                "name": it["name"],
                "quantity": it["quantity"],
                "price": it["price"],
                "total_price": it["price"] * it["quantity"],
                "image": it["image"]
            })

        # Update Day-wise and Month-wise Sales 
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        for it in cart_items:
            # Day-wise update
            c.execute("""
                INSERT INTO sales_day_summary (day, item_id, total_quantity, total_sales)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(day, item_id) DO UPDATE SET
                    total_quantity = total_quantity + excluded.total_quantity,
                    total_sales = total_sales + excluded.total_sales
            """, (today, it["item_id"], it["quantity"], it["quantity"] * it["price"]))

            # Month-wise update
            c.execute("""
                INSERT INTO sales_month_summary (month, item_id, total_quantity, total_sales)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(month, item_id) DO UPDATE SET
                    total_quantity = total_quantity + excluded.total_quantity,
                    total_sales = total_sales + excluded.total_sales
            """, (month, it["item_id"], it["quantity"], it["quantity"] * it["price"]))

        # store payment record
        c.execute("INSERT INTO payments (user_id, payment_method, upi_id, total_amount, status) VALUES (?, ?, ?, ?, ?)",
                  (user_id, payment_method, upi_id if upi_id else None, total_amount, payment_status))

        # clear cart
        c.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()

        # render thankyou page
        return render_template(
            "thankyou.html",
            message=message,
            order_id=order_id,
            ordered_items=ordered_items,
            total_amount=total_amount
        )

    conn.close()
    return render_template("payment.html", total_amount=total_amount)

# Student Account
@app.route("/account", methods=["GET", "POST"])
def student_account():
    if request.method == "POST":
        if "login" in request.form:
            phone = request.form["phone"]
            password = request.form["password"]

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE phone=?", (phone,))
            user = c.fetchone()
            conn.close()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                flash(f"Welcome back, {user['name']}!", "success")
                return redirect(url_for("student_dashboard"))
            else:
                flash("Invalid phone or password", "danger")

        elif "signup" in request.form:
            name = request.form["name"]
            phone = request.form["phone"]
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]

            if password != confirm_password:
                flash("Passwords do not match!", "danger")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                try:
                    hashed_password = generate_password_hash(password)
                    c.execute("INSERT INTO users (name, phone, password) VALUES (?, ?, ?)",
                              (name, phone, hashed_password))
                    conn.commit()
                    user_id = c.lastrowid
                    session["user_id"] = user_id
                    session["user_name"] = name
                    flash("Signup successful! Welcome!", "success")
                    return redirect(url_for("student_dashboard"))
                except sqlite3.IntegrityError:
                    flash("Phone number already registered!", "danger")
                finally:
                    conn.close()

    return render_template("student_account.html")

# Student Dashboard 
@app.route("/student/dashboard")
def student_dashboard():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("student_account"))

    user_id = session["user_id"]
    conn = get_db_connection()
    c = conn.cursor()

    orders = c.execute("""
        SELECT o.id, o.total_amount, o.status, o.pickup_time, o.created_at,
               GROUP_CONCAT(m.name || ' x' || oi.quantity, ' || ') as items
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        LEFT JOIN menu m ON oi.item_id = m.id
        WHERE o.user_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
    """, (user_id,)).fetchall()

    next_confirmed = c.execute("""
        SELECT id, pickup_time FROM orders
        WHERE user_id=? AND status='Confirmed' AND pickup_time IS NOT NULL
        ORDER BY pickup_time ASC LIMIT 1
    """, (user_id,)).fetchone()

    conn.close()
    return render_template("student_dashboard.html", name=session.get("user_name"), orders=orders, next_confirmed=next_confirmed)

# API: student next confirmed pickup (for live countdown)
@app.route("/api/student/next_pickup")
def api_student_next_pickup():
    if "user_id" not in session:
        return jsonify({"error": "login required"}), 401

    user_id = session["user_id"]
    conn = get_db_connection()
    c = conn.cursor()
    row = c.execute("""
        SELECT id, pickup_time, status
        FROM orders
        WHERE user_id=? AND status='Confirmed' AND pickup_time IS NOT NULL
        ORDER BY pickup_time ASC LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"order": None})

    pickup_time_str = row["pickup_time"]
    try:
        pickup_dt = datetime.strptime(pickup_time_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        
        return jsonify({
            "order_id": row["id"],
            "pickup_time": pickup_time_str,
            "seconds_remaining": 0,
            "status": row["status"]
        })

    now = datetime.now()
    seconds_remaining = int((pickup_dt - now).total_seconds())
    if seconds_remaining < 0:
        seconds_remaining = 0

    return jsonify({
        "order_id": row["id"],
        "pickup_time": pickup_time_str,
        "seconds_remaining": seconds_remaining,
        "status": row["status"]
    })

# API: student orders list (JSON)
@app.route("/api/student/orders")
def api_student_orders():
    if "user_id" not in session:
        return jsonify({"error": "login required"}), 401

    user_id = session["user_id"]
    conn = get_db_connection()
    c = conn.cursor()
    rows = c.execute("""
        SELECT o.id, o.total_amount, o.status, o.pickup_time, o.created_at,
               GROUP_CONCAT(m.name || ' x' || oi.quantity, ' || ') as items
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        LEFT JOIN menu m ON oi.item_id = m.id
        WHERE o.user_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()

    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "items": r["items"],
            "total_amount": r["total_amount"],
            "pickup_time": r["pickup_time"],
            "status": r["status"],
            "created_at": r["created_at"]
        })
    return jsonify(out)

#  Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("student_account"))

# Admin Account 
@app.route("/admin/account", methods=["GET", "POST"])
def admin_account():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM admins WHERE username=?", (username,))
        admin = c.fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            flash("Welcome Admin!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials!", "danger")

    return render_template("admin_account.html")

#  Admin Dashboard

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    conn = get_db_connection()
    c = conn.cursor()
    menu_items = c.execute("SELECT * FROM menu").fetchall()
    users = c.execute("SELECT * FROM users").fetchall()
   
    total_orders = c.execute("SELECT COUNT(*) as cnt FROM orders").fetchone()["cnt"]
    total_revenue = c.execute("SELECT SUM(total_amount) as s FROM orders").fetchone()["s"] or 0
    conn.close()

    return render_template(
        "admin_dashboard.html",
        menu_items=menu_items,
        users=users,
        admin_name=session.get("admin_name"),
        total_orders=total_orders,
        total_revenue=total_revenue
    )

# Admin: Delete User 
@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully!", "success")
    return redirect(url_for("admin_dashboard"))

# Admin: Add / Edit / Delete Menu 
@app.route("/admin/add_menu", methods=["POST"])
def admin_add_menu():
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    name = request.form["name"]
    category = request.form["category"]  
    price = request.form["price"]
    image = request.form.get("image", "")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO menu (name, category, price, image) VALUES (?, ?, ?, ?)", (name, category, price, image))
    conn.commit()
    conn.close()
    flash("Menu item added successfully!", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/edit_menu/<int:item_id>", methods=["POST"])
def admin_edit_menu(item_id):
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    name = request.form["name"]
    price = request.form["price"]
    image = request.form.get("image", "")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE menu SET name=?, price=?, image=? WHERE id=?", (name, price, image, item_id))
    conn.commit()
    conn.close()
    flash("Menu item updated successfully!", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_menu/<int:item_id>", methods=["POST"])
def admin_delete_menu(item_id):
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM menu WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    flash("Menu item deleted successfully!", "success")
    return redirect(url_for("admin_dashboard"))
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    conn = get_db_connection()
    c = conn.cursor()
    menu_items = c.execute("SELECT * FROM menu").fetchall()
    users = c.execute("SELECT * FROM users").fetchall()
    conn.close()

    return render_template("admin_dashboard.html", menu_items=menu_items, users=users, admin_name=session.get("admin_name"))



# Vendor Account 
@app.route("/vendor/account", methods=["GET", "POST"])
def vendor_account():
    if request.method == "POST":
        if "login" in request.form:
            username = request.form["username"]
            password = request.form["password"]

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM vendors WHERE username=?", (username,))
            vendor = c.fetchone()
            conn.close()

            if vendor and check_password_hash(vendor["password"], password):
                session["vendor_id"] = vendor["id"]
                session["vendor_name"] = vendor["name"]
                flash("Welcome Vendor!", "success")
                return redirect(url_for("vendor_dashboard"))
            else:
                flash("Invalid credentials!", "danger")

        elif "signup" in request.form:
            name = request.form["name"]
            username = request.form["username"]
            password = request.form["password"]
            hashed = generate_password_hash(password)

            conn = get_db_connection()
            c = conn.cursor()
            try:
                c.execute("INSERT INTO vendors (name, username, password) VALUES (?, ?, ?)",
                          (name, username, hashed))
                conn.commit()
                vendor_id = c.lastrowid
                session["vendor_id"] = vendor_id
                session["vendor_name"] = name
                flash("Vendor account created! Welcome!", "success")
                return redirect(url_for("vendor_dashboard"))
            except sqlite3.IntegrityError:
                flash("Username already exists!", "danger")
            finally:
                conn.close()

    return render_template("vendor_account.html")

# ---------- Vendor Dashboard ----------
@app.route("/vendor/dashboard")
def vendor_dashboard():
    if "vendor_id" not in session:
        flash("Vendor access only!", "danger")
        return redirect(url_for("vendor_account"))

    conn = get_db_connection()
    c = conn.cursor()

    orders = c.execute("""
        SELECT o.id, u.name as student, o.total_amount, o.status, o.pickup_time, o.created_at,
               GROUP_CONCAT(m.name || ' x' || oi.quantity, ' || ') as items
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN order_items oi ON oi.order_id = o.id
        LEFT JOIN menu m ON oi.item_id = m.id
        GROUP BY o.id
        ORDER BY o.created_at DESC
    """).fetchall()

    conn.close()
    return render_template("vendor_dashboard.html", orders=orders, vendor_name=session.get("vendor_name"))

# ---------- Vendor: Confirm order & set pickup time (minutes) ----------
@app.route("/vendor/confirm_order/<int:order_id>", methods=["POST"])
def vendor_confirm_order(order_id):
    if "vendor_id" not in session:
        flash("Vendor access only!", "danger")
        return redirect(url_for("vendor_account"))

    # Expect minutes
    minutes_raw = request.form.get("pickup_minutes")
    if not minutes_raw:
        flash("Please provide pickup minutes.", "danger")
        return redirect(url_for("vendor_dashboard"))

    try:
        minutes = int(minutes_raw)
        if minutes <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid number of minutes (>=1).", "danger")
        return redirect(url_for("vendor_dashboard"))

    pickup_dt = datetime.now() + timedelta(minutes=minutes)
    pickup_time_str = pickup_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE orders SET status='Confirmed', pickup_time=? WHERE id=?", (pickup_time_str, order_id))
    conn.commit()
    conn.close()
    flash(f"Order confirmed — pickup in {minutes} min ({pickup_time_str}).", "success")
    return redirect(url_for("vendor_dashboard"))

# Mark as Ready
@app.route("/vendor/mark_ready/<int:order_id>", methods=["POST"])
def vendor_mark_ready(order_id):
    if "vendor_id" not in session:
        flash("Vendor access only!", "danger")
        return redirect(url_for("vendor_account"))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE orders SET status='Ready' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    flash("Order marked Ready.", "success")
    return redirect(url_for("vendor_dashboard"))

# Cancel order
@app.route("/vendor/cancel_order/<int:order_id>", methods=["POST"])
def vendor_cancel_order(order_id):
    if "vendor_id" not in session:
        flash("Vendor access only!", "danger")
        return redirect(url_for("vendor_account"))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    flash("Order cancelled.", "warning")
    return redirect(url_for("vendor_dashboard"))

# API: vendor pending orders (JSON) 
@app.route("/api/vendor/pending_orders")
def api_vendor_pending_orders():
    if "vendor_id" not in session:
        return jsonify({"error": "login required"}), 401

    conn = get_db_connection()
    c = conn.cursor()
    rows = c.execute("""
        SELECT o.id, u.name as student, o.total_amount, o.status, o.pickup_time,
               GROUP_CONCAT(m.name || ' x' || oi.quantity, ' || ') as items
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN order_items oi ON oi.order_id = o.id
        LEFT JOIN menu m ON oi.item_id = m.id
        WHERE o.status = 'Pending' OR o.status = 'Confirmed'
        GROUP BY o.id
        ORDER BY o.created_at ASC
    """).fetchall()
    conn.close()

    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "student": r["student"],
            "items": r["items"],
            "total_amount": r["total_amount"],
            "status": r["status"],
            "pickup_time": r["pickup_time"]
        })
    return jsonify(out)
    # get wise report generation

def draw_border_footer(canvas, doc):
    width, height = letter
    # Full page border
    canvas.setStrokeColor(colors.HexColor("#4CAF50"))
    canvas.setLineWidth(3)
    margin = 20
    canvas.rect(margin, margin, width - 2*margin, height - 2*margin)

    # Footer - page number
    page_num_text = f"Page {doc.page}"
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - margin, 15, page_num_text)

# for PDF Builder 
def build_pdf(title, rows, totals, most_sold, least_sold, filename):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40, rightMargin=40,
        topMargin=60, bottomMargin=40
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'title',
        parent=styles['Title'],
        alignment=1,
        textColor=colors.HexColor("#4CAF50"),
        fontSize=20,
        spaceAfter=12
    )
    normal_style = styles["Normal"]

    elements = []
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    elements.append(Spacer(1, 12))

    # Table header
    data = [["Date/Month", "Item", "Quantity Sold", "Total Sales"]]
    for i, r in enumerate(rows):
        bg_color = colors.beige if i % 2 == 0 else colors.whitesmoke
        data.append([r[0], r[1], r[2], f"{r[3]:.2f}"])

    # Add totals
    data.append(["", "", "", ""])
    data.append(["Date/Month", "Total Quantity", "Total Sales", ""])
    for t in totals:
        data.append([t[0], t[1], f"{t[2]:.2f}", ""])

    table = Table(data, repeatRows=1, hAlign='CENTER')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4CAF50")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    
    if most_sold:
        elements.append(Paragraph(f"Most Sold Item: <b>{most_sold[0]}</b> ({most_sold[1]} sold)", normal_style))
    if least_sold:
        elements.append(Paragraph(f"Least Sold Item: <b>{least_sold[0]}</b> ({least_sold[1]} sold)", normal_style))

   
    doc.build(elements, onFirstPage=draw_border_footer, onLaterPages=draw_border_footer)
    pdf_value = buffer.getvalue()
    buffer.close()
    return pdf_value

# ---------- Admin Day-wise Report ----------
@app.route("/admin/report/day")
def admin_day_report():
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    conn = get_db_connection()
    c = conn.cursor()

    rows = c.execute("""
        SELECT DATE(o.created_at) as day, m.name, SUM(oi.quantity) as total_qty, SUM(oi.quantity * oi.price) as total_sales
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN menu m ON oi.item_id = m.id
        GROUP BY day, m.name
        ORDER BY day DESC
    """).fetchall()

    totals = c.execute("""
        SELECT DATE(o.created_at) as day, SUM(oi.quantity) as total_qty, SUM(oi.quantity * oi.price) as total_sales
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        GROUP BY day
        ORDER BY day DESC
    """).fetchall()

    most_sold = c.execute("""
        SELECT m.name, SUM(oi.quantity) as qty_sold
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.id
        GROUP BY m.id
        ORDER BY qty_sold DESC
        LIMIT 1
    """).fetchone()

    least_sold = c.execute("""
        SELECT m.name, SUM(oi.quantity) as qty_sold
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.id
        GROUP BY m.id
        ORDER BY qty_sold ASC
        LIMIT 1
    """).fetchone()
    conn.close()

    if not rows:
        flash("No sales data available.", "warning")
        return redirect(url_for("admin_dashboard"))

    pdf_value = build_pdf("Day-wise Sales Report", rows, totals, most_sold, least_sold, "day_sales_report.pdf")
    response = make_response(pdf_value)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=day_sales_report.pdf'
    return response

# ---------- Admin Month-wise Report ----------
@app.route("/admin/report/month")
def admin_report_month():
    if "admin_id" not in session:
        flash("Admin access only!", "danger")
        return redirect(url_for("admin_account"))

    conn = get_db_connection()
    c = conn.cursor()

    rows = c.execute("""
        SELECT strftime('%Y-%m', o.created_at) as month, m.name,
               SUM(oi.quantity) as total_qty, SUM(oi.quantity * oi.price) as total_sales
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN menu m ON oi.item_id = m.id
        GROUP BY month, m.name
        ORDER BY month DESC
    """).fetchall()

    totals = c.execute("""
        SELECT strftime('%Y-%m', o.created_at) as month,
               SUM(oi.quantity) as total_qty, SUM(oi.quantity * oi.price) as total_sales
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        GROUP BY month
        ORDER BY month DESC
    """).fetchall()

    most_sold = c.execute("""
        SELECT m.name, SUM(oi.quantity) as qty_sold
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.id
        GROUP BY m.id
        ORDER BY qty_sold DESC
        LIMIT 1
    """).fetchone()

    least_sold = c.execute("""
        SELECT m.name, SUM(oi.quantity) as qty_sold
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.id
        GROUP BY m.id
        ORDER BY qty_sold ASC
        LIMIT 1
    """).fetchone()
    conn.close()

    if not rows:
        flash("No sales data available.", "warning")
        return redirect(url_for("admin_dashboard"))

    pdf_value = build_pdf("Month-wise Sales Report", rows, totals, most_sold, least_sold, "month_sales_report.pdf")
    response = make_response(pdf_value)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=month_sales_report.pdf'
    return response

 
if __name__ == "__main__":
    app.run()