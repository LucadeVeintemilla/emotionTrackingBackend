from flask import Blueprint, request, jsonify
from bson.objectid import ObjectId
from user_utils import token_required, is_professor

def create_session_blueprint(db, config):
    sessions_collection = db['sessions']
    session_blueprint = Blueprint('session', __name__)
    SECRET_KEY = config['SECRET_KEY']

    @session_blueprint.route('/create_session', methods=['POST'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def create_session(current_user):
        # sesion has a profesor_id, a name, and id of the classroom
        data = request.get_json()
        if not data or 'name' not in data or 'classroom_id' not in data:
            return jsonify({"error": "Session must have a name and a classroom_id"}), 400
        
        session = {
            "professor_id": current_user['_id'],
            "name": data['name'],
            "classroom_id": ObjectId(data['classroom_id'])
        }
        
        result = sessions_collection.insert_one(session)
        session['_id'] = str(result.inserted_id)
        
        return jsonify({"message": "Session created successfully"}), 201

    @session_blueprint.route('/get_sessions', methods=['GET'])
    @token_required(db, SECRET_KEY)
    def get_sessions(current_user):
        sessions = list(sessions_collection.find({"professor_id": current_user['_id']}))
        for session in sessions:
            session['_id'] = str(session['_id'])
        return jsonify(sessions), 200

    return session_blueprint