# Face Recognition Web App

The project is designed to detect faces in real time, identify them, and display their Name + ID above their detected faces.
It combines computer vision, feature extraction, and real time GUI display to create an interactive system for monitoring or attendance purposes.

## 📦 Installation Guide

### 1️⃣ Requirements

- Python **3.11** (not tested for other versions)
- A working **webcam**
- **pip** (Python package manager)



### 2️⃣ Download the Project

#### For Linux and macOS:
- Extract the zip file & Navigate to the project's directory
- Create a python virtual environment
- Install the required libraries found in requirements.txt

#### For Windows:
- Install Visual Studio (preferably 2022) and Desktop Development with C++ workload
- Install CMake and add it to environment variables
- Extract the zip file & Navigate to the project's directory
- Create a python virtual environment and activate it
- Run each one of these commands separately and **in the same order**:
```
pip install cmake
pip install dlib
pip install face_recognition
pip install opencv-contrib-python flask
```

### 3️⃣ Run and Use the project
1. Run the flask application
```
python app.py
```
2. After running, open your browser and navigate to:
```
http://127.0.0.1:5000
```
3. The web interface will open automatically, showing the **Live Feed** page. From there, you can:
    - Start or stop detection
    - Register new faces
    - View known faces
    - Check system statistics

## 👥 Team Members & Responsibilities

| **Member**         | **Role**                          | **Responsibilities**                                                                                                                                                                                              |
| ------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Khaled Mohamed** | 🧠 *Face Detection*               | - Implemented real-time face detection.<br>- Extracted facial features and performed recognition.<br>- Optimized accuracy and speed of detection in live video.                              |
| **George Bassem**  | 💻 *GUI (Frontend & Integration)* | - Designed and implemented the graphical user interface.<br>- Displayed live camera feed with detected faces and overlays.<br>- Ensured an interactive, clean, and user-friendly experience.           |
| **Mariam Nabeh**   | 📊 *Data Management*              | - Prepared and managed the face dataset.<br>- Labeled each face with correct Name and ID.<br>- Preprocessed images (resizing, grayscale, normalization). |
