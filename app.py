import os, cv2, json, numpy as np, base64
from flask import Flask, render_template, Response, request, jsonify
from faces import FaceRecognition

app = Flask(__name__, template_folder="frontend", static_folder="frontend")

fr = FaceRecognition()

cap = None
detecting = False
current_frame_faces = []  # list of dicts: {"encoding":..., "image":...}
current_frame_data = []   # list of dicts: {"name":..., "image":..., "extra_data":...}

def generate_frames():
    global cap, current_frame_faces, current_frame_data
    while True:
        if detecting and cap:
            success, frame = cap.read()
            if not success:
                continue

            face_locations, names, encodings = fr.detect_and_recognize(frame)
            current_frame_faces = []
            current_frame_data = []

            for (top, right, bottom, left), name, encoding in zip(face_locations, names, encodings):
                color = (0, 0, 255) if name == "Unknown" else (0, 128, 255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                face_crop = frame[top:bottom, left:right]
                if name == "Unknown":
                    _, buffer = cv2.imencode('.jpg', face_crop)
                    current_frame_faces.append({"encoding": encoding, "image": buffer.tobytes()})
                else:
                    current_frame_data.append({
                        "name": name,
                        "image": face_crop,
                        "extra_data": next((f for f in fr.load_known_faces() if f["name"]==name), None)
                    })

            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+buffer.tobytes()+b'\r\n')
        else:
            blank = np.zeros((480,640,3), dtype=np.uint8)
            _, buffer = cv2.imencode('.jpg', blank)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+buffer.tobytes()+b'\r\n')

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/faces_count')
def faces_count():
    return jsonify({"faces": len(current_frame_faces)+len(current_frame_data)})

@app.route('/toggle_detection', methods=['POST'])
def toggle_detection():
    global detecting, cap
    action = request.json.get("action")
    if action == "start":
        if not detecting:
            cap = cv2.VideoCapture(0)
            detecting = True
        return jsonify({"success": True})
    elif action == "stop":
        detecting = False
        if cap:
            cap.release()
            cap = None
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid action"})

@app.route('/register_face', methods=['POST'])
def register_face():
    idx = int(request.form.get("index"))
    name = request.form.get("name")
    dob = request.form.get("dob")
    nid = request.form.get("nid")
    extra_data = {"dob": dob, "national_id": nid} if dob or nid else None

    if idx >= len(current_frame_faces):
        return jsonify({"success": False, "message": "Face no longer available."})

    face = current_frame_faces.pop(idx)
    fr.register_face(face["encoding"], name, cv2.imdecode(np.frombuffer(face["image"], np.uint8), cv2.IMREAD_COLOR), extra_data)
    return jsonify({"success": True, "message": f"{name} registered."})

@app.route('/detected_faces')
def detected_faces():
    faces_list = []
    for f in current_frame_data:
        _, buffer = cv2.imencode('.jpg', f["image"])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        faces_list.append({"name": f["name"], "extra_data": f.get("extra_data"), "image": img_b64})
    return jsonify(faces_list)

@app.route('/unknown_faces')
def unknown_faces():
    unknown_list = []
    for idx, f in enumerate(current_frame_faces):
        img_b64 = base64.b64encode(f["image"]).decode('utf-8')
        unknown_list.append({"index": idx, "image": img_b64})
    return jsonify(unknown_list)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
