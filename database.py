import sqlite3

DB_FILE = "database.db"

class Database():
    def __init__(self):
        self.statements = []
        self.connection = sqlite3.connect(DB_FILE)
        self.cursor = self.connection.cursor()

        self.add_statement('''create table if not exists lines (id INTEGER PRIMARY KEY, name STRING)''')
        self.add_statement('''create table if not exists stations (id INTEGER PRIMARY KEY, key STRING, name STRING, route_id INTEGER, coordinate_id INTEGER, duration INTEGER)''')
        self.add_statement('''create table if not exists coordinates (id INTEGER PRIMARY KEY, lon FLOAT, lat FLOAT, route_id INTEGER)''')
        self.add_statement('''create table if not exists routes (id INTEGER PRIMARY KEY, towards STRING, line_id INTEGER, duration INTEGER)''')

        self.commit()

    def add_statement(self, statement, args = []):
        self.statements.append((statement, args))

    def commit(self):
        map(lambda x: self.cursor.execute(x[0], x[1]), self.statements)
        self.connection.commit()
        self.statements = []

if __name__ == "__main__":
    import os
    try:
        os.remove(DB_FILE)
    except OSError:
        pass
    db = Database()
