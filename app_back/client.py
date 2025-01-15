import cv2
import numpy as np
import base64
import requests
import threading

def decode_image(base64_string):
    img_data = base64.b64decode(base64_string)
    np_arr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

def analyze_frame(frame):
    _, img_encoded = cv2.imencode('.jpg', frame)
    img_base64 = base64.b64encode(img_encoded).decode('utf-8')
    response = requests.post(
        'http://localhost:3001/emotion/process_frame',
        files={
            'image': ('frame.jpg', base64.b64decode(img_base64), 'image/jpeg'),
            'detector_backend': (None, 'mctnn')
        }
    )
    return response.json()

def capture_video():
    cap = cv2.VideoCapture(0)
    processed_frame = None

    def update_processed_frame():
        nonlocal processed_frame
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            result = analyze_frame(frame)
            if 'processed_image' in result:
                try:
                    processed_frame = decode_image(result['processed_image'])
                except Exception as e:
                    print(e)

    threading.Thread(target=update_processed_frame, daemon=True).start()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Create a blank image to combine both frames
        combined_frame = np.zeros((frame.shape[0], frame.shape[1] * 2, frame.shape[2]), dtype=np.uint8)

        # Place the real-time frame on the left
        combined_frame[:, :frame.shape[1]] = frame

        # Place the processed frame on the right if available
        if processed_frame is not None:
            combined_frame[:, frame.shape[1]:] = processed_frame

        # Display the combined frame
        cv2.imshow('Real-time and Processed Frames', combined_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

capture_video()