from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect("canteen.db")
c = conn.cursor()

username = "myadmin"
password = "mypassword123"
hashed = generate_password_hash(password)

c.execute("INSERT INTO admins (name, username, password) VALUES (?, ?, ?)", 
          ("Admin", username, hashed))
conn.commit()
conn.close()
print("Admin user created successfully.")