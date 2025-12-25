"""
This is the face recognition module I settled on. It handles loading known faces,
detecting and recognizing faces in frames, and registering new faces.
"""

import os, json, cv2, face_recognition, numpy as np

FACES_DIR = "faces"
DATA_FILE = os.path.join(FACES_DIR, "data.json")
os.makedirs(FACES_DIR, exist_ok=True)

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
        self.known_encodings, self.known_names = [], []
        self.load_known_faces()

    def load_known_faces(self):
        self.known_encodings, self.known_names = [], []
        for face in data["faces"]:
            self.known_encodings.append(np.array(face["encoding"]))
            self.known_names.append(face["name"])

    def detect_and_recognize(self, frame):
        # Optional downscale for speed
        small_frame = cv2.resize(frame, (0,0), fx=0.5, fy=0.5)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        names = []
        for encoding in face_encodings:
            matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=0.5)
            name = "Unknown"
            if True in matches:
                name = self.known_names[matches.index(True)]
            names.append(name)

        # scale back coordinates to full frame size
        scaled_locs = [(t*2, r*2, b*2, l*2) for (t, r, b, l) in face_locations]
        return scaled_locs, names, face_encodings

    def register_face(self, face_encoding, name, face_image, extra_data=None):
        idx = len(data["faces"]) + 1
        filename = f"{name}_{idx}.jpg"
        path = os.path.join(FACES_DIR, filename)
        cv2.imwrite(path, face_image)

        entry = {
            "name": name,
            "filename": filename,
            "encoding": face_encoding.tolist()
        }
        if extra_data:
            entry.update(extra_data)

        data["faces"].append(entry)
        save_data()
        self.known_encodings.append(face_encoding)
        self.known_names.append(name)
