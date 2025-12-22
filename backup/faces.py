"""
This is the face recognition module I settled on. It handles loading known faces,
detecting and recognizing faces in frames, and registering new faces.
"""

import os
import json
import cv2
import face_recognition
import numpy as np

# Paths
FACES_DIR = "faces"
DATA_FILE = os.path.join(FACES_DIR, "data.json")

# Ensure folders exist
os.makedirs(FACES_DIR, exist_ok=True)

# Load known faces and metadata
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"faces": []}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class FaceRecognition:
    def __init__(self):
        self.known_encodings = []
        self.known_names = []
        self.load_known_faces()

    def load_known_faces(self):
        """Load known faces from data.json"""
        for face in data["faces"]:
            encoding = np.array(face["encoding"])
            self.known_encodings.append(encoding)
            self.known_names.append(face["name"])

    def detect_and_recognize(self, frame):
        """Detect faces and return locations, names"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        names = []
        for encoding in face_encodings:
            matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=0.5)
            name = "Unknown"

            if True in matches:
                first_match_index = matches.index(True)
                name = self.known_names[first_match_index]

            names.append(name)

        return face_locations, names, face_encodings

    def register_face(self, face_encoding, name, face_image):
        """Save a new face with metadata"""
        idx = len(data["faces"]) + 1
        filename = f"{name}_{idx}.jpg"
        path = os.path.join(FACES_DIR, filename)

        # Save cropped face image
        cv2.imwrite(path, face_image)

        # Update data
        data["faces"].append({
            "name": name,
            "filename": filename,
            "encoding": face_encoding.tolist()
        })
        save_data()

        # Update memory
        self.known_encodings.append(face_encoding)
        self.known_names.append(name)
