import os

class Config:
    PORT = os.getenv('PORT', 3001)  # API port
    DEBUG = os.getenv('DEBUG', True)  # Enable debug mode
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'emotion_db')
    SECRET_KEY = os.getenv('SECRET_KEY', '123456')