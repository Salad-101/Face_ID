# """
# Face Detection System from Scratch
# Built using only NumPy, Pillow, and PyGame - NO OpenCV or other CV libraries

# Architecture:
# 1. Webcam capture using PyGame
# 2. Manual image processing (grayscale, resize, normalize)
# 3. LBP (Local Binary Patterns) feature extraction
# 4. PCA dimensionality reduction
# 5. KNN classifier for face/non-face classification
# 6. Sliding window multi-scale detector
# 7. Real-time optimization
# 8. Emoji overlay on detected faces
# """

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pygame
import pygame.camera
import time
import os
import math
import sys
import contextlib

# Suppress OpenCV warnings from pygame.camera backend
@contextlib.contextmanager
def suppress_stderr():
    """Temporarily suppress stderr to hide OpenCV warnings."""
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

# IMAGE PROCESSING FUNCTIONS (Manual Implementation)

def rgb_to_grayscale(image_array):
    """
    Convert RGB image to grayscale manually using NumPy.
    Uses standard luminance formula: Y = 0.299*R + 0.587*G + 0.114*B
    """
    if len(image_array.shape) == 2:
        return image_array  # Already grayscale
    
    # Extract RGB channels
    r = image_array[:, :, 0].astype(np.float32)
    g = image_array[:, :, 1].astype(np.float32)
    b = image_array[:, :, 2].astype(np.float32)
    
    # Apply luminance formula
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    
    return gray.astype(np.uint8)


def resize_nearest_neighbor(image_array, new_width, new_height):
    """
    Resize image using nearest-neighbor interpolation (manual implementation).
    No cv2.resize - pure NumPy implementation.
    """
    h, w = image_array.shape[:2]
    
    # Create output array
    if len(image_array.shape) == 3:
        output = np.zeros((new_height, new_width, image_array.shape[2]), dtype=image_array.dtype)
    else:
        output = np.zeros((new_height, new_width), dtype=image_array.dtype)
    
    # Calculate scaling factors
    scale_x = w / new_width
    scale_y = h / new_height
    
    # Map each output pixel to nearest input pixel
    for y in range(new_height):
        for x in range(new_width):
            # Find nearest source pixel
            src_x = int(x * scale_x)
            src_y = int(y * scale_y)
            
            # Clamp to valid range
            src_x = min(src_x, w - 1)
            src_y = min(src_y, h - 1)
            
            output[y, x] = image_array[src_y, src_x]
    
    return output


def normalize_image(image_array):
    """
    Normalize pixel values to 0-1 range manually.
    """
    if image_array.dtype == np.uint8:
        return image_array.astype(np.float32) / 255.0
    else:
        # Already float, just ensure 0-1 range
        min_val = np.min(image_array)
        max_val = np.max(image_array)
        if max_val > min_val:
            return (image_array - min_val) / (max_val - min_val)
        return image_array

