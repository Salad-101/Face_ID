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
from collections import deque
from flask import Flask, Response, request, jsonify, send_from_directory
from flask_cors import CORS
from faces import FaceRecognition, FACES_DIR

# Serve the built Vue app (run `pnpm build` in frontend/) from frontend/dist.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "frontend", "dist"))

app = Flask(__name__, static_folder=DIST_DIR, static_url_path="")
CORS(app, origins=["http://localhost:5173"])

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

# Real statistics (all guarded by stats_lock)
SERVER_START = time.time()
stats_lock = threading.Lock()
frame_times = deque(maxlen=30)  # timestamps of recently processed frames
known_detections = 0            # face observations matched to a registered person
unknown_detections = 0          # face observations that matched nobody

def generate_frames():
    """Generate video frames for streaming"""
    global cap, detecting, last_frame, known_detections, unknown_detections
    
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

                    n_unknown = sum(1 for n in names if n == "Unknown")
                    with stats_lock:
                        unknown_detections += n_unknown
                        known_detections += len(names) - n_unknown
                        frame_times.append(time.time())
                
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
    if not os.path.exists(os.path.join(DIST_DIR, "index.html")):
        return ("Frontend not built. Run `pnpm build` in frontend/, "
                "or use `pnpm dev` and open http://localhost:5173.", 404)
    return send_from_directory(DIST_DIR, "index.html")

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/faces_count')
def faces_count():
    with frame_lock:
        total_faces = len(current_frame_faces) + len(current_frame_data)
    return jsonify({"faces": total_faces, "fps": current_fps()})

def current_fps():
    """Real processing rate, measured from the timestamps of the last frames."""
    with stats_lock:
        if not detecting or len(frame_times) < 2:
            return 0.0
        if time.time() - frame_times[-1] > 2:  # stalled
            return 0.0
        span = frame_times[-1] - frame_times[0]
        return round((len(frame_times) - 1) / span, 1) if span > 0 else 0.0

def db_size_bytes():
    """Total size of everything in the faces directory (images + data.json)."""
    total = 0
    if os.path.isdir(FACES_DIR):
        for entry in os.scandir(FACES_DIR):
            if entry.is_file():
                total += entry.stat().st_size
    return total

@app.route('/stats')
def stats():
    with stats_lock:
        known, unknown = known_detections, unknown_detections
    total = known + unknown
    return jsonify({
        "total_registered": fr.get_face_count(),
        "recognition_rate": round(known / total * 100) if total else None,
        "known_detections": known,
        "unknown_detections": unknown,
        "db_bytes": db_size_bytes(),
        "uptime_seconds": int(time.time() - SERVER_START),
        "detecting": detecting,
    })

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
                    
                    with stats_lock:
                        frame_times.clear()
                    
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

@app.route('/delete_face', methods=['POST'])
def delete_face():
    """Remove a registered face (database entry and image file)"""
    try:
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "message": "Name is required"}), 400
        
        if fr.delete_face(name):
            return jsonify({"success": True, "message": f"{name} removed"})
        return jsonify({"success": False, "message": f"{name} not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/known_faces_list')
def known_faces_list():
    """Return list of all registered faces (static data)"""
    try:
        faces_list = []
        known_faces = fr.load_known_faces()
        
        for face in known_faces:
            try:
                img_path = os.path.join(FACES_DIR, face["filename"])
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