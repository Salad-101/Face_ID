"""
This is the main Flask application for real-time face recognition. It streams video from the webcam,
detects and recognizes faces using the FaceRecognition module, and allows registering new faces.
"""

from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
from faces import FaceRecognition

app = Flask(__name__)
fr = FaceRecognition()
cap = cv2.VideoCapture(0)
face_count = 0
current_frame_faces = []  # Store detected faces for registration

def generate_frames():
    global face_count, current_frame_faces
    while True:
        success, frame = cap.read()
        if not success:
            break

        face_locations, names, encodings = fr.detect_and_recognize(frame)
        face_count = len(face_locations)
        current_frame_faces = []

        for (top, right, bottom, left), name, encoding in zip(face_locations, names, encodings):
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.putText(frame, name, (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Save unknown faces for possible registration
            if name == "Unknown":
                face_crop = frame[top:bottom, left:right]
                current_frame_faces.append((encoding, face_crop))

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/faces_count')
def faces_count():
    return jsonify({"faces": face_count})

@app.route('/register_face', methods=['POST'])
def register_face():
    """Register the first unknown face detected in the frame"""
    name = request.form.get("name")
    if not name:
        return jsonify({"success": False, "message": "Name is required."})

    if not current_frame_faces:
        return jsonify({"success": False, "message": "No unknown face to register."})

    encoding, face_crop = current_frame_faces[0]
    fr.register_face(encoding, name, face_crop)
    return jsonify({"success": True, "message": f"Face registered as {name}"})

@app.route('/upload_face', methods=['POST'])
def upload_face():
    """Optional: register face from uploaded image"""
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."})

    file = request.files['file']
    name = request.form.get("name", "Unknown")
    npimg = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    face_locations, _, face_encodings = fr.detect_and_recognize(img)
    if not face_locations:
        return jsonify({"success": False, "message": "No face found in image."})

    # Register first face
    fr.register_face(face_encodings[0], name, img)
    return jsonify({"success": True, "message": f"Face registered as {name}"})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
