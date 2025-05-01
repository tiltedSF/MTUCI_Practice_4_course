from flask import Flask
from flask_caching import Cache
import os
from config import Config
from ultralytics import YOLO
import torch

cache = Cache()
model = None  # Глобальная переменная для модели

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Инициализация модели YOLO
    from ultralytics import YOLO
    app.config['model'] = YOLO(app.config['MODEL_PATH'])
    
    # Инициализация базы данных
    from app.models import init_db
    init_db(app)
    
    # Регистрация маршрутов
    from app.routes import init_routes
    init_routes(app, app.config['model'])
    
    # Создание директорий
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['RESULT_FOLDER'], 'videos'), exist_ok=True)
    
    return app