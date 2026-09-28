"""
The main Flask application for real-time face recognition.
Handles video streaming, face detection, registration, and data endpoints.
"""

import os
import cv2
import json
import numpy as np
import base64
import threading
import time
from flask import Flask, render_template, Response, request, jsonify
from faces import FaceRecognition

app = Flask(__name__, template_folder="frontend", static_folder="frontend")

fr = FaceRecognition()

# Global variables with thread safety
cap = None
detecting = False
current_frame_faces = []
current_frame_data = []
frame_lock = threading.Lock()
last_frame = None
last_frame_lock = threading.Lock()
unknown_faces_snapshot = []
snapshot_lock = threading.Lock()

def generate_frames():
    """Generate video frames for streaming"""
    global cap, detecting, last_frame
    
    while True:
        if detecting and cap is not None:
            try:
                success, frame = cap.read()
                if not success:
                    # Create a placeholder frame
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Camera Reading Error", (180, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    # Store the latest frame for other threads
                    with last_frame_lock:
                        last_frame = frame.copy()
                    
                    # Detect and recognize faces
                    face_locations, names, encodings = fr.detect_and_recognize(frame)
                    
                    with frame_lock:
                        current_frame_faces.clear()
                        current_frame_data.clear()
                        
                        for (top, right, bottom, left), name, encoding in zip(face_locations, names, encodings):
                            # Draw rectangle and label
                            color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)
                            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                            cv2.putText(frame, name, (left, top - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                            
                            # Extract face region
                            face_crop = frame[top:bottom, left:right]
                            
                            if name == "Unknown":
                                if face_crop.size > 0:
                                    _, buffer = cv2.imencode('.jpg', face_crop)
                                    current_frame_faces.append({
                                        "encoding": encoding,
                                        "image": buffer.tobytes(),
                                        "location": (top, right, bottom, left)
                                    })
                            else:
                                if face_crop.size > 0:
                                    _, buffer = cv2.imencode('.jpg', face_crop)
                                    current_frame_data.append({
                                        "name": name,
                                        "image": buffer.tobytes(),
                                        "extra_data": next((f for f in fr.known_faces_data if f["name"] == name), None)
                                    })
                
                # Encode the frame for streaming
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    time.sleep(0.1)
                
            except Exception as e:
                print(f"Error in frame generation: {e}")
                error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(error_frame, "Processing Error", (200, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                _, buffer = cv2.imencode('.jpg', error_frame)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                time.sleep(0.1)
                
        else:
            # Create a "stopped" frame
            stopped_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(stopped_frame, "Detection Stopped", (180, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(stopped_frame, "Click 'Start Detection'", (160, 280), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            _, buffer = cv2.imencode('.jpg', stopped_frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(1)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/faces_count')
def faces_count():
    with frame_lock:
        total_faces = len(current_frame_faces) + len(current_frame_data)
    return jsonify({"faces": total_faces})

@app.route('/toggle_detection', methods=['POST'])
def toggle_detection():
    global cap, detecting
    action = request.json.get("action")
    
    if action == "start":
        if not detecting:
            try:
                # Try to open camera
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(1)  # Try secondary camera
                
                if cap.isOpened():
                    # Set camera properties
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    detecting = True
                    
                    # Clear previous data
                    with frame_lock:
                        current_frame_faces.clear()
                        current_frame_data.clear()
                    
                    return jsonify({
                        "success": True, 
                        "status": "started",
                        "message": "Camera started successfully"
                    })
                else:
                    return jsonify({
                        "success": False,
                        "message": "Cannot access camera. Please make sure a webcam is connected and not in use by another application."
                    })
                    
            except Exception as e:
                return jsonify({
                    "success": False,
                    "message": f"Error starting camera: {str(e)}"
                })
        else:
            return jsonify({
                "success": True,
                "status": "already_running",
                "message": "Detection is already running"
            })
    
    elif action == "stop":
        detecting = False
        if cap is not None:
            cap.release()
            cap = None
        
        with frame_lock:
            current_frame_faces.clear()
            current_frame_data.clear()
        
        return jsonify({
            "success": True,
            "status": "stopped",
            "message": "Detection stopped"
        })
    
    return jsonify({
        "success": False,
        "message": "Invalid action"
    })

@app.route('/register_face', methods=['POST'])
def register_face():
    try:
        idx = int(request.form.get("index"))
        name = request.form.get("name", "").strip()
        dob = request.form.get("dob", "").strip()
        nid = request.form.get("nid", "").strip()
        
        if not name:
            return jsonify({
                "success": False,
                "message": "Name is required"
            })
        
        extra_data = {}
        if dob:
            extra_data["dob"] = dob
        if nid:
            extra_data["national_id"] = nid
        
        with frame_lock:
            # Take a snapshot of current unknown faces for reference
            unknown_snapshot = current_frame_faces.copy()
            
            if idx >= len(unknown_snapshot):
                return jsonify({
                    "success": False,
                    "message": "Face no longer available. Please refresh the list."
                })
            
            face = unknown_snapshot[idx]
            face_image = cv2.imdecode(
                np.frombuffer(face["image"], np.uint8), 
                cv2.IMREAD_COLOR
            )
            
            # Register the face
            success = fr.register_face(
                face["encoding"], 
                name, 
                face_image, 
                extra_data
            )
            
            if success:
                # Remove this face from current frame faces
                if idx < len(current_frame_faces):
                    current_frame_faces.pop(idx)
                
                return jsonify({
                    "success": True,
                    "message": f"{name} registered successfully!"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Failed to register face"
                })
                
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        })

@app.route('/known_faces_list')
def known_faces_list():
    """Return list of all registered faces (static data)"""
    try:
        faces_list = []
        known_faces = fr.load_known_faces()
        
        for face in known_faces:
            try:
                img_path = os.path.join("faces", face["filename"])
                if os.path.exists(img_path):
                    img = cv2.imread(img_path)
                    if img is not None:
                        _, buffer = cv2.imencode('.jpg', img)
                        img_b64 = base64.b64encode(buffer).decode('utf-8')
                        
                        face_data = {
                            "name": face["name"],
                            "image": img_b64,
                            "extra_data": {
                                k: v for k, v in face.items() 
                                if k not in ["name", "filename", "encoding"]
                            }
                        }
                        faces_list.append(face_data)
            except Exception as e:
                print(f"Error loading face {face.get('name', 'Unknown')}: {e}")
        
        return jsonify(faces_list)
        
    except Exception as e:
        print(f"Error in known_faces_list: {e}")
        return jsonify([])

@app.route('/static_unknown_faces')
def static_unknown_faces():
    """Return a static snapshot of current unknown faces"""
    try:
        with frame_lock:
            # Create a snapshot that won't change
            snapshot = []
            for idx, face in enumerate(current_frame_faces):
                img_b64 = base64.b64encode(face["image"]).decode('utf-8')
                snapshot.append({
                    "index": idx,
                    "image": img_b64,
                    "timestamp": time.time()  # For cache busting
                })
        
        return jsonify(snapshot)
        
    except Exception as e:
        print(f"Error in static_unknown_faces: {e}")
        return jsonify([])

@app.route('/update_unknown_snapshot', methods=['POST'])
def update_unknown_snapshot():
    """Update the snapshot of unknown faces"""
    try:
        with frame_lock:
            snapshot = []
            for idx, face in enumerate(current_frame_faces):
                img_b64 = base64.b64encode(face["image"]).decode('utf-8')
                snapshot.append({
                    "index": idx,
                    "image": img_b64,
                    "timestamp": time.time()
                })
        
        return jsonify({
            "success": True,
            "snapshot": snapshot
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        })

@app.route('/detected_faces')
def detected_faces():
    """Return faces detected in current frame"""
    try:
        with frame_lock:
            faces_list = []
            for f in current_frame_data:
                img_b64 = base64.b64encode(f["image"]).decode('utf-8')
                faces_list.append({
                    "name": f["name"],
                    "extra_data": f.get("extra_data"),
                    "image": img_b64
                })
        
        return jsonify(faces_list)
        
    except Exception as e:
        print(f"Error in detected_faces: {e}")
        return jsonify([])

@app.route('/refresh_faces')
def refresh_faces():
    """Force refresh of face data"""
    try:
        fr.load_known_faces()
        return jsonify({
            "success": True,
            "message": "Faces database refreshed"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error refreshing faces: {str(e)}"
        })

@app.route('/camera_status')
def camera_status():
    """Check if camera is available"""
    try:
        test_cap = cv2.VideoCapture(0)
        available = test_cap.isOpened()
        test_cap.release()
        return jsonify({
            "available": available,
            "detecting": detecting,
            "message": "Camera available" if available else "No camera detected"
        })
    except Exception as e:
        return jsonify({
            "available": False,
            "detecting": detecting,
            "message": f"Error: {str(e)}"
        })

@app.route('/test_camera')
def test_camera():
    """Test camera endpoint"""
    try:
        test_cap = cv2.VideoCapture(0)
        if test_cap.isOpened():
            ret, frame = test_cap.read()
            test_cap.release()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame)
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                return jsonify({
                    "success": True,
                    "image": img_b64,
                    "message": "Camera is working"
                })
        
        return jsonify({
            "success": False,
            "message": "Camera test failed"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)