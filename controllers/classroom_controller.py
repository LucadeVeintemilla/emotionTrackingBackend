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
        data = request.get_json()
        
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
        
        for classroom in classrooms:
            classroom['_id'] = str(classroom['_id'])
            classroom['professor_id'] = str(classroom['professor_id'])
            classroom['students'] = [str(student_id) for student_id in classroom['students']]
        
        return jsonify(classrooms), 200
    
    @classroom_blueprint.route('/<classroom_id>', methods=['PUT'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def update_classroom(current_user, classroom_id):
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "No update data provided"}), 400
            
            if 'name' not in data:
                return jsonify({"error": "Classroom name is required"}), 400
            
            classroom = classrooms_collection.find_one({
                "_id": ObjectId(classroom_id),
                "professor_id": current_user['_id']
            })
            
            if not classroom:
                return jsonify({"error": "Classroom not found or unauthorized"}), 404
            
            update_data = {
                "name": data['name']
            }
            
            if 'students' in data:
                try:
                    students = data['students']
                    if not isinstance(students, list):
                        raise ValueError
                    update_data["students"] = [ObjectId(student_id) for student_id in students]
                except (ValueError, TypeError):
                    return jsonify({"error": "Students must be a valid JSON list of ObjectIds"}), 400
            
            result = classrooms_collection.update_one(
                {"_id": ObjectId(classroom_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                updated_classroom = classrooms_collection.find_one({"_id": ObjectId(classroom_id)})
                updated_classroom['_id'] = str(updated_classroom['_id'])
                updated_classroom['professor_id'] = str(updated_classroom['professor_id'])
                updated_classroom['students'] = [str(student_id) for student_id in updated_classroom['students']]
                
                return jsonify(updated_classroom), 200
            else:
                return jsonify({"message": "No changes made"}), 200
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @classroom_blueprint.route('/<classroom_id>', methods=['DELETE'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def delete_classroom(current_user, classroom_id):
        try:
            classroom = classrooms_collection.find_one({
                "_id": ObjectId(classroom_id),
                "professor_id": current_user['_id']
            })
            
            if not classroom:
                return jsonify({"error": "Classroom not found or unauthorized"}), 404
            
            result = classrooms_collection.delete_one({
                "_id": ObjectId(classroom_id),
                "professor_id": current_user['_id']
            })
            
            if result.deleted_count == 1:
                return jsonify({"message": "Classroom deleted successfully"}), 200
            else:
                return jsonify({"error": "Failed to delete classroom"}), 500
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @classroom_blueprint.route('/<classroom_id>/students', methods=['POST'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def add_student_to_classroom(current_user, classroom_id):
        try:
            data = request.get_json()
            student_ids = data.get('student_ids', [])
            classroom_id_obj = ObjectId(classroom_id)

            classroom = classrooms_collection.find_one({
                "_id": classroom_id_obj,
                "professor_id": current_user['_id']
            })
            
            if not classroom:
                return jsonify({"error": "Classroom not found or unauthorized"}), 404

            student_ids_obj = []
            for student_id in student_ids:
                student_ids_obj.append(ObjectId(student_id))

            result = classrooms_collection.update_one(
                {'_id': classroom_id_obj},
                {'$addToSet': {'students': {'$each': student_ids_obj}}}
            )

            if result.modified_count > 0:
                return jsonify({"message": "Students added successfully"}), 200
            
            return jsonify({"message": "No changes made"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @classroom_blueprint.route('/<classroom_id>/students/remove', methods=['POST'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def remove_students_from_classroom(current_user, classroom_id):
        try:
            data = request.get_json()
            student_ids = data.get('student_ids', [])
            
            if not student_ids:
                return jsonify({"error": "No student IDs provided"}), 400
                
            classroom_id_obj = ObjectId(classroom_id)
            
            classroom = classrooms_collection.find_one({
                "_id": classroom_id_obj,
                "professor_id": current_user['_id']
            })
            
            if not classroom:
                return jsonify({"error": "Classroom not found or unauthorized"}), 404

            student_ids_obj = []
            for student_id in student_ids:
                student_ids_obj.append(ObjectId(student_id))
                
            result = classrooms_collection.update_one(
                {'_id': classroom_id_obj},
                {'$pull': {'students': {'$in': student_ids_obj}}}
            )
            
            return jsonify({"message": "Students removed from classroom successfully"}), 200
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return classroom_blueprint