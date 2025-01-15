from flask import Flask
from controllers.emotion_controller import create_emotion_blueprint
from controllers.user_controller import create_user_blueprint
from controllers.class_controller import create_class_blueprint
from controllers.session_controller import create_session_blueprint
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from flask_cors import CORS

# Load environment variables
load_dotenv()

# Initialize the Flask application
app = Flask(__name__)

# Enable CORS
CORS(app)

# Load configuration from config.py
app.config.from_object('config.Config')

# Configure MongoDB
client = MongoClient(app.config['MONGO_URI'])
db = client[app.config['MONGO_DB_NAME']]

# Register blueprints
app.register_blueprint(create_emotion_blueprint(db, app.config), url_prefix='/emotion')
app.register_blueprint(create_user_blueprint(db, app.config), url_prefix='/user')
app.register_blueprint(create_class_blueprint(db, app.config), url_prefix='/class')
app.register_blueprint(create_session_blueprint(db, app.config), url_prefix='/session')

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=app.config['PORT'])