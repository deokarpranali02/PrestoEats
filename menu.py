import os
import sqlite3

db_path = os.path.abspath("canteen.db")
print("Using database file:", db_path)
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Clear old data (optional, prevents duplicates if script rerun)
c.execute("DELETE FROM menu")

menu_items = [
    # Specials
    ("Veg Pulav", "Special", 80, "veg-pulav.jpg"),
    ("Pav Bhaji", "Special", 50, "pav-bhaji.jpg"),
    ("Veg Thali", "Special", 90, "veg-thali.jpg"),
    ("Vada Sambhar", "Special", 40, "vada-sambhar.jpg"),
    ("Vada Sambhar", "Special", 40, "vada-sambhar.jpg"),
    
    # Snacks
    ("Lays", "Snacks", 40, "chips1.jpg"),
    ("Wafers", "Snacks", 25, "chips2.jpg"),
    ("Chips", "Snacks", 20, "chips3.jpg"),
    
    # Fried Food
    ("Bhaji", "Fried Food", 30, "bhaji.jpg"),   # fixed file name typo
    ("Vada Pav", "Fried Food", 16, "vadapav.jpg"),
    ("French Fries", "Fried Food", 40, "french-fries.jpg"),  # lowercase consistent
    
    # Healthy Choices
    ("Idli", "Healthy Choices", 25, "idli.jpg"),
    ("Dosa", "Healthy Choices", 40, "dosa.jpg"),
    
    # Beverages
    ("Tea", "Beverages", 15, "tea.jpg"),
    ("Coffee", "Beverages", 20, "coffee.jpg"),
    ("Cold Drinks", "Beverages", 20, "drinks.webp"),
    ("Water Bottle", "Beverages", 40, "water.jpg"),
]

# Insert into DB
for item in menu_items:
    c.execute("INSERT INTO menu (name, category, price, image) VALUES (?, ?, ?, ?)", item)

conn.commit()
print("✅ Menu items inserted successfully!")
conn.close()
