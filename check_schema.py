import sqlite3
conn = sqlite3.connect('database/test.db')
cursor = conn.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print("Users table columns:")
for col in columns:
    print(col)
conn.close()
