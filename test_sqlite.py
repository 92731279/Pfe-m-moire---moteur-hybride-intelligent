import sqlite3
conn = sqlite3.connect('data/geonames/db/geonames.sqlite')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(c.fetchall())
