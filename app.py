from flask import Flask, request, jsonify
from controllers.emotion_controller import create_emotion_blueprint
from controllers.user_controller import create_user_blueprint
from controllers.classroom_controller import create_classroom_blueprint
from controllers.session_controller import create_session_blueprint
from controllers.semester_controller import create_semester_blueprint
from controllers.student_controller import create_student_blueprint
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from flask_cors import CORS

# Load environment variables
load_dotenv()

def create_app(config):
    # Initialize the Flask application
    app = Flask(__name__)

    # Enable CORS
    CORS(app)

    # Load configuration from config.py
    app.config.from_object(config)

    # Configure MongoDB
    client = MongoClient(app.config['MONGO_URI'])
    db = client[app.config['MONGO_DB_NAME']]

    # Register blueprints
    app.register_blueprint(create_emotion_blueprint(db, app.config), url_prefix='/emotion')
    app.register_blueprint(create_user_blueprint(db, app.config), url_prefix='/user')
    app.register_blueprint(create_classroom_blueprint(db, app.config), url_prefix='/classroom')
    app.register_blueprint(create_session_blueprint(db, app.config), url_prefix='/session')
    app.register_blueprint(create_semester_blueprint(db), url_prefix='/semester')
    app.register_blueprint(create_student_blueprint(db, app.config), url_prefix='/student')

    return app

if __name__ == '__main__':
    app = create_app('config.Config')
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=app.config['PORT'])