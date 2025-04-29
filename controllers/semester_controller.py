from flask import Blueprint, request, jsonify
from datetime import datetime
from bson import ObjectId

def create_semester_blueprint(db):
    semester_blueprint = Blueprint('semester', __name__)
    semesters_collection = db.semesters
    users_collection = db.users

    @semester_blueprint.route('/all', methods=['GET'])
    def get_all_semesters():
        try:
            semesters = list(semesters_collection.find())
            # Convert ObjectId to string for JSON serialization
            for semester in semesters:
                semester['_id'] = str(semester['_id'])
                # Convert student ObjectIds to strings if they exist
                if 'students' in semester and semester['students']:
                    semester['students'] = [str(student_id) for student_id in semester['students']]
            
            return jsonify(semesters), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @semester_blueprint.route('/create', methods=['POST'])
    def create_semester():
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({"error": "Semester must have a name"}), 400
        
        semester = {
            'name': data['name'],
            'description': data.get('description', ''),
            'created_at': datetime.utcnow(),
            'is_active': True,
            'students': data.get('students', [])
        }
        
        result = semesters_collection.insert_one(semester)
        semester['_id'] = str(result.inserted_id)
        
        # Update students with semester assignment
        students = data.get('students', [])
        if students:
            users_collection.update_many(
                {'_id': {'$in': [ObjectId(id) for id in students]}},
                {'$set': {'semester': str(result.inserted_id)}}
            )
        
        return jsonify({"message": "Semester created successfully", "semester": semester}), 201

    return semester_blueprint