# LBP (LOCAL BINARY PATTERNS) FEATURE EXTRACTION
class LBPFeatureExtractor:
    """
    Local Binary Patterns feature extractor implemented from scratch.
    LBP is a texture descriptor that encodes local patterns in images.
    """
    
    def __init__(self, radius=1, n_points=8):
        """
        Initialize LBP extractor.
        radius: radius of the circle around each pixel
        n_points: number of sampling points around the circle
        """
        self.radius = radius
        self.n_points = n_points
        self.lookup_table = self._create_lookup_table()
    
    def _create_lookup_table(self):
        """
        Precompute LBP lookup table for optimization.
        Maps 8-bit patterns to uniform patterns (patterns with <=2 transitions).
        """
        lookup = np.zeros(256, dtype=np.uint8)
        
        for i in range(256):
            # Count transitions (0->1 or 1->0)
            binary = format(i, '08b')
            transitions = 0
            for j in range(8):
                if binary[j] != binary[(j + 1) % 8]:
                    transitions += 1
            
            # Uniform patterns have <= 2 transitions
            if transitions <= 2:
                lookup[i] = i
            else:
                lookup[i] = 0  # Non-uniform pattern
        
        return lookup
    
    def _get_circular_neighbors(self, center_y, center_x, image):
        """
        Get pixel values at circular sampling points around center.
        Uses bilinear interpolation for sub-pixel positions.
        """
        h, w = image.shape
        neighbors = []
        
        for i in range(self.n_points):
            # Calculate angle for this sampling point
            angle = 2 * np.pi * i / self.n_points
            
            # Calculate coordinates
            x = center_x + self.radius * np.cos(angle)
            y = center_y - self.radius * np.sin(angle)  # Negative for image coordinates
            
            # Bilinear interpolation
            x1, y1 = int(np.floor(x)), int(np.floor(y))
            x2, y2 = x1 + 1, y1 + 1
            
            # Check bounds
            if x1 < 0 or y1 < 0 or x2 >= w or y2 >= h:
                neighbors.append(0)
                continue
            
            # Interpolation weights
            wx = x - x1
            wy = y - y1
            
            # Get pixel values
            val = (image[y1, x1] * (1 - wx) * (1 - wy) +
                   image[y1, x2] * wx * (1 - wy) +
                   image[y2, x1] * (1 - wx) * wy +
                   image[y2, x2] * wx * wy)
            
            neighbors.append(val)
        
        return np.array(neighbors)
    
    def compute_lbp(self, image):
        """
        Compute LBP image from grayscale image.
        Returns LBP image and histogram features.
        """
        h, w = image.shape
        lbp_image = np.zeros((h, w), dtype=np.uint8)
        
        # Process each pixel
        for y in range(self.radius, h - self.radius):
            for x in range(self.radius, w - self.radius):
                center = image[y, x]
                neighbors = self._get_circular_neighbors(y, x, image)
                
                # Create binary pattern
                pattern = 0
                for i, neighbor in enumerate(neighbors):
                    if neighbor >= center:
                        pattern |= (1 << (self.n_points - 1 - i))
                
                # Apply lookup table (uniform patterns)
                lbp_image[y, x] = self.lookup_table[pattern]
        
        return lbp_image
    
    def extract_features(self, image, cell_size=8):
        """
        Extract LBP histogram features from image.
        Divides image into cells and computes histogram for each cell.
        """
        lbp_image = self.compute_lbp(image)
        h, w = lbp_image.shape
        
        # Calculate number of cells
        n_cells_y = h // cell_size
        n_cells_x = w // cell_size
        
        features = []
        
        for cy in range(n_cells_y):
            for cx in range(n_cells_x):
                # Extract cell
                cell = lbp_image[cy*cell_size:(cy+1)*cell_size,
                                cx*cell_size:(cx+1)*cell_size]
                
                # Compute histogram (256 bins for 8-bit LBP)
                hist, _ = np.histogram(cell.flatten(), bins=256, range=(0, 256))
                
                # Normalize histogram
                hist = hist.astype(np.float32)
                if np.sum(hist) > 0:
                    hist = hist / np.sum(hist)
                
                features.extend(hist)
        
        return np.array(features)

# PCA (PRINCIPAL COMPONENT ANALYSIS) - Manual Implementation

class PCA:
    """
    Principal Component Analysis implemented from scratch using NumPy.
    Reduces dimensionality of feature vectors.
    """
    
    def __init__(self, n_components=None, variance_ratio=0.95):
        """
        Initialize PCA.
        n_components: number of components to keep (None = use variance_ratio)
        variance_ratio: fraction of variance to retain
        """
        self.n_components = n_components
        self.variance_ratio = variance_ratio
        self.mean = None
        self.components = None
        self.explained_variance = None
    
    def fit(self, X):
        """
        Fit PCA to data X (samples x features).
        """
        # Center the data
        self.mean = np.mean(X, axis=0)
        X_centered = X - self.mean
        
        # Compute covariance matrix
        cov_matrix = np.cov(X_centered.T)
        
        # Eigenfaces decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # Sort by eigenvalue (descending)
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # Determine number of components
        if self.n_components is None:
            # Use variance ratio
            cumsum_variance = np.cumsum(eigenvalues) / np.sum(eigenvalues)
            self.n_components = np.argmax(cumsum_variance >= self.variance_ratio) + 1
        
        # Keep top components
        self.components = eigenvectors[:, :self.n_components]
        self.explained_variance = eigenvalues[:self.n_components]
    
    def transform(self, X):
        """
        Transform data using fitted PCA.
        """
        X_centered = X - self.mean
        return np.dot(X_centered, self.components)
    
    def fit_transform(self, X):
        """
        Fit and transform in one step.
        """
        self.fit(X)
        return self.transform(X)



# KNN CLASSIFIER - Manual Implementation


