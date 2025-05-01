import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-123'
    DATABASE = os.path.join(os.path.dirname(__file__), 'detections.db')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'app', 'static', 'uploads')
    RESULT_FOLDER = os.path.join(os.path.dirname(__file__), 'app', 'static', 'results')
    MODEL_PATH = 'yolov8n.pt'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'mp4', 'avi', 'mov'}
    MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB