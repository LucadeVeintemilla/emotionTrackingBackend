from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId
from user_utils import token_required, is_professor

def create_semester_blueprint(db, config):
    semester_blueprint = Blueprint('semester', __name__)
    semesters_collection = db.semesters
    users_collection = db.users
    SECRET_KEY = config['SECRET_KEY']

    @semester_blueprint.route('/all', methods=['GET'])
    @token_required(db, SECRET_KEY)
    def get_all_semesters(current_user):
        try:
            if current_user['role'] == 'professor':
                semesters = list(semesters_collection.find({"professor_id": current_user['_id']}))
            else:
                semesters = list(semesters_collection.find())
                
            for semester in semesters:
                semester['_id'] = str(semester['_id'])
                if 'students' in semester and semester['students']:
                    semester['students'] = [str(student_id) for student_id in semester['students']]
                if 'professor_id' in semester:
                    semester['professor_id'] = str(semester['professor_id'])
            
            return jsonify(semesters), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @semester_blueprint.route('/create', methods=['POST'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def create_semester(current_user):
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({"error": "Semester must have a name"}), 400
        
        semester = {
            'name': data['name'],
            'description': data.get('description', ''),
            'created_at': datetime.utcnow(),
            'is_active': True,
            'students': data.get('students', []),
            'professor_id': current_user['_id']
        }
        
        result = semesters_collection.insert_one(semester)
        semester['_id'] = str(result.inserted_id)
        semester['professor_id'] = str(semester['professor_id'])
        
        students = data.get('students', [])
        if students:
            users_collection.update_many(
                {'_id': {'$in': [ObjectId(id) for id in students]}},
                {'$set': {'semester': str(result.inserted_id)}}
            )
        
        return jsonify({"message": "Semester created successfully", "semester": semester}), 201

    @semester_blueprint.route('/<semester_id>', methods=['PUT'])
    def update_semester(semester_id):
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "No update data provided"}), 400
            
            if 'name' not in data:
                return jsonify({"error": "Semester name is required"}), 400
            
            update_data = {
                'name': data['name'],
                'description': data.get('description', '')
            }
            
            result = semesters_collection.update_one(
                {'_id': ObjectId(semester_id)},
                {'$set': update_data}
            )
            
            if result.matched_count == 0:
                return jsonify({"error": "Semester not found"}), 404
                
            if result.modified_count > 0:
                updated_semester = semesters_collection.find_one({'_id': ObjectId(semester_id)})
                updated_semester['_id'] = str(updated_semester['_id'])
                
                if 'students' in updated_semester and updated_semester['students']:
                    updated_semester['students'] = [str(student_id) for student_id in updated_semester['students']]
                
                if 'professor_id' in updated_semester:
                    updated_semester['professor_id'] = str(updated_semester['professor_id'])
                
                return jsonify(updated_semester), 200
            else:
                return jsonify({"message": "No changes made"}), 200
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @semester_blueprint.route('/<semester_id>', methods=['DELETE'])
    def delete_semester(semester_id):
        try:
            semester = semesters_collection.find_one({'_id': ObjectId(semester_id)})
            if not semester:
                return jsonify({"error": "Semester not found"}), 404
            
            if 'students' in semester and semester['students']:
                users_collection.update_many(
                    {'_id': {'$in': semester['students']}},
                    {'$unset': {'semester': ""}}
                )
            
            result = semesters_collection.delete_one({'_id': ObjectId(semester_id)})
            
            if result.deleted_count == 1:
                return jsonify({"message": "Semester deleted successfully"}), 200
            else:
                return jsonify({"error": "Failed to delete semester"}), 500
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @semester_blueprint.route('/<semester_id>/students', methods=['POST'])
    def add_student_to_semester(semester_id):
        try:
            data = request.get_json()
            student_ids = data.get('student_ids', [])
            semester_id = ObjectId(semester_id)

            result = semesters_collection.update_one(
                {'_id': semester_id},
                {'$addToSet': {'students': {'$each': student_ids}}}
            )

            if result.modified_count > 0:
                users_collection.update_many(
                    {'_id': {'$in': [ObjectId(id) for id in student_ids]}},
                    {'$set': {'semester': str(semester_id)}}
                )
                return jsonify({"message": "Students added successfully"}), 200
            
            return jsonify({"error": "No changes made"}), 304

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @semester_blueprint.route('/<semester_id>/students/remove', methods=['POST'])
    def remove_students_from_semester(semester_id):
        try:
            data = request.get_json()
            student_ids = data.get('student_ids', [])
            
            if not student_ids:
                return jsonify({"error": "No student IDs provided"}), 400
                
            semester_id_obj = ObjectId(semester_id)
            
            semester = semesters_collection.find_one({'_id': semester_id_obj})
            if not semester:
                return jsonify({"error": "Semester not found"}), 404
                
            result = semesters_collection.update_one(
                {'_id': semester_id_obj},
                {'$pull': {'students': {'$in': student_ids}}}
            )
            
            users_collection.update_many(
                {
                    '_id': {'$in': [ObjectId(id) for id in student_ids]},
                    'semester': str(semester_id_obj)  
                },
                {'$unset': {'semester': ""}}
            )
            
            return jsonify({"message": "Students removed from semester successfully"}), 200
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return semester_blueprint