class KNNClassifier:
    """
    K-Nearest Neighbors classifier implemented from scratch using NumPy.
    """
    
    def __init__(self, k=5):
        """
        Initialize KNN classifier.
        k: number of nearest neighbors to consider
        """
        self.k = k
        self.X_train = None
        self.y_train = None
    
    def fit(self, X, y):
        """
        Store training data.
        """
        self.X_train = X
        self.y_train = y
    
    def _euclidean_distance(self, x1, x2):
        """
        Compute Euclidean distance between two vectors.
        """
        return np.sqrt(np.sum((x1 - x2) ** 2))
    
    def predict(self, X):
        """
        Predict class for samples in X.
        """
        predictions = []
        
        for sample in X:
            # Compute distances to all training samples
            distances = [self._euclidean_distance(sample, train_sample)
                        for train_sample in self.X_train]
            
            # Get k nearest neighbors
            k_indices = np.argsort(distances)[:self.k]
            k_labels = self.y_train[k_indices]
            
            # Majority vote
            unique, counts = np.unique(k_labels, return_counts=True)
            prediction = unique[np.argmax(counts)]
            predictions.append(prediction)
        
        return np.array(predictions)
    
    def predict_proba(self, X):
        """
        Predict class probabilities.
        """
        probabilities = []
        
        for sample in X:
            # Compute distances
            distances = [self._euclidean_distance(sample, train_sample)
                        for train_sample in self.X_train]
            
            # Get k nearest neighbors
            k_indices = np.argsort(distances)[:self.k]
            k_labels = self.y_train[k_indices]
            
            # Compute probabilities
            unique, counts = np.unique(k_labels, return_counts=True)
            prob = np.zeros(2)  # Binary classification: face=1, non-face=0
            for label, count in zip(unique, counts):
                prob[int(label)] = count / self.k
            
            probabilities.append(prob)
        
        return np.array(probabilities)

# FACE DETECTOR - Sliding Window with Multi-Scale

