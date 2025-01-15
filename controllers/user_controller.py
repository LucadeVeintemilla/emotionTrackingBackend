from flask import Blueprint, request, jsonify, send_from_directory
from PIL import Image
import os
import numpy as np
import uuid
import jwt
from functools import wraps
from bson.objectid import ObjectId
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from user_utils import identify_users, identify_user, save_emotions_to_user, token_required, is_self, is_professor

def create_user_blueprint(db, config):
    users_collection = db['users']
    user_blueprint = Blueprint('user', __name__)
    SECRET_KEY = config['SECRET_KEY']
    
    @user_blueprint.route('/user_images/<path:filename>')
    def user_images(filename):
        return send_from_directory('user_images', filename)
    
    def register_user(images, user_data):
        user_images = []
        base_folder = 'user_images'
        role_folder = os.path.join(base_folder, user_data['role'])
        gender_folder = os.path.join(role_folder, user_data['gender'])

        # Create the folders if they don't exist
        if not os.path.exists(gender_folder):
            os.makedirs(gender_folder)

        for image in images:
            # Generate a unique filename
            filename = f"{uuid.uuid4().hex}.jpg"
            image_path = os.path.join(gender_folder, filename)
            
            # Save image to file system
            image.save(image_path)
            user_images.append(image_path)

        user_data['images'] = user_images
        result = users_collection.insert_one(user_data)
        user_id = result.inserted_id
        return user_id

    @user_blueprint.route('/register', methods=['POST'])
    def register_user_route():
        try:
            # Check if images and user data are included in the request
            if 'images' not in request.files or 'name' not in request.form or 'last_name' not in request.form or 'age' not in request.form or 'gender' not in request.form or 'email' not in request.form or 'role' not in request.form:
                return jsonify({"error": "Missing images or user data in request"}), 400

            # Get user data from the request
            name = request.form.get('name')
            last_name = request.form.get('last_name')
            age = request.form.get('age')
            gender = request.form.get('gender')
            email = request.form.get('email')
            role = request.form.get('role')

            # Get the list of image files from the request
            files = request.files.getlist('images')

            if role == 'professor':
                if len(files) != 1:
                    return jsonify({"error": "Professors must upload exactly one image."}), 400
                password = request.form.get('password')
                if not password:
                    return jsonify({"error": "Professors must provide a password."}), 400
                hashed_password = generate_password_hash(password)
                user_data = {
                    "name": name,
                    "last_name": last_name,
                    "age": age,
                    "gender": gender,
                    "email": email,
                    "role": role,
                    "password": hashed_password
                }
            elif role == 'student':
                if len(files) < 3:
                    return jsonify({"error": "Students must upload at least 3 images."}), 400
                user_data = {
                    "name": name,
                    "last_name": last_name,
                    "age": age,
                    "gender": gender,
                    "email": email,
                    "role": role
                }
            else:
                return jsonify({"error": "Invalid role specified."}), 400

            # Check if the user already exists
            existing_user = users_collection.find_one({"email": email})
            if existing_user:
                return jsonify({"error": "User already exists"}), 400

            # Convert files to PIL images
            images = [Image.open(file) for file in files]

            # Register the user
            user_id = register_user(images, user_data)
            token = jwt.encode({
                    'user_id': str(user_id),
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                }, SECRET_KEY, algorithm='HS256')
                
            return jsonify({"token": token}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @user_blueprint.route('/login', methods=['POST'])
    def login():
        try:
            if 'email' not in request.form or 'password' not in request.form:
                return jsonify({"error": "Missing email or password in request"}), 400

            email = request.form.get('email')
            password = request.form.get('password')
            user = users_collection.find_one({"email": email})

            if user and user['role'] == 'professor' and check_password_hash(user['password'], password):
                token = jwt.encode({
                    'user_id': str(user['_id']),
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                }, SECRET_KEY, algorithm='HS256')
                return jsonify({"token": token}), 200
            else:
                return jsonify({"error": "Invalid email or password"}), 401
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @user_blueprint.route('/identify_users_by_image', methods=['POST'])
    def identify_users_by_image_route():
        try:
            # Check if the image is included in the request
            if 'image' not in request.files:
                return jsonify({"error": "Missing image in request"}), 400

            # Get the image file from the request
            file = request.files['image']
            image = Image.open(file)

            # Convert the image to a numpy array
            image_array = np.array(image)

            # Attempt to identify the users using the provided image
            identified_users = identify_users(image_array, users_collection)
            for user in identified_users:
                print(user['name'])
            if identified_users:
                return jsonify({"message": "Users identified successfully", "users": identified_users}), 200
            else:
                return jsonify({"message": "No users could be identified"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @user_blueprint.route('/identify_user_by_image', methods=['POST'])
    def identify_user_by_image_route():
        try:
            # Check if the image is included in the request
            if 'image' not in request.files:
                return jsonify({"error": "Missing image in request"}), 400

            # Get the image file from the request
            file = request.files['image']
            image = Image.open(file)

            # Convert the image to a numpy array
            image_array = np.array(image)

            # Attempt to identify the users using the provided image
            identified_user = identify_user(image_array, users_collection)

            if identified_user:
                return jsonify({"message": "User identified successfully", "user": identified_user}), 200
            else:
                return jsonify({"message": "No user could be identified"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @user_blueprint.route('/me', methods=['GET'])
    @token_required(db, SECRET_KEY)
    def get_user_info(current_user):
        if not current_user:
            return jsonify({"error": "User not found!"}), 404
        
        current_user['_id'] = str(current_user['_id'])
        return jsonify(current_user), 200
    
    @user_blueprint.route('/update_profile', methods=['PUT'])
    @token_required(db, SECRET_KEY)
    @is_professor
    @is_self
    def update_profile(current_user):
        update_data = request.json.get('update_data', {})
        if 'password' in update_data:
            update_data['password'] = generate_password_hash(update_data['password'])
        
        users_collection.update_one({"_id": ObjectId(current_user['_id'])}, {"$set": update_data})
        return jsonify({"message": "Profile updated successfully!"}), 200
    
    return user_blueprint