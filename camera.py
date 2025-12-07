"""
This file captures camera frames and opens a display window showing frames. Frames cannot go any higher than 30 FPS because it is a hardware limitation
"""

import cv2
import time
import mediapipe as mp

cap = cv2.VideoCapture(0)
pTime = 0

if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

while True:

    # Read frames
    ret, frame = cap.read()

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