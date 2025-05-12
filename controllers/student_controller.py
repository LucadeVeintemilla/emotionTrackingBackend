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
            if not image_file or not allowed_file(image_file.filename):
                return False, "Invalid image file or extension"
            
            img = Image.open(image_file)
            img.verify()
            
            image_file.seek(0)
            
            img = Image.open(image_file)
            img.load()
            
            image_file.seek(0)
            return True, img
        except Exception as e:
            return False, str(e)

    def register_user(images, user_data):
        user_images = []
        base_folder = 'user_images'
        role_folder = os.path.join(base_folder, user_data['role'])
        gender_folder = os.path.join(role_folder, user_data['gender'])

        if not os.path.exists(gender_folder):
            os.makedirs(gender_folder)

        for image in images:
            try:
                filename = f"{uuid.uuid4().hex}.jpg"
                image_path = os.path.join(gender_folder, filename)
                
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                image.save(image_path, format='JPEG', quality=95)
                user_images.append(image_path)
            except Exception as e:
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
            if 'name' not in request.form or 'last_name' not in request.form or 'age' not in request.form or 'gender' not in request.form or 'email' not in request.form:
                return jsonify({"error": "Missing user data in request"}), 400

            user_data = {
                "name": request.form.get('name'),
                "last_name": request.form.get('last_name'),
                "age": request.form.get('age'),
                "gender": request.form.get('gender'),
                "email": request.form.get('email'),
                "role": "student",
                "created_by_professor": request.form.get('created_by_professor')
            }

            existing_user = users_collection.find_one({
                "email": user_data["email"],
                "created_by_professor": user_data["created_by_professor"]
            })
            if existing_user:
                return jsonify({"error": "Ya has registrado un estudiante con este correo"}), 400

            files = []
            for key in request.files:
                if key.startswith('image'):
                    files.append(request.files[key])

            validated_images = []
            for file in files:
                is_valid, result = validate_image(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid image: {result}"}), 400
                validated_images.append(result)

            user_id = register_user(validated_images, user_data)
            
            return jsonify({
                "message": "Student registered successfully",
                "user_id": str(user_id)
            }), 201

        except Exception as e:
            print(f"Error in student registration: {str(e)}")
            return jsonify({"error": f"Registration failed: {str(e)}"}), 500

    @student_blueprint.route('/<student_id>', methods=['DELETE'])
    @token_required(db, config['SECRET_KEY'])
    @is_professor
    def delete_student(current_user, student_id):
        try:
            student = users_collection.find_one({
                "_id": ObjectId(student_id),
                "role": "student",
                "created_by_professor": str(current_user['_id'])
            })
            
            if not student:
                return jsonify({"error": "Student not found or unauthorized"}), 404
            
            if 'images' in student and student['images']:
                for image_path in student['images']:
                    if os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                        except Exception as e:
                            print(f"Error deleting image {image_path}: {str(e)}")
            
            result = users_collection.delete_one({"_id": ObjectId(student_id)})
            
            if result.deleted_count == 1:
                return jsonify({"message": "Student deleted successfully"}), 200
            else:
                return jsonify({"error": "Failed to delete student"}), 500
                
        except Exception as e:
            print(f"Error deleting student: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @student_blueprint.route('/<student_id>', methods=['PUT'])
    @token_required(db, config['SECRET_KEY'])
    @is_professor
    def update_student(current_user, student_id):
        try:
            student = users_collection.find_one({
                '_id': ObjectId(student_id),
                'role': 'student',
                'created_by_professor': str(current_user['_id'])
            })
            
            if not student:
                return jsonify({'error': 'Student not found or unauthorized'}), 404

            data = request.get_json()
            
            if not all(key in data for key in ['name', 'last_name', 'email', 'age', 'gender']):
                return jsonify({'error': 'Missing required fields'}), 400

            update_data = {
                'name': data['name'],
                'last_name': data['last_name'],
                'email': data['email'],
                'age': int(data['age']),
                'gender': data['gender']
            }

            result = users_collection.update_one(
                {'_id': ObjectId(student_id)},
                {'$set': update_data}
            )

            if result.modified_count > 0:
                updated_student = users_collection.find_one({'_id': ObjectId(student_id)})
                updated_student['_id'] = str(updated_student['_id'])
                return jsonify(updated_student), 200
            else:
                return jsonify({'error': 'No changes made'}), 304

        except ValueError as e:
            return jsonify({'error': 'Invalid data format'}), 400
        except Exception as e:
            print(f"Error updating student: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500

    return student_blueprint
