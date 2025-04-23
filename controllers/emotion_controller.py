import base64
import concurrent.futures
import cv2
import uuid
from flask import Blueprint, request, jsonify
from PIL import Image
import numpy as np
from deepface import DeepFace
import io
from user_utils import identify_user, save_emotions_to_user, token_required, is_professor
from bson.objectid import ObjectId
import datetime

def create_emotion_blueprint(db, config):
    SECRET_KEY = config['SECRET_KEY']
    # Create a collection for emotions in the database
    emotions_collection = db['emotions']
    # Create a collection for users in the database
    users_collection = db['users']
    # Create a collection for sessions in the database
    sessions_collection = db['sessions']
    # Create a collection for classrooms in the database
    classrooms_collection = db['classrooms']
    # Create a Flask blueprint for the emotion routes
    emotion_blueprint = Blueprint('emotion', __name__)

    def preprocess_image(img_array):
        # Convert the image to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        # Apply Gaussian blur to the grayscale image
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Equalize the histogram of the blurred image
        equalized = cv2.equalizeHist(blurred)
        # Convert the equalized image back to BGR color space
        preprocessed_img = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
        # Resize the preprocessed image to half its original size
        resized_img = cv2.resize(preprocessed_img, (0, 0), fx=0.5, fy=0.5)
        # Return the resized image and its original dimensions
        return resized_img, img_array.shape[1], img_array.shape[0]

    def preprocess_image(img_array):
        # Convert the image to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        # Apply Gaussian blur to the grayscale image
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Equalize the histogram of the blurred image
        equalized = cv2.equalizeHist(blurred)
        # Convert the equalized image back to BGR color space
        preprocessed_img = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
        # Resize the preprocessed image to half its original size
        resized_img = cv2.resize(preprocessed_img, (0, 0), fx=0.5, fy=0.5)
        # Return the resized image and its original dimensions
        return resized_img, img_array.shape[1], img_array.shape[0]

    def convert_region_to_box(region):
        box = {
            'x': int(region['x']),
            'y': int(region['y']),
            'w': int(region['w']),
            'h': int(region['h']),
            'left_eye': {
                'x': int(region['left_eye'][0]),
                'y': int(region['left_eye'][1])
            },
            'right_eye': {
                'x': int(region['right_eye'][0]),
                'y': int(region['right_eye'][1])
            }
        }
        
        return box

    def analyze_emotion(img_array, detector_backend='mtcnn'):
        # Analyze the image to detect emotions using DeepFace
        results = DeepFace.analyze(img_array, actions=['emotion', 'gender'], detector_backend=detector_backend, enforce_detection=False)
        emotions = []
        
        for result in results:
            # Extract the dominant emotion and its confidence
            dominant_emotion = result['dominant_emotion']
            emotion_confidence = result['emotion'][dominant_emotion]
            dominant_gender = result['dominant_gender']
            
            region = result['region']
            box = convert_region_to_box(region)
            
            # Extract the face region from the image
            _face_region = img_array[box['y']:box['y'] + box['h'], box['x']:box['x'] + box['w']]
            face_region = base64.b64encode(cv2.imencode('.jpg', _face_region)[1]).decode('utf-8')
            
            emotion = {
                'dominant_emotion': dominant_emotion,
                'emotion_confidence': emotion_confidence,
                'dominant_gender': dominant_gender,
                'box': box,
                'face_region': face_region,
            }
            
            emotions.append(emotion)
            
        return emotions

    def draw_boxes(img_array, emotions, scale_x, scale_y):
        # Draw rectangles and emotion text on the image
        for emotion_data in emotions:
            box = emotion_data['box']
            x, y, w, h = box['x'], box['y'], box['w'], box['h']
            x = int(x * scale_x)
            y = int(y * scale_y)
            w = int(w * scale_x)
            h = int(h * scale_y)
            
            # Draw rectangle around the face
            cv2.rectangle(img_array, (x, y), (x + w, y + h), (255, 0, 0), 2)
            
            # Draw points for the eyes
            left_eye_x = box['left_eye'].get('x', 0)
            left_eye_y = box['left_eye'].get('y', 0)
            right_eye_x = box['right_eye'].get('x', 0)
            right_eye_y = box['right_eye'].get('y', 0)
            
            
            radius = 20

            cv2.circle(img_array, (int(left_eye_x * scale_x), int(left_eye_y * scale_y)), radius, (0, 0, 255), -1)
            cv2.circle(img_array, (int(right_eye_x * scale_x), int(right_eye_y * scale_y)), radius, (0, 0, 255), -1)
            
            identified_user = emotion_data['identified_user']
            emotion_text = f"{emotion_data['dominant_emotion']}"
            if identified_user:
                emotion_text = f"{emotion_text} - {identified_user['name']}"
                
            font_scale = 4.0  # Increase this value to make the text larger
            thickness = 2   
            
            # Calculate the position for the text
            text_size, _ = cv2.getTextSize(emotion_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            text_w, text_h = text_size
            text_x = x
            text_y = y - 10 if y - 10 > 10 else y + 10
                
            # Draw rectangle behind the text
            cv2.rectangle(img_array, (text_x, text_y - text_h - 5), (text_x + text_w, text_y + 40), (255, 0, 0), -1)

            # Put the emotion text on the image
            cv2.putText(img_array, emotion_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)

    @emotion_blueprint.route('/process_frame', methods=['POST'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def process_frame(current_user):
        try:
            # Check if an image is included in the request
            if 'image' not in request.files:
                return jsonify({"error": "No image found in request"}), 400
            
            if 'session_id' not in request.form or 'student_id' not in request.form:
                return jsonify({"error": "Missing session_id or student_id"}), 400
            
            session_id = request.form.get('session_id')
            student_id = request.form.get('student_id')
            
            file = request.files['image']
            image = Image.open(file)
            img_array = np.array(image)
            
            if img_array is None or img_array.size == 0:
                return jsonify({"error": "Invalid image data"}), 400
                
            preprocessed_img, original_width, original_height = preprocess_image(img_array)
            detector_backend = request.form.get('detector_backend', 'mtcnn')
            
            session = sessions_collection.find_one({'_id': ObjectId(session_id)})
            
            if not session:
                return jsonify({"error": "Session not found"}), 404
            
            # Use a thread pool to analyze the emotion
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(analyze_emotion, preprocessed_img, detector_backend)
                emotions = future.result()
            
            if not emotions:
                return jsonify({"error": "No emotions detected"}), 404

            scale_x = original_width / preprocessed_img.shape[1]
            scale_y = original_height / preprocessed_img.shape[0]
            
            # Process each detected face to identify the user
            for emotion in emotions:
                try:
                    face_region = emotion.get('face_region')
                    if not face_region:
                        continue
                        
                    face_image = Image.open(io.BytesIO(base64.b64decode(face_region)))
                    face_img_array = np.array(face_image)
                    
                    gender = "female" if emotion.get('dominant_gender') == "Woman" else "male"
                    identified_user = identify_user(face_img_array, users_collection, gender, 'student')
                    emotion['identified_user'] = identified_user
                    
                    if identified_user:
                        emotion_data = {
                            'emotion': emotion['dominant_emotion'],
                            'timestamp': datetime.datetime.utcnow()
                        }
                        
                        if 'student_emotions' not in session:
                            session['student_emotions'] = {}
                            
                        if student_id in session['student_emotions']:
                            session['student_emotions'][student_id].append(emotion_data)
                        else:
                            session['student_emotions'][student_id] = [emotion_data]
                except Exception as e:
                    print(f"Error processing face: {str(e)}")
                    continue
            
            # Update session
            try:
                sessions_collection.update_one(
                    {'_id': ObjectId(session_id)},
                    {'$set': {'student_emotions': session.get('student_emotions', {})}}
                )
            except Exception as e:
                print(f"Error updating session: {str(e)}")
            
            # Store detected emotions
            session = sessions_collection.find_one({'_id': ObjectId(session_id)})
            
            for emotion in emotions:
                emotion_record = {
                    'timestamp': datetime.datetime.utcnow(),
                    'emotion': emotion['dominant_emotion'],
                    'confidence': emotion['emotion_confidence'],
                    'student_id': student_id
                }
                
                sessions_collection.update_one(
                    {'_id': ObjectId(session_id)},
                    {'$push': {'emotions_data': emotion_record}}
                )
            
            # Draw boxes and emotions on the image
            draw_boxes(img_array, emotions, scale_x, scale_y)
            
            # Ensure we can encode the image
            try:
                processed_image = base64.b64encode(cv2.imencode('.jpg', img_array)[1]).decode('utf-8')
            except Exception as e:
                print(f"Error encoding processed image: {str(e)}")
                return jsonify({"error": "Error encoding processed image"}), 500
                
            return jsonify({
                'emotions': emotions,
                'detector_backend': detector_backend,
                'processed_image': processed_image
            }), 200

        except Exception as e:
            print(f"Error in process_frame: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return jsonify({"error": "Error analyzing emotion", "message": str(e)}), 500

    @emotion_blueprint.route('/status', methods=['GET'])
    def status():
        return jsonify({"message": "Emotion Tracking Backend Running"}), 200

    @emotion_blueprint.route('/detectors', methods=['GET'])
    def get_detectors():
        detectors = {
            'opencv': {
                'description': 'OpenCV is an open-source computer vision and machine learning software library.',
                'pros': ['Fast', 'Widely used', 'Supports many languages'],
                'cons': ['Less accurate for face detection compared to other models']
            },
            'ssd': {
                'description': 'SSD (Single Shot MultiBox Detector) is a popular object detection model.',
                'pros': ['Fast', 'Good accuracy'],
                'cons': ['May not be as accurate as more complex models']
            },
            'mtcnn': {
                'description': 'MTCNN (Multi-task Cascaded Convolutional Networks) is a face detection model.',
                'pros': ['High accuracy', 'Good for face detection'],
                'cons': ['Slower than some other models']
            },
            'retinaface': {
                'description': 'RetinaFace is a robust single-stage face detector.',
                'pros': ['Very high accuracy', 'Robust'],
                'cons': ['Requires more computational resources']
            },
            'mediapipe': {
                'description': 'MediaPipe is a cross-platform framework for building multimodal applied ML pipelines.',
                'pros': ['Versatile', 'Good accuracy'],
                'cons': ['Can be complex to set up']
            }
        }
        return jsonify({'detectors': detectors}), 200

    @emotion_blueprint.route('/session/<session_id>/stats', methods=['GET'])
    @token_required(db, SECRET_KEY)
    @is_professor
    def get_session_stats(current_user, session_id):
        try:
            session = sessions_collection.find_one({'_id': ObjectId(session_id)})
            if not session:
                return jsonify({"error": "Session not found"}), 404

            emotions_data = session.get('emotions_data', [])
            print("DEBUG: emotions_data count:", len(emotions_data))
            print("DEBUG: emotions_data sample:", emotions_data[:2])

            # Agrupar emociones por estudiante y ordenar por timestamp
            stats_by_student = {}
            for emotion in emotions_data:
                student_id = emotion.get('student_id')
                if not student_id or 'emotion' not in emotion or 'timestamp' not in emotion:
                    continue
                if student_id not in stats_by_student:
                    stats_by_student[student_id] = []
                stats_by_student[student_id].append(emotion)

            # Ordenar emociones por timestamp para cada estudiante
            for student_id in stats_by_student:
                stats_by_student[student_id].sort(
                    key=lambda x: x.get('timestamp')
                )

            final_stats = []
            emotion_types = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']

            for student_id, emotions in stats_by_student.items():
                if not emotions:
                    continue
                mid_point = len(emotions) // 2
                before_emotions = emotions[:mid_point]
                after_emotions = emotions[mid_point:]

                before_counts = {emotion: 0 for emotion in emotion_types}
                after_counts = {emotion: 0 for emotion in emotion_types}

                for e in before_emotions:
                    emotion = e['emotion'].lower()
                    if emotion in emotion_types:
                        before_counts[emotion] += 1

                for e in after_emotions:
                    emotion = e['emotion'].lower()
                    if emotion in emotion_types:
                        after_counts[emotion] += 1

                print(f"DEBUG: student_id={student_id} before={before_counts} after={after_counts}")

                final_stats.append({
                    'student_id': student_id,
                    'before': before_counts,
                    'after': after_counts,
                    'total_frames': len(emotions)
                })

            print("DEBUG: final_stats:", final_stats)

            return jsonify({
                'stats': final_stats,
                'session_id': session_id,
                'emotion_types': emotion_types
            }), 200

        except Exception as e:
            print(f"Error in get_session_stats: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    return emotion_blueprint