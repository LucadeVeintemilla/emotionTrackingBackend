from flask import Blueprint, request, jsonify, send_from_directory
from PIL import Image
import os
import uuid
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash
from user_utils import token_required, is_professor

def create_student_blueprint(db, config):
    users_collection = db['users']
    student_blueprint = Blueprint('student', __name__)
    SECRET_KEY = config['SECRET_KEY']
    UPLOAD_FOLDER = 'user_images'

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

    def validate_image(image_file):
        try:
            # Check if the file exists and has valid extension
            if not image_file or not allowed_file(image_file.filename):
                return False, "Invalid image file or extension"
            
            # Try to open and verify the image
            img = Image.open(image_file)
            img.verify()
            
            # Reset file pointer after verify
            image_file.seek(0)
            
            # Try to actually load the image
            img = Image.open(image_file)
            img.load()
            
            # Reset file pointer again
            image_file.seek(0)
            return True, img
        except Exception as e:
            return False, str(e)

    def register_user(images, user_data):
        user_images = []
        base_folder = 'user_images'
        role_folder = os.path.join(base_folder, user_data['role'])
        gender_folder = os.path.join(role_folder, user_data['gender'])

        # Create the folders if they don't exist
        if not os.path.exists(gender_folder):
            os.makedirs(gender_folder)

        for image in images:
            try:
                # Generate a unique filename
                filename = f"{uuid.uuid4().hex}.jpg"
                image_path = os.path.join(gender_folder, filename)
                
                # Convert image to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Save image to file system
                image.save(image_path, format='JPEG', quality=95)
                user_images.append(image_path)
            except Exception as e:
                # Clean up any saved images if there's an error
                for saved_image in user_images:
                    if os.path.exists(saved_image):
                        os.remove(saved_image)
                raise Exception(f"Error saving image: {str(e)}")

        user_data['images'] = user_images
        result = users_collection.insert_one(user_data)
        user_id = result.inserted_id
        return user_id

    @student_blueprint.route('/register', methods=['POST'])
    @token_required(db, config['SECRET_KEY'])
    @is_professor
    def register_student_route(current_user):
        try:
            # Check if user data are included in the request
            if 'name' not in request.form or 'last_name' not in request.form or 'age' not in request.form or 'gender' not in request.form or 'email' not in request.form:
                return jsonify({"error": "Missing user data in request"}), 400

            # Get user data from the request
            user_data = {
                "name": request.form.get('name'),
                "last_name": request.form.get('last_name'),
                "age": request.form.get('age'),
                "gender": request.form.get('gender'),
                "email": request.form.get('email'),
                "role": "student",
                "created_by_professor": request.form.get('created_by_professor')
            }

            # Check if the user already exists
            existing_user = users_collection.find_one({"email": user_data["email"]})
            if existing_user:
                return jsonify({"error": "User already exists"}), 400

            # Handle image upload
            files = []
            for key in request.files:
                if key.startswith('image'):
                    files.append(request.files[key])

            # Validate each image before processing
            validated_images = []
            for file in files:
                is_valid, result = validate_image(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid image: {result}"}), 400
                validated_images.append(result)

            # Register the user with validated images
            user_id = register_user(validated_images, user_data)
            
            return jsonify({
                "message": "Student registered successfully",
                "user_id": str(user_id)
            }), 201

        except Exception as e:
            print(f"Error in student registration: {str(e)}")
            return jsonify({"error": f"Registration failed: {str(e)}"}), 500

    return student_blueprint
