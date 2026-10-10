# Face ID

A real-time face recognition web app. It reads a live webcam feed, identifies people who have been registered, captures faces it doesn't recognize, and lets you register them from the browser.

- **Backend:** Flask, OpenCV, `face_recognition` (dlib)
- **Frontend:** Vue 3, Tailwind CSS v4, Vite

## Features

- **Live feed:** annotated MJPEG video stream with start/stop detection, live face count and processing FPS.
- **Recognition:** detects faces with dlib's HOG model and matches them against registered 128-d encodings.
- **Unknown face capture:** unrecognized faces are captured as snapshots you can review and register.
- **Registration:** name (required), date of birth and national ID (optional), stored with the face image.
- **Known faces:** browse registered people, see who is currently in frame, and remove entries.
- **Statistics:** registered faces, recognition rate, database size on disk and backend uptime, all measured by the backend.

## How it works

1. The backend opens the camera (index 0, falling back to 1) at 640x480.
2. Each frame is downscaled to 50% and run through the HOG face detector.
3. Every detected face gets a 128-d encoding. It is matched to the closest registered encoding, and counts as a match if the distance is below `0.5`. Otherwise the face is labelled "Unknown".
4. Annotated frames are streamed to the browser as MJPEG (`/video_feed`). The Vue app polls small JSON endpoints for counts, FPS, faces and stats.
5. Registered faces are saved in `faces/data.json` (encodings and metadata) alongside the face images in `faces/`.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and [pnpm](https://pnpm.io/)
- A webcam
- **A C++ build toolchain and CMake**, because `dlib` is compiled from source during install
  - Windows: Visual Studio Build Tools ("Desktop development with C++") and CMake
  - Ubuntu/Debian: `sudo apt install build-essential cmake`
  - macOS: `xcode-select --install` and `brew install cmake`

## Getting started

### Development (two terminals)

```bash
# Terminal 1: backend (http://localhost:5000)
cd backend
uv sync
uv run src/app.py

# Terminal 2: frontend (http://localhost:5173)
cd frontend
pnpm install
pnpm dev
```

Open <http://localhost:5173>. Vite proxies all API calls to the backend, so no extra CORS setup is needed.

### Single server (production-style)

```bash
cd frontend
pnpm install
pnpm build

cd ../backend
uv run src/app.py
```

Open <http://localhost:5000>. Flask serves the built app from `frontend/dist`.

> Run the backend from the `backend/` directory. The `faces/` data folder is created relative to where you start the server (`backend/faces/`), so starting it from elsewhere creates a separate, empty database.

## Usage

1. Go to **Live Feed** and press start to begin detection.
2. Faces that aren't recognized are captured automatically. Open **Register New**, pick one, enter a name (and optionally date of birth and national ID) and save.
3. Registered people are labelled by name on the live feed from then on.
4. **Known Faces** lists everyone registered and lets you remove entries.
5. **Statistics** shows live system metrics.

## Project structure

```
Face ID/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   └── src/
│       ├── app.py        # Flask app: video stream, REST API, stats, serves frontend/dist
│       └── faces.py      # Detection, matching, registration, persistence
└── frontend/
    ├── index.html
    ├── vite.config.js    # Tailwind plugin + dev proxy to the backend
    └── src/
        ├── main.js
        ├── App.vue       # All pages: live feed, known faces, register, statistics
        └── style.css     # Tailwind import and theme colours
```

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serves the built frontend |
| GET | `/video_feed` | MJPEG stream with detection overlays |
| POST | `/toggle_detection` | Start or stop detection (opens/releases the camera) |
| GET | `/faces_count` | Faces in the current frame and processing FPS |
| GET | `/stats` | Registered count, recognition rate, database size, uptime |
| GET | `/detected_faces` | Registered people currently in frame |
| GET | `/static_unknown_faces` | Snapshot of unrecognized faces for registration |
| POST | `/update_unknown_snapshot` | Refresh the unknown-face snapshot |
| POST | `/register_face` | Register a face (form: `index`, `name`, `dob`, `nid`) |
| GET | `/known_faces_list` | All registered faces with images |
| POST | `/delete_face` | Remove a registered face (JSON: `name`) |
| GET | `/refresh_faces` | Reload the face database from disk |
| GET | `/camera_status`, `/test_camera` | Check whether a camera is available |

## Configuration

Settings live in the source for now:

| Setting | Location | Default |
|---|---|---|
| Match distance threshold | `backend/src/faces.py` | `0.5` (lower is stricter) |
| Detection model / frame scale | `backend/src/faces.py` | `hog`, 50% |
| Camera resolution | `backend/src/app.py` | 640x480 |
| Server host/port | `backend/src/app.py` | `0.0.0.0:5000` |

## Privacy and security

This app stores **biometric data** (face encodings and images) and optionally **dates of birth and national ID numbers**, as plain files in `backend/faces/`.

- Only register people who have given consent.
- Don't commit `faces/` to version control (see `.gitignore`).
- There is no authentication, and the server listens on all network interfaces in debug mode. Use it on a trusted local network only, and add authentication and disable `debug` before exposing it anywhere else.

## Known limitations

- Each open browser tab on the video feed runs its own detection loop, so detection counters and FPS are over-counted when several tabs are open.
- The recognition rate counts every face in every frame, so someone standing in view counts many times. It is a rate over detections, not over unique people.
- The Known Faces page shows who is in the current frame, not a history of past sightings.
- Matching uses a single encoding per person and HOG detection, so accuracy drops with poor lighting, strong angles, or masks.

## Roadmap ideas

- Detection history and logs
- Multiple encodings per person
- Authentication and encrypted storage
- Configuration through environment variables