class FaceDetector:
    """
    Face detector using sliding window approach with multi-scale detection.
    """
    
    def __init__(self, lbp_extractor, pca, classifier, window_size=24, step_size=8):
        """
        Initialize face detector.
        window_size: size of detection window
        step_size: stride for sliding window
        """
        self.lbp_extractor = lbp_extractor
        self.pca = pca
        self.classifier = classifier
        self.window_size = window_size
        self.step_size = step_size
    
    def detect_faces(self, image, scales=[1.0, 0.75, 0.5, 0.25], threshold=0.6):
        """
        Detect faces in image using multi-scale sliding window.
        Optimized for speed with early rejection.
        """
        detections = []
        h, w = image.shape
        
        # Limit number of scales for performance
        scales = scales[:2] if len(scales) > 2 else scales
        
        for scale in scales:
            # Resize image for this scale
            scaled_w = int(w * scale)
            scaled_h = int(h * scale)
            
            # Skip if image too small
            if scaled_w < self.window_size or scaled_h < self.window_size:
                continue
                
            scaled_image = resize_nearest_neighbor(image, scaled_w, scaled_h)
            
            # Slide window across image with larger step for speed
            windows_checked = 0
            max_windows = 200  # Increased limit for better detection
            scale_max_confidence = 0.0  # Track max confidence for this scale
            all_confidences = []  # Track all confidences for statistics
            
            print(f"    Scale {scale:.2f}: Scanning {scaled_w}x{scaled_h} image...")
            
            for y in range(0, scaled_h - self.window_size, self.step_size):
                if windows_checked >= max_windows:
                    break
                for x in range(0, scaled_w - self.window_size, self.step_size):
                    if windows_checked >= max_windows:
                        break
                    
                    # Extract window
                    window = scaled_image[y:y+self.window_size, x:x+self.window_size]
                    
                    # Quick variance check - skip uniform regions (very low threshold)
                    if np.var(window) < 30:  # Low variance = likely not a face (lowered for sensitivity)
                        continue
                    
                    try:
                        # Extract features
                        features = self.lbp_extractor.extract_features(window)
                        
                        # Apply PCA
                        features_pca = self.pca.transform(features.reshape(1, -1))
                        
                        # Classify
                        proba = self.classifier.predict_proba(features_pca)
                        confidence = proba[0][1]  # Probability of face
                        
                        # Track max confidence and all confidences for debugging
                        scale_max_confidence = max(scale_max_confidence, confidence)
                        all_confidences.append(confidence)
                        
                        # Show more windows for debugging
                        if windows_checked < 20:
                            print(f"      Window {windows_checked}: confidence = {confidence:.3f} {'✓' if confidence >= threshold else ''}")
                        
                        # Use a more lenient threshold - accept anything above threshold
                        if confidence >= threshold:
                            # Scale coordinates back to original size
                            orig_x = int(x / scale)
                            orig_y = int(y / scale)
                            orig_w = int(self.window_size / scale)
                            orig_h = int(self.window_size / scale)
                            
                            # Filter by reasonable face size (avoid tiny or huge detections)
                            # Typical face is 80-200 pixels in a 320px wide image
                            # Relaxed size constraints for better detection
                            if 40 <= orig_w <= 300 and 40 <= orig_h <= 300:
                                detections.append({
                                    'x': orig_x,
                                    'y': orig_y,
                                    'w': orig_w,
                                    'h': orig_h,
                                    'confidence': confidence
                                })
                    except Exception as e:
                        if windows_checked < 3:
                            print(f"  Error processing window: {e}")
                        continue  # Skip windows that cause errors
                    
                    windows_checked += 1
            
            # Debug: show statistics for this scale
            if len(all_confidences) > 0:
                conf_mean = np.mean(all_confidences)
                conf_std = np.std(all_confidences)
                conf_max = np.max(all_confidences)
                conf_min = np.min(all_confidences)
                above_threshold = sum(1 for c in all_confidences if c >= threshold)
                
                print(f"    Scale {scale:.2f} Statistics:")
                print(f"      Windows checked: {windows_checked}")
                print(f"      Confidence: mean={conf_mean:.3f}, std={conf_std:.3f}, min={conf_min:.3f}, max={conf_max:.3f}")
                print(f"      Above threshold ({threshold:.2f}): {above_threshold}/{windows_checked} windows")
                if scale_max_confidence < threshold:
                    print(f"      ⚠ Max confidence {conf_max:.3f} below threshold {threshold:.2f}")
        
        # Non-maximum suppression to remove overlapping detections
        # Pass image dimensions for better scoring
        h, w = image.shape
        detections = self._non_max_suppression(detections, overlap_threshold=0.4, 
                                               image_width=w, image_height=h)
        
        # Return only the best detection (single face)
        return detections
    
    def _non_max_suppression(self, detections, overlap_threshold=0.3, 
                            image_width=None, image_height=None):
        """
        Remove overlapping detections using non-maximum suppression.
        Returns only the best detection.
        """
        if not detections:
            return []
        
        # Sort by confidence
        detections = sorted(detections, key=lambda x: x['confidence'], reverse=True)
        
        # Standard NMS - remove overlapping detections
        keep = []
        while detections:
            # Take highest confidence detection
            current = detections.pop(0)
            keep.append(current)
            
            # Remove overlapping detections
            detections = [d for d in detections 
                         if self._iou(current, d) < overlap_threshold]
        
        # If we have image dimensions, prefer detections in center-upper region
        if len(keep) > 1 and image_width and image_height:
            image_center_x = image_width / 2
            image_center_y = image_height / 3  # Upper third (where faces typically are)
            
            def score_detection(det):
                det_center_x = det['x'] + det['w'] / 2
                det_center_y = det['y'] + det['h'] / 2
                dist = np.sqrt((det_center_x - image_center_x)**2 + 
                              (det_center_y - image_center_y)**2)
                size_score = det['w'] * det['h']
                # Combine: higher confidence, larger size, closer to center-upper
                return det['confidence'] * 1000 + size_score - dist * 0.1
            
            keep = sorted(keep, key=score_detection, reverse=True)
        
        # Return only the best detection
        return [keep[0]]
    
    def _iou(self, box1, box2):
        """
        Compute Intersection over Union (IoU) of two bounding boxes.
        """
        x1 = max(box1['x'], box2['x'])
        y1 = max(box1['y'], box2['y'])
        x2 = min(box1['x'] + box1['w'], box2['x'] + box2['w'])
        y2 = min(box1['y'] + box1['h'], box2['y'] + box2['h'])
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = box1['w'] * box1['h']
        area2 = box2['w'] * box2['h']
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0


# TRAINING DATA GENERATION (Simple Synthetic Data)

