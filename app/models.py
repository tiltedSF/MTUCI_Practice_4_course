import sqlite3
from flask import current_app

def get_db():
    return sqlite3.connect(current_app.config['DATABASE'])

def init_db(app):
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        # Удаляем старую таблицу если существует (осторожно, это удалит данные!)
        cursor.execute("DROP TABLE IF EXISTS detections")
        
        # Создаем новую таблицу с нужной структурой
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            animals_count INTEGER,
            classes TEXT,
            image_path TEXT
        )
        ''')
        conn.commit()
        conn.close()