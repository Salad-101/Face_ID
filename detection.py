"""
This is the detection pipeline of the project using MediaPipe and OpenCV.
"""

import cv2
import time
import mediapipe as mp

class FaceDetector:

    # Initialize the FaceDetector with a minimum detection confidence
    def __init__(self, min_detection_confidence=0.65):

        self.min_detection_confidence = min_detection_confidence
        self.mpFaceDetection = mp.solutions.face_detection
        self.faceDetection = self.mpFaceDetection.FaceDetection(min_detection_confidence=self.min_detection_confidence)
        self.mpDraw = mp.solutions.drawing_utils


    def detect_faces(self, frame):

        # Convert BGR images to RGB and store in results
        frameRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.results = self.faceDetection.process(frameRGB)
        faces = []

        # Check for face(s)
        if self.results.detections:
            for id, detection in enumerate(self.results.detections):
                self.mpDraw.draw_detection(frame, detection)                # Draws bounding box
                bboxC = detection.location_data.relative_bounding_box       # Get bounding box
                ih, iw, ic = frame.shape                                    # Get image dimensions
                
                bbox = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                    int(bboxC.width * iw), int(bboxC.height * ih)           # Convert to pixel values
                
                faces.append((id, bbox, detection.score))                   # Append face data
                
                cv2.putText(frame, f'ID: {id}, Score: {int(detection.score[0]*100)}%',
                            (bbox[0], bbox[1]-20), cv2.FONT_HERSHEY_PLAIN,
                            1, (0, 255, 0), 2)                              # Label with ID and Score
        
        return frame, faces

def main():
    # Initialize camera and frametime
    cap = cv2.VideoCapture(0)
    pTime = 0

    if not cap.isOpened():
        print("Error: Could not open camera.")
    
    detector = FaceDetector()

    while True:

        # Read frames
        ret, frame = cap.read()
        frame, faces = detector.detect_faces(frame)

        if not ret:
            print("Error: Could not read frame.")
            break

        # Calculate & show FPS
        cTime = time.time()
        fps = 1 / (cTime - pTime) if pTime != 0 else 0
        pTime = cTime

        print(f"FPS: {fps:.2f}", end="\r")
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