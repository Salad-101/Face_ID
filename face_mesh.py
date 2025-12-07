"""
Docstring for face_mesh
"""

import cv2
import time
import mediapipe as mp



class FaceMeshDetector:
    def __init__(self, static_mode = False, min_detection_confidence=0.65, min_tracking_confidence=0.5, max_num_faces=5):
        
        self.static_mode = static_mode
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.max_num_faces = max_num_faces
        
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=self.max_num_faces,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence)
        
        self.mpDraw = mp.solutions.drawing_utils
        self.drawSpec = self.mpDraw.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=2)
    

    def detect_face_mesh(self, frame):
        
        # Convert BGR to RGB
        self.rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.results = self.face_mesh.process(self.rgb_frame)
        faces = []

        if self.results.multi_face_landmarks:

            for face_landmarks in self.results.multi_face_landmarks:
                self.mpDraw.draw_landmarks(frame, face_landmarks, self.mp_face_mesh.FACEMESH_TESSELATION, self.drawSpec, self.drawSpec)
                
                face = []
                for id, lm in enumerate(face_landmarks.landmark):
                    ih, iw, ic = frame.shape
                    x, y = int(lm.x * iw), int(lm.y * ih)
                    face.append((id, x, y))

                faces.append(face)
        return frame, faces

def main():
    
    # Initialize camera and frametime
    cap = cv2.VideoCapture(0)
    pTime = 0
    detector = FaceMeshDetector()

    # Check for camera open error
    if not cap.isOpened():
        print("Error: Could not open camera.")
        exit
    
    while True:

        # Read frames
        ret, frame = cap.read()
        frame, faces = detector.detect_face_mesh(frame)

        # Check for frame read error
        if not ret:
            print("Error: Could not read frame.")
            break

        # Calculate & show FPS
        cTime = time.time()
        fps = 1 / (cTime - pTime)
        pTime = cTime

        cv2.putText(frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 0), 2)
    
        # Show feed
        cv2.imshow('Camera Feed', frame)
    
        # Quit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release camera and destroy windows
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()