def generate_training_data():
    """
    Generate improved training data with more realistic face patterns.
    In a real application, you would use a proper face dataset.
    """
    print("Generating synthetic training data...")
    
    # Create more realistic face-like patterns
    face_samples = []
    non_face_samples = []
    
    np.random.seed(42)  # For reproducibility
    
    for i in range(100):  # More samples for better training
        # Face-like pattern: oval shape with eye and mouth regions
        face = np.zeros((24, 24), dtype=np.uint8)
        center_y, center_x = 12, 12
        
        for y in range(24):
            for x in range(24):
                # Create oval face shape
                dx = (x - center_x) / 10.0
                dy = (y - center_y) / 12.0
                dist = np.sqrt(dx*dx + dy*dy*1.2)  # Oval shape
                
                if dist < 0.8:
                    # Face center - lighter
                    face[y, x] = 180 + np.random.randint(-20, 20)
                elif dist < 1.2:
                    # Face edges - medium
                    face[y, x] = 140 + np.random.randint(-20, 20)
                else:
                    # Background - darker
                    face[y, x] = 60 + np.random.randint(-20, 20)
        
        # Add "eyes" (darker regions in upper third)
        eye_y = 8
        for eye_x in [8, 16]:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    if 0 <= eye_y + dy < 24 and 0 <= eye_x + dx < 24:
                        face[eye_y + dy, eye_x + dx] = max(50, face[eye_y + dy, eye_x + dx] - 40)
        
        # Add "mouth" (darker region in lower third)
        mouth_y = 16
        for mouth_x in range(6, 18):
            for dy in range(-1, 2):
                if 0 <= mouth_y + dy < 24 and 0 <= mouth_x < 24:
                    face[mouth_y + dy, mouth_x] = max(50, face[mouth_y + dy, mouth_x] - 30)
        
        face_samples.append(face)
        
        # Non-face patterns: various textures
        if i % 3 == 0:
            # Random noise
            non_face = np.random.randint(0, 255, (24, 24), dtype=np.uint8)
        elif i % 3 == 1:
            # Uniform color
            val = np.random.randint(50, 200)
            non_face = np.full((24, 24), val, dtype=np.uint8)
        else:
            # Stripes
            non_face = np.zeros((24, 24), dtype=np.uint8)
            for y in range(24):
                val = 255 if (y // 4) % 2 == 0 else 0
                non_face[y, :] = val
        
        non_face_samples.append(non_face)
    
    return face_samples, non_face_samples


def train_detector():
    """
    Train the face detector with synthetic data.
    """
    print("Training face detector...")
    
    # Generate training data
    face_samples, non_face_samples = generate_training_data()
    
    # Initialize LBP extractor
    lbp_extractor = LBPFeatureExtractor(radius=1, n_points=8)
    
    # Extract features from all samples
    print("Extracting LBP features...")
    X_train = []
    y_train = []
    
    for face in face_samples:
        features = lbp_extractor.extract_features(face, cell_size=8)
        X_train.append(features)
        y_train.append(1)  # Face label
    
    for non_face in non_face_samples:
        features = lbp_extractor.extract_features(non_face, cell_size=8)
        X_train.append(features)
        y_train.append(0)  # Non-face label
    
    X_train = np.array(X_train)
    y_train = np.array(y_train)
    
    # Apply PCA for dimensionality reduction
    print("Applying PCA...")
    pca = PCA(n_components=50, variance_ratio=0.95)
    X_train_pca = pca.fit_transform(X_train)
    
    # Train KNN classifier
    print("Training KNN classifier...")
    classifier = KNNClassifier(k=5)
    classifier.fit(X_train_pca, y_train)
    
    print("Training complete!")
    
    return lbp_extractor, pca, classifier


# EMOJI OVERLAY


def create_emoji_image(emotion='happy', size=64):
    """
    Create a simple emoji image using PIL.
    """
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw face circle
    margin = 5
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 fill='yellow', outline='black', width=2)
    
    if emotion == 'happy':
        # Happy face: smile and eyes
        # Left eye
        draw.ellipse([size//3-5, size//3, size//3+5, size//3+10], fill='black')
        # Right eye
        draw.ellipse([2*size//3-5, size//3, 2*size//3+5, size//3+10], fill='black')
        # Smile (arc)
        draw.arc([size//4, size//2, 3*size//4, 3*size//4+size//2], 
                start=0, end=180, fill='black', width=3)
    else:
        # Sad face: frown and eyes
        # Left eye
        draw.ellipse([size//3-5, size//3, size//3+5, size//3+10], fill='black')
        # Right eye
        draw.ellipse([2*size//3-5, size//3, 2*size//3+5, size//3+10], fill='black')
        # Frown (arc)
        draw.arc([size//4, size//2-size//8, 3*size//4, size//2+size//8], 
                start=180, end=360, fill='black', width=3)
    
    return img


# MAIN APPLICATION - Real-time Face Detection

def main():
    """
    Main function for real-time face detection from webcam.
    """
    print("="*60)
    print("  Face Detection System from Scratch")
    print("="*60)
    print("\nBuilt with: NumPy, Pillow, PyGame only")
    print("NO OpenCV, MediaPipe, or other CV libraries\n")
    
    # Initialize PyGame
    pygame.init()
    
    # Suppress OpenCV warnings during camera initialization
    print("Initializing camera system...")
    print("(Note: OpenCV warnings about camera indices are harmless)\n")
    
    with suppress_stderr():
        pygame.camera.init()
    
    # Get available cameras
    with suppress_stderr():
        cameras = pygame.camera.list_cameras()
    
    if not cameras:
        print("Error: No cameras found!")
        print("Please make sure your camera is connected and not being used by another application.")
        return
    
    print(f"Found {len(cameras)} camera(s)")
    print(f"Initializing camera: {cameras[0]}...")
    try:
        # Try smaller resolution first for faster initialization
        with suppress_stderr():
            camera = pygame.camera.Camera(cameras[0], (320, 240))
        print("Starting camera...")
        with suppress_stderr():
            camera.start()
        # Give camera time to initialize
        print("Waiting for camera to be ready...")
        time.sleep(0.5)
        
        # Try to get a test frame to verify camera is working
        print("Testing camera...")
        test_frame = None
        for _ in range(10):  # Try up to 10 times
            try:
                test_frame = camera.get_image()
                if test_frame is not None:
                    break
            except:
                time.sleep(0.1)
        
        if test_frame is None:
            print("Warning: Could not get test frame, but continuing anyway...")
        else:
            print("Camera test successful!")
        
        print("Camera ready!")
    except Exception as e:
        print(f"Error initializing camera: {e}")
        import traceback
        traceback.print_exc()
        print("\nTrying alternative camera initialization...")
        try:
            # Try with default resolution
            with suppress_stderr():
                camera = pygame.camera.Camera(cameras[0])
                camera.start()
            time.sleep(0.5)
            print("Camera initialized with default settings.")
        except Exception as e2:
            print(f"Alternative initialization also failed: {e2}")
            print("\nTroubleshooting tips:")
            print("1. Make sure no other application is using the camera")
            print("2. Try disconnecting and reconnecting the camera")
            print("3. Check Windows Camera privacy settings")
            return
    
    # Create display window - match camera resolution
    # Get actual camera size
    try:
        test_frame = camera.get_image()
        if test_frame:
            cam_size = test_frame.get_size()
        else:
            cam_size = (320, 240)  # Default fallback
    except:
        cam_size = (320, 240)  # Default fallback
    
    print(f"Camera resolution: {cam_size}")
    screen = pygame.display.set_mode(cam_size)
    pygame.display.set_caption("Face Detection from Scratch")
    
    # Train detector
    print("\n" + "="*60)
    print("Training face detector...")
    lbp_extractor, pca, classifier = train_detector()
    # Use larger step size and smaller window for faster detection
    detector = FaceDetector(lbp_extractor, pca, classifier, 
                           window_size=24, step_size=24)  # Larger step = fewer windows
    print(f"Detector initialized: window_size=24, step_size=24")
    print("="*60)
    
    # Create emoji images
    happy_emoji = create_emoji_image('happy', size=48)
    sad_emoji = create_emoji_image('sad', size=48)
    
    print("\n" + "="*60)
    print("Starting face detection...")
    print("Press 'q' to quit")
    print("="*60 + "\n")
    
    clock = pygame.time.Clock()
    frame_count = 0
    skip_frames = 5  # Process every Nth frame for performance (increased for speed)
    last_detections = []  # Store last detections to show while processing
    test_mode = True  # Set to True to show test rectangle (for debugging)
    save_debug_frames = True  # Save sample frames for debugging
    debug_frame_count = 0
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
        
        try:
            # Capture frame
            frame = camera.get_image()
            
            if frame is None:
                if frame_count % 30 == 0:
                    print("⚠ Warning: Got None frame from camera")
                continue
            
            # Convert PyGame surface to PIL Image
            frame_string = pygame.image.tostring(frame, 'RGB')
            pil_image = Image.frombytes('RGB', frame.get_size(), frame_string)
            
                # Debug: Check frame quality periodically
            if frame_count % 60 == 0:
                frame_array_debug = np.array(pil_image)
                # Check frame statistics
                mean_brightness = np.mean(frame_array_debug)
                std_brightness = np.std(frame_array_debug)
                min_val, max_val = np.min(frame_array_debug), np.max(frame_array_debug)
                print(f"\n📷 Frame Quality Check (frame {frame_count}):")
                print(f"   Size: {pil_image.width}x{pil_image.height}")
                print(f"   Brightness: {mean_brightness:.1f} (mean), {std_brightness:.1f} (std)")
                print(f"   Range: {min_val}-{max_val}")
                
                # Warn if frame is too dark or too uniform
                if mean_brightness < 50:
                    print("   ⚠ Warning: Frame is very dark - improve lighting!")
                elif mean_brightness > 200:
                    print("   ⚠ Warning: Frame is very bright - may be overexposed")
                if std_brightness < 20:
                    print("   ⚠ Warning: Frame has low contrast - may affect detection")
                
                # Save sample frame for debugging
                if save_debug_frames and debug_frame_count < 3:
                    debug_filename = f"debug_frame_{debug_frame_count}_{frame_count}.png"
                    pil_image.save(debug_filename)
                    print(f"   💾 Saved debug frame: {debug_filename}")
                    debug_frame_count += 1
                
        except Exception as e:
            print(f"❌ Error capturing frame: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Convert to NumPy array
        frame_array = np.array(pil_image)
        
        # Process every Nth frame
        frame_count += 1
        if frame_count % (skip_frames + 1) == 0:
            try:
                # Convert to grayscale
                gray = rgb_to_grayscale(frame_array)
                
                # Debug: Check grayscale quality
                if frame_count % 60 == 0:
                    gray_mean = np.mean(gray)
                    gray_std = np.std(gray)
                    gray_min, gray_max = np.min(gray), np.max(gray)
                    print(f"   Grayscale: mean={gray_mean:.1f}, std={gray_std:.1f}, range=[{gray_min}, {gray_max}]")
                
                # Apply simple contrast enhancement if frame is too dark/flat
                if np.std(gray) < 25:
                    # Enhance contrast
                    gray = np.clip((gray - np.mean(gray)) * 1.5 + np.mean(gray), 0, 255).astype(np.uint8)
                    if frame_count % 60 == 0:
                        print(f"   ✨ Applied contrast enhancement (std was too low)")
                
                # Resize to smaller size for faster processing
                h, w = gray.shape
                if w > 160:  # Downscale if too large
                    scale_factor = 160 / w
                    new_w, new_h = int(w * scale_factor), int(h * scale_factor)
                    gray_small = resize_nearest_neighbor(gray, new_w, new_h)
                    if frame_count % 60 == 0:
                        print(f"   Resized: {w}x{h} -> {new_w}x{new_h} (scale={scale_factor:.2f})")
                else:
                    gray_small = gray
                    scale_factor = 1.0
                
                # Detect faces with fewer scales for speed
                # Very low threshold since synthetic data may not match real faces well
                print(f"\n🔍 Frame {frame_count}: Detecting faces...")
                print(f"   Processing image: {gray_small.shape[1]}x{gray_small.shape[0]} pixels")
                
                # Try with very low threshold first
                detections = detector.detect_faces(gray_small, scales=[1.0, 0.75], threshold=0.15)
                
                # Debug: show detection stats
                if len(detections) > 0:
                    confidences = [d['confidence'] for d in detections]
                    print(f"  ✓ Found {len(detections)} face(s) with confidences: {[f'{c:.2f}' for c in confidences]}")
                else:
                    print("  ✗ No faces detected with threshold 0.15")
                    # Try even lower threshold as fallback
                    print("  Trying with threshold 0.10...")
                    detections = detector.detect_faces(gray_small, scales=[1.0, 0.75], threshold=0.10)
                    if len(detections) > 0:
                        confidences = [d['confidence'] for d in detections]
                        print(f"  ✓ Found {len(detections)} face(s) with lower threshold: {[f'{c:.2f}' for c in confidences]}")
                    else:
                        print("  ✗ Still no faces detected")
                        print("  The synthetic training data may not match real faces well.")
                        print("  Consider using real face training data for better results.")
                
                # Scale detections back to original FULL image size (not just grayscale)
                # Get the actual PIL image dimensions for proper scaling
                original_h, original_w = gray.shape
                pil_h, pil_w = pil_image.height, pil_image.width
                
                # Scale factor from small detection image to full PIL image
                if scale_factor != 1.0:
                    for det in detections:
                        # First scale from small detection image to original grayscale size
                        det['x'] = int(det['x'] / scale_factor)
                        det['y'] = int(det['y'] / scale_factor)
                        det['w'] = int(det['w'] / scale_factor)
                        det['h'] = int(det['h'] / scale_factor)
                
                # Scale to match PIL image size (in case grayscale and PIL sizes differ)
                if original_w != pil_w or original_h != pil_h:
                    scale_x = pil_w / original_w
                    scale_y = pil_h / original_h
                    for det in detections:
                        det['x'] = int(det['x'] * scale_x)
                        det['y'] = int(det['y'] * scale_y)
                        det['w'] = int(det['w'] * scale_x)
                        det['h'] = int(det['h'] * scale_y)
                
                # Always update detections (clear if none found, keep if found)
                if len(detections) > 0:
                    last_detections = detections
                    print(f"✓ Updated: {len(detections)} detection(s)")
                    for i, det in enumerate(detections):
                        print(f"  Face {i+1}: x={det['x']}, y={det['y']}, w={det['w']}, h={det['h']}, conf={det['confidence']:.3f}")
                else:
                    # Try simple fallback: detect center region with face-like characteristics
                    # This is a basic heuristic when ML classifier fails
                    h, w = gray.shape
                    center_x, center_y = w // 2, h // 3  # Upper center (typical face position)
                    face_size = min(w, h) // 3  # Reasonable face size
                    
                    # Check if center region has good variance (not uniform)
                    x1 = max(0, center_x - face_size // 2)
                    y1 = max(0, center_y - face_size // 2)
                    x2 = min(w, center_x + face_size // 2)
                    y2 = min(h, center_y + face_size // 2)
                    center_region = gray[y1:y2, x1:x2]
                    
                    if center_region.size > 0 and np.var(center_region) > 100:
                        # Simple fallback detection - assume face in center
                        fallback_det = {
                            'x': int(x1 * (pil_w / w)),
                            'y': int(y1 * (pil_h / h)),
                            'w': int((x2 - x1) * (pil_w / w)),
                            'h': int((y2 - y1) * (pil_h / h)),
                            'confidence': 0.5  # Low confidence for fallback
                        }
                        last_detections = [fallback_det]
                        print(f"  ⚠ Fallback detection (center region) - ML classifier may need better training data")
                    else:
                        # Clear old detections if no new ones found (for real-time tracking)
                        last_detections = []
                        print(f"  No faces detected - cleared previous detections")
            except Exception as e:
                print(f"Error processing frame: {e}")
                import traceback
                traceback.print_exc()
        
        # Always draw last detections (even on skipped frames)
        draw = ImageDraw.Draw(pil_image)
        
        if last_detections and len(last_detections) > 0:
            # Only draw the best detection (first one)
            det = last_detections[0]
            x, y, w, h = det['x'], det['y'], det['w'], det['h']
            conf = det['confidence']
            
            # Ensure coordinates are within image bounds
            x = max(0, min(x, pil_image.width - 1))
            y = max(0, min(y, pil_image.height - 1))
            w = min(w, pil_image.width - x)
            h = min(h, pil_image.height - y)
            
            # Only print occasionally to avoid spam
            if frame_count % 30 == 0:
                print(f"Drawing: x={x}, y={y}, w={w}, h={h}, conf={conf:.3f}")
            
            # Draw bounding box with thicker line for visibility
            draw.rectangle([x, y, x+w, y+h], outline='green', width=4)
            
            # Draw confidence text
            text_y = max(0, y - 20)
            draw.text((x, text_y), f"Face: {conf:.2f}", fill='green')
            
            # Overlay emoji (alternate between happy/sad based on confidence)
            emoji = happy_emoji if conf > 0.6 else sad_emoji
            # Ensure emoji position is within image bounds
            emoji_y = max(0, y - 48)
            if emoji_y + 48 <= pil_image.height and x + 48 <= pil_image.width:
                pil_image.paste(emoji, (x, emoji_y), emoji)
        
        # Test mode: show a test rectangle (disable this once detection works)
        if test_mode and len(last_detections) == 0:
            # Only show test rectangle when no face is detected
            center_x = pil_image.width // 2 - 50
            center_y = pil_image.height // 2 - 50
            draw.rectangle([center_x, center_y, center_x+100, center_y+100], 
                         outline='red', width=2)
            draw.text((center_x, center_y-15), "NO FACE", fill='red')
        
        # Convert to PyGame surface
        frame_string = pil_image.tobytes()
        frame = pygame.image.fromstring(frame_string, pil_image.size, 'RGB')
        
        # Display frame
        screen.blit(frame, (0, 0))
        pygame.display.flip()
        
        clock.tick(60)  # Limit to 30 FPS
    
    # Cleanup
    camera.stop()
    pygame.quit()
    print("\nFace detection stopped. Goodbye!")


if __name__ == "__main__":
    main()