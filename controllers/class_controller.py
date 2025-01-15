from flask import Blueprint, request, jsonify
from bson.objectid import ObjectId
from user_utils import token_required, is_professor

def create_class_blueprint(db, config):
    classes_collection = db['classes']
    class_blueprint = Blueprint('class', __name__)
    SECRET_KEY = config['SECRET_KEY']

    @class_blueprint.route('/create_class', methods=['POST'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def create_class(current_user):
        class_data = request.json
        class_data['professor_id'] = current_user['_id']
        result = classes_collection.insert_one(class_data)
        return jsonify({"message": "Class created successfully!", "class_id": str(result.inserted_id)}), 201

    @class_blueprint.route('/get_classes', methods=['GET'])
    @token_required(db, SECRET_KEY)
    def get_classes(current_user):
        classes = list(classes_collection.find({"professor_id": current_user['_id']}))
        for cls in classes:
            cls['_id'] = str(cls['_id'])
        return jsonify(classes), 200

    return class_blueprint