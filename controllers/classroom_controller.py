from user_utils import token_required, is_professor
from flask import Blueprint, request, jsonify
from bson import ObjectId
import json

def create_classroom_blueprint(db, config):
    classrooms_collection = db['classrooms']
    classroom_blueprint = Blueprint('classroom', __name__)
    SECRET_KEY = config['SECRET_KEY']

    @classroom_blueprint.route('/create_classroom', methods=['POST'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def create_classroom(current_user):
        # Parse JSON data from request body
        data = request.get_json()
        
        # Validate JSON data
        if not data or 'name' not in data or 'students' not in data:
            return jsonify({"error": "Classroom must have a name and a list of students"}), 400

        try:
            students = data['students']
            if not isinstance(students, list):
                raise ValueError
            students = [ObjectId(student_id) for student_id in students]
        except (ValueError, TypeError):
            return jsonify({"error": "Students must be a valid JSON list of ObjectIds"}), 400

        classroom = {
            "name": data['name'],
            "professor_id": current_user['_id'],
            "students": students
        }
        
        result = classrooms_collection.insert_one(classroom)
        classroom['_id'] = str(result.inserted_id)
        return jsonify({"message": "Classroom created successfully"}), 201

    @classroom_blueprint.route('/get_classrooms', methods=['GET'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def get_classrooms(current_user):
        classrooms = list(classrooms_collection.find({"professor_id": current_user['_id']}))
        
        # Convert ObjectId to string
        for classroom in classrooms:
            classroom['_id'] = str(classroom['_id'])
            classroom['professor_id'] = str(classroom['professor_id'])
            classroom['students'] = [str(student_id) for student_id in classroom['students']]
        
        return jsonify(classrooms), 200
    
    return classroom_blueprint