from deepface import DeepFace
from datetime import datetime
import os
from bson.objectid import ObjectId
import jwt
from functools import wraps
from flask import request, jsonify
import numpy as np
import time

def token_required(db, secret_key):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                token = request.headers['Authorization'].split(" ")[1]
            if not token:
                return jsonify({"error": "Token is missing!"}), 401
            try:
                data = jwt.decode(token, secret_key, algorithms=['HS256'])
                current_user = db['users'].find_one({"_id": ObjectId(data['user_id'])})
            except:
                return jsonify({"error": "Token is invalid!"}), 401
            return f(current_user, *args, **kwargs)
        return decorated_function
    return decorator

def is_professor(f):
    @wraps(f)
    def decorated_function(current_user, *args, **kwargs):
        if current_user['role'] != 'professor':
            return jsonify({"error": "Only professors can perform this action!"}), 403
        return f(current_user, *args, **kwargs)
    return decorated_function

def is_self(f):
    @wraps(f)
    def decorated_function(current_user, *args, **kwargs):
        user_id = request.json.get('user_id')
        if str(current_user['_id']) != user_id:
            return jsonify({"error": "You can only update your own profile!"}), 403
        return f(current_user, *args, **kwargs)
    return decorated_function

def identify_users(image_path, users_collection):
    try:
        results = DeepFace.find(img_path=image_path, db_path="user_images", enforce_detection=False)
        identified_users = []
        seen_users = set()
        
        for result in results:
            user_image_path = result['identity'][0]
            user = users_collection.find_one({"images": user_image_path})
            
            if user:
                user_id = str(user['_id'])  # Convert ObjectId to string
                if user_id not in seen_users:
                    user['_id'] = str(user['_id'])
                    identified_users.append(user)
                    seen_users.add(user_id)

        return identified_users
    except Exception as e:
        print(f"Error identifying users: {e}")
        return []

def identify_user(image_path, users_collection, gender, role):
    try:
        # Construct the image path based on role and gender
        db_path = f"user_images/{role}/{gender}"
        
        results = DeepFace.find(img_path=image_path, db_path=db_path, enforce_detection=False)
        identified_user = None

        if results:
            user_image_path = results[0]['identity'][0]
            user = users_collection.find_one({"images": user_image_path})
            
            if user:
                user['_id'] = str(user['_id'])
                identified_user = user

        return identified_user
    except Exception as e:
        print(f"Error identifying user: {e}")
        return None

def save_emotions_to_user(person_id, emotions, users_collection):
    for emotion_data in emotions:
        emotion_record = {
            "timestamp": datetime.utcnow(),
            "emotion": emotion_data['emotion'],
            "confidence": emotion_data['confidence']
        }
        users_collection.update_one(
            {"_id": person_id},
            {"$push": {"emotions": emotion_record}}
        )