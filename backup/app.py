"""
This is the flask port for the face detection pipeline
"""
from flask import Flask, render_template, Response, jsonify
import cv2
from face_detect import FaceDetector

app = Flask(__name__)

detector = FaceDetector()
cap = cv2.VideoCapture(0)
face_count = 0

# Route for video feed
def generate_frames():
    global face_count
    while True:
        success, frame = cap.read()
        if not success:
            break

        frame, faces = detector.detect_faces(frame)
        face_count = len(faces)

        # Encode the frame for MJPEG streaming
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/faces_count')
def faces_count():
    return jsonify({"faces": face_count})


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)