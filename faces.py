"""
Face Recognition Module - Handles face detection, recognition, registration, and data management.
"""

import os
import json
import cv2
import face_recognition
import numpy as np
from datetime import datetime

FACES_DIR = "faces"
DATA_FILE = os.path.join(FACES_DIR, "data.json")
os.makedirs(FACES_DIR, exist_ok=True)

# Load or initialize face data
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = {"faces": [], "last_updated": str(datetime.now())}
else:
    data = {"faces": [], "last_updated": str(datetime.now())}

def save_data():
    """Save face data to JSON file"""
    data["last_updated"] = str(datetime.now())
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

class FaceRecognition:
    def __init__(self):
        self.known_encodings = []
        self.known_names = []
        self.known_faces_data = []
        self.load_known_faces()

    def load_known_faces(self):
        """Load known faces from data file"""
        self.known_encodings = []
        self.known_names = []
        self.known_faces_data = []
        
        for face in data["faces"]:
            try:
                encoding = np.array(face["encoding"])
                self.known_encodings.append(encoding)
                self.known_names.append(face["name"])
                self.known_faces_data.append(face)
            except Exception as e:
                print(f"Error loading face {face.get('name', 'Unknown')}: {e}")
        
        print(f"Loaded {len(self.known_names)} known faces")
        return self.known_faces_data

    def detect_and_recognize(self, frame):
        """Detect and recognize faces in a frame"""
        # Downscale for better performance
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        names = ["Unknown"] * len(face_encodings)
        
        for i, encoding in enumerate(face_encodings):
            if len(self.known_encodings) == 0:
                continue
            
            # Compare with known faces
            distances = face_recognition.face_distance(self.known_encodings, encoding)
            if len(distances) > 0:
                min_distance = np.min(distances)
                if min_distance < 0.5:  # Lower threshold for better accuracy
                    best_match_index = np.argmin(distances)
                    names[i] = self.known_names[best_match_index]
        
        # Scale coordinates back to original size
        scaled_locations = [(t*2, r*2, b*2, l*2) for (t, r, b, l) in face_locations]
        
        return scaled_locations, names, face_encodings

    def register_face(self, face_encoding, name, face_image, extra_data=None):
        """Register a new face"""
        try:
            # Check if name already exists
            for face in data["faces"]:
                if face["name"].lower() == name.lower():
                    # Update existing face
                    face["encoding"] = face_encoding.tolist()
                    face.update(extra_data or {})
                    face["updated_at"] = str(datetime.now())
                    save_data()
                    self.load_known_faces()
                    return True
            
            # Create new face entry
            idx = len(data["faces"]) + 1
            filename = f"{name}_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            path = os.path.join(FACES_DIR, filename)
            
            # Save face image
            cv2.imwrite(path, face_image)
            
            # Create entry
            entry = {
                "name": name,
                "filename": filename,
                "encoding": face_encoding.tolist(),
                "registered_at": str(datetime.now()),
                "updated_at": str(datetime.now())
            }
            
            if extra_data:
                entry.update(extra_data)
            
            data["faces"].append(entry)
            save_data()
            self.load_known_faces()
            
            return True
            
        except Exception as e:
            print(f"Error registering face: {e}")
            return False

    def get_face_count(self):
        """Get total number of registered faces"""
        return len(data["faces"])

    def delete_face(self, name):
        """Delete a registered face"""
        for i, face in enumerate(data["faces"]):
            if face["name"].lower() == name.lower():
                # Remove image file
                img_path = os.path.join(FACES_DIR, face["filename"])
                if os.path.exists(img_path):
                    os.remove(img_path)
                
                # Remove from data
                data["faces"].pop(i)
                save_data()
                self.load_known_faces()
                return True
        return False