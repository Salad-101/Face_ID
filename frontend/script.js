// Global state
let state = {
    detecting: false,
    fps: 0,
    faceCount: 0,
    knownFaces: [],
    unknownFaces: [],
    unknownFacesSnapshot: [],
    recentDetections: [],
    lastUpdate: 0,
    page: 'videoPage',
    updateInterval: null,
    fpsInterval: null,
    frameCount: 0,
    startTime: Date.now(),
    operationInProgress: false,
    cameraAvailable: false,
    formValues: {} // Store form values to prevent loss
};

// DOM Elements
const elements = {
    videoFeed: document.getElementById('videoFeed'),
    toggleBtn: document.getElementById('toggleBtn'),
    faceCount: document.getElementById('faceCount'),
    fpsCounter: document.getElementById('fpsCounter'),
    facesGrid: document.getElementById('facesGrid'),
    unknownFacesGrid: document.getElementById('unknownFacesGrid'),
    recentDetections: document.getElementById('recentDetections'),
    totalKnownFaces: document.getElementById('totalKnownFaces'),
    searchFaces: document.getElementById('searchFaces'),
    refreshKnownBtn: document.getElementById('refreshKnownBtn'),
    refreshUnknownBtn: document.getElementById('refreshUnknownBtn'),
    detectionStatus: document.getElementById('detectionStatus'),
    noFacesState: document.getElementById('noFacesState'),
    statTotalFaces: document.getElementById('statTotalFaces'),
    statRecognitionRate: document.getElementById('statRecognitionRate'),
    statDbSize: document.getElementById('statDbSize'),
    statUptime: document.getElementById('statUptime'),
    activityLog: document.getElementById('activityLog'),
    loadingOverlay: document.getElementById('loadingOverlay')
};

// Toast System
class Toast {
    static show(message, type = 'info', duration = 5000) {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        
        toast.innerHTML = `
            <i class="toast-icon ${icons[type] || icons.info}"></i>
            <div class="toast-content">
                <div class="toast-title">${type.charAt(0).toUpperCase() + type.slice(1)}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        container.appendChild(toast);
        
        // Auto remove
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, duration);
        
        // Close button
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        });
    }
}

// Loading Overlay
function showLoading(message = 'Processing...') {
    elements.loadingOverlay.style.display = 'flex';
    elements.loadingOverlay.querySelector('p').textContent = message;
}

function hideLoading() {
    elements.loadingOverlay.style.display = 'none';
}

// Navigation
function switchToPage(pageId) {
    // Update active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-page="${pageId}"]`).classList.add('active');
    
    // Update pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(pageId).classList.add('active');
    
    // Load page data
    state.page = pageId;
    loadPageData();
    
    // Add to activity log
    addActivity(`Switched to ${pageId.replace('Page', '')} page`);
}

// Initialize navigation
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const pageId = item.dataset.page;
        switchToPage(pageId);
    });
});

// Load page-specific data
function loadPageData() {
    switch(state.page) {
        case 'detectedPage':
            loadKnownFaces();
            break;
        case 'registerPage':
            // Load static snapshot of unknown faces
            loadUnknownFacesSnapshot();
            break;
        case 'statsPage':
            loadStatistics();
            break;
    }
}

// Face Detection Control
async function toggleDetection() {
    if (state.operationInProgress) return;
    
    state.operationInProgress = true;
    updateUI();
    
    try {
        const action = state.detecting ? 'stop' : 'start';
        
        // Update button immediately for better UX
        elements.toggleBtn.innerHTML = action === 'start' 
            ? '<i class="fas fa-spinner fa-spin"></i> Starting...'
            : '<i class="fas fa-spinner fa-spin"></i> Stopping...';
        
        const response = await fetch('/toggle_detection', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action})
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.detecting = !state.detecting;
            
            if (state.detecting) {
                // Start FPS counter
                state.startTime = Date.now();
                state.frameCount = 0;
                
                // Clear any existing intervals
                if (state.fpsInterval) clearInterval(state.fpsInterval);
                if (state.updateInterval) clearInterval(state.updateInterval);
                
                // Start new intervals
                state.fpsInterval = setInterval(calculateFPS, 1000);
                state.updateInterval = setInterval(updateDetectionInfo, 2000); // Reduced frequency
                
                // Update video feed
                elements.videoFeed.src = '/video_feed?' + new Date().getTime();
                
                Toast.show(data.message || 'Face detection started', 'success');
                addActivity('Face detection started');
                
                // Update unknown faces snapshot if on register page
                if (state.page === 'registerPage') {
                    setTimeout(loadUnknownFacesSnapshot, 1000); // Wait a bit for detection to start
                }
            } else {
                // Clear intervals
                if (state.fpsInterval) {
                    clearInterval(state.fpsInterval);
                    state.fpsInterval = null;
                }
                if (state.updateInterval) {
                    clearInterval(state.updateInterval);
                    state.updateInterval = null;
                }
                
                // Reset FPS display
                elements.fpsCounter.textContent = '0';
                state.faceCount = 0;
                updateUI();
                
                Toast.show(data.message || 'Face detection stopped', 'info');
                addActivity('Face detection stopped');
            }
        } else {
            Toast.show(data.message || 'Failed to toggle detection', 'error');
        }
    } catch (error) {
        console.error('Error toggling detection:', error);
        Toast.show('Network error. Please check connection.', 'error');
    } finally {
        state.operationInProgress = false;
        updateUI();
    }
}

// FPS Calculation
function calculateFPS() {
    const now = Date.now();
    const elapsed = (now - state.startTime) / 1000;
    state.fps = Math.round(state.frameCount / elapsed);
    state.startTime = now;
    state.frameCount = 0;
    
    elements.fpsCounter.textContent = state.fps;
}

// Update detection info (does NOT update unknown faces grid)
async function updateDetectionInfo() {
    try {
        // Get face count
        const countResponse = await fetch('/faces_count');
        const countData = await countResponse.json();
        state.faceCount = countData.faces || 0;
        
        // Update FPS counter
        state.frameCount++;
        
        // Update UI
        elements.faceCount.textContent = state.faceCount;
        
        // Update recent detections
        updateRecentDetections();
        
    } catch (error) {
        console.error('Error updating detection info:', error);
    }
}

// Load known faces
async function loadKnownFaces() {
    try {
        elements.facesGrid.innerHTML = `
            <div class="loading-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading faces...</p>
            </div>
        `;
        
        const response = await fetch('/known_faces_list');
        state.knownFaces = await response.json();
        
        renderKnownFaces();
        
        // Update statistics
        elements.totalKnownFaces.textContent = `${state.knownFaces.length} face${state.knownFaces.length !== 1 ? 's' : ''}`;
        
        // Show/hide empty state
        if (state.knownFaces.length === 0) {
            elements.noFacesState.style.display = 'block';
            elements.facesGrid.style.display = 'none';
        } else {
            elements.noFacesState.style.display = 'none';
            elements.facesGrid.style.display = 'grid';
        }
        
    } catch (error) {
        console.error('Error loading known faces:', error);
        elements.facesGrid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Error Loading Faces</h3>
                <p>Failed to load faces from server. Please try again.</p>
                <button class="btn btn-secondary" onclick="loadKnownFaces()">
                    <i class="fas fa-sync-alt"></i> Retry
                </button>
            </div>
        `;
        Toast.show('Failed to load faces', 'error');
    }
}

// Render known faces
function renderKnownFaces() {
    const searchTerm = elements.searchFaces ? elements.searchFaces.value.toLowerCase() : '';
    
    const filteredFaces = state.knownFaces.filter(face => 
        face.name.toLowerCase().includes(searchTerm) ||
        (face.extra_data && JSON.stringify(face.extra_data).toLowerCase().includes(searchTerm))
    );
    
    elements.facesGrid.innerHTML = '';
    
    filteredFaces.forEach(face => {
        const card = createFaceCard(face);
        elements.facesGrid.appendChild(card);
    });
    
    if (filteredFaces.length === 0) {
        elements.facesGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <i class="fas fa-search"></i>
                <h3>No Faces Found</h3>
                <p>No faces match your search criteria.</p>
            </div>
        `;
    }
}

// Create face card
function createFaceCard(face) {
    const card = document.createElement('div');
    card.className = 'face-card';
    
    const extraHtml = face.extra_data ? `
        <div class="face-meta">
            ${face.extra_data.dob ? `
                <div class="face-meta-item">
                    <i class="fas fa-birthday-cake"></i>
                    <span>DOB: ${face.extra_data.dob}</span>
                </div>
            ` : ''}
            ${face.extra_data.national_id ? `
                <div class="face-meta-item">
                    <i class="fas fa-id-card"></i>
                    <span>ID: ${face.extra_data.national_id}</span>
                </div>
            ` : ''}
            ${face.extra_data.registered_at ? `
                <div class="face-meta-item">
                    <i class="fas fa-calendar-alt"></i>
                    <span>Registered: ${new Date(face.extra_data.registered_at).toLocaleDateString()}</span>
                </div>
            ` : ''}
        </div>
    ` : '';
    
    card.innerHTML = `
        <img src="data:image/jpeg;base64,${face.image}" alt="${face.name}" class="face-image">
        <div class="face-content">
            <h3 class="face-name">${face.name}</h3>
            ${extraHtml}
            <div class="face-actions">
                <button class="btn btn-secondary btn-sm" onclick="deleteFace('${face.name}')">
                    <i class="fas fa-trash"></i> Remove
                </button>
            </div>
        </div>
    `;
    
    return card;
}

// Load static snapshot of unknown faces (does NOT auto-refresh)
async function loadUnknownFacesSnapshot() {
    try {
        elements.unknownFacesGrid.innerHTML = `
            <div class="loading-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading unknown faces...</p>
            </div>
        `;
        
        // Get static snapshot (won't change until manually refreshed)
        const response = await fetch('/static_unknown_faces');
        const snapshot = await response.json();
        
        // Store the snapshot
        state.unknownFacesSnapshot = snapshot;
        
        // Render the snapshot (forms will maintain their state)
        renderUnknownFacesFromSnapshot();
        
        if (snapshot.length === 0) {
            showNoUnknownFacesMessage();
        }
        
    } catch (error) {
        console.error('Error loading unknown faces:', error);
        showNoUnknownFacesMessage();
        Toast.show('Failed to load unknown faces', 'error');
    }
}

// Render unknown faces from static snapshot
function renderUnknownFacesFromSnapshot() {
    elements.unknownFacesGrid.innerHTML = '';
    
    if (state.unknownFacesSnapshot.length === 0) {
        showNoUnknownFacesMessage();
        return;
    }
    
    state.unknownFacesSnapshot.forEach((face, index) => {
        const card = createUnknownFaceCard(face, index);
        elements.unknownFacesGrid.appendChild(card);
    });
}

// Create unknown face card with preserved form values
function createUnknownFaceCard(face, snapshotIndex) {
    const card = document.createElement('div');
    card.className = 'face-card';
    card.dataset.snapshotIndex = snapshotIndex;
    
    // Get stored form values for this card
    const formKey = `face_${snapshotIndex}`;
    const storedValues = state.formValues[formKey] || {};
    
    card.innerHTML = `
        <img src="data:image/jpeg;base64,${face.image}" alt="Unknown Face" class="face-image">
        <div class="face-content">
            <h3 class="face-name">Unknown Face #${face.index + 1}</h3>
            <p class="face-meta">Snapshot taken at ${new Date().toLocaleTimeString()}</p>
            
            <form class="registration-form" onsubmit="registerFace(event, ${face.index})">
                <div class="form-group">
                    <label class="form-label" for="name-${snapshotIndex}">
                        <i class="fas fa-user"></i> Name *
                    </label>
                    <input type="text" 
                           id="name-${snapshotIndex}" 
                           class="form-input" 
                           placeholder="Enter full name" 
                           value="${storedValues.name || ''}"
                           required
                           oninput="storeFormValue(${snapshotIndex}, 'name', this.value)">
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="dob-${snapshotIndex}">
                        <i class="fas fa-birthday-cake"></i> Date of Birth
                    </label>
                    <input type="date" 
                           id="dob-${snapshotIndex}" 
                           class="form-input"
                           value="${storedValues.dob || ''}"
                           oninput="storeFormValue(${snapshotIndex}, 'dob', this.value)">
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="nid-${snapshotIndex}">
                        <i class="fas fa-id-card"></i> National ID
                    </label>
                    <input type="text" 
                           id="nid-${snapshotIndex}" 
                           class="form-input" 
                           placeholder="Optional"
                           value="${storedValues.nid || ''}"
                           oninput="storeFormValue(${snapshotIndex}, 'nid', this.value)">
                </div>
                
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save"></i> Register Face
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="refreshThisFace(${snapshotIndex})">
                        <i class="fas fa-sync"></i> Refresh
                    </button>
                </div>
            </form>
        </div>
    `;
    
    return card;
}

// Store form values to prevent loss
function storeFormValue(snapshotIndex, field, value) {
    const formKey = `face_${snapshotIndex}`;
    if (!state.formValues[formKey]) {
        state.formValues[formKey] = {};
    }
    state.formValues[formKey][field] = value;
}

// Refresh a specific face
async function refreshThisFace(snapshotIndex) {
    const card = document.querySelector(`.face-card[data-snapshot-index="${snapshotIndex}"]`);
    if (card) {
        card.querySelector('.form-actions button').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
        card.querySelector('.form-actions button').disabled = true;
        
        // Update the snapshot
        const response = await fetch('/update_unknown_snapshot', {
            method: 'POST'
        });
        
        const data = await response.json();
        if (data.success) {
            // Update this specific card in the snapshot
            if (snapshotIndex < data.snapshot.length) {
                state.unknownFacesSnapshot[snapshotIndex] = data.snapshot[snapshotIndex];
                // Re-render just this card
                const newCard = createUnknownFaceCard(data.snapshot[snapshotIndex], snapshotIndex);
                card.parentNode.replaceChild(newCard, card);
                Toast.show('Face refreshed', 'success');
            }
        } else {
            Toast.show('Failed to refresh face', 'error');
            card.querySelector('.form-actions button').innerHTML = '<i class="fas fa-sync"></i> Refresh';
            card.querySelector('.form-actions button').disabled = false;
        }
    }
}

// Show no unknown faces message
function showNoUnknownFacesMessage() {
    elements.unknownFacesGrid.innerHTML = `
        <div class="empty-state">
            <i class="fas fa-user-friends"></i>
            <h3>No Unknown Faces Detected</h3>
            <p>${state.detecting 
                ? 'Make sure faces are visible in the camera.' 
                : 'Start face detection in the Live Feed tab to see unknown faces here.'}</p>
            ${!state.detecting ? `
                <button class="btn btn-primary" onclick="switchToPage('videoPage')">
                    <i class="fas fa-video"></i> Go to Live Feed
                </button>
            ` : `
                <button class="btn btn-primary" onclick="loadUnknownFacesSnapshot()">
                    <i class="fas fa-sync-alt"></i> Refresh List
                </button>
            `}
        </div>
    `;
}

// Register face (with preserved form values)
async function registerFace(event, faceIndex) {
    event.preventDefault();
    
    const form = event.target;
    const snapshotIndex = form.closest('.face-card').dataset.snapshotIndex;
    const nameInput = form.querySelector(`#name-${snapshotIndex}`);
    const dobInput = form.querySelector(`#dob-${snapshotIndex}`);
    const nidInput = form.querySelector(`#nid-${snapshotIndex}`);
    
    const formData = new FormData();
    formData.append('index', faceIndex);
    formData.append('name', nameInput.value.trim());
    formData.append('dob', dobInput.value);
    formData.append('nid', nidInput.value.trim());
    
    try {
        showLoading('Registering face...');
        
        const response = await fetch('/register_face', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            Toast.show(data.message, 'success');
            addActivity(`Registered new face: ${nameInput.value.trim()}`);
            
            // Clear stored form values for this card
            delete state.formValues[`face_${snapshotIndex}`];
            
            // Refresh both lists
            loadUnknownFacesSnapshot(); // This will get fresh snapshot without the registered face
            if (state.page === 'detectedPage') {
                setTimeout(loadKnownFaces, 500); // Wait a bit for server to update
            }
            
            // Update statistics
            setTimeout(loadStatistics, 500);
            
        } else {
            Toast.show(data.message || 'Registration failed', 'error');
        }
    } catch (error) {
        console.error('Error registering face:', error);
        Toast.show('Network error. Please try again.', 'error');
    } finally {
        hideLoading();
    }
}

// Load statistics
async function loadStatistics() {
    try {
        // Update total faces
        elements.statTotalFaces.textContent = state.knownFaces.length;
        
        // Update recognition rate
        const detectionResponse = await fetch('/detected_faces');
        const detectedFaces = await detectionResponse.json();
        const knownDetected = detectedFaces.filter(f => f.name !== 'Unknown').length;
        const totalDetected = detectedFaces.length;
        const recognitionRate = totalDetected > 0 ? Math.round((knownDetected / totalDetected) * 100) : 0;
        elements.statRecognitionRate.textContent = `${recognitionRate}%`;
        
        // Update database size (dummy calculation)
        const dbSize = state.knownFaces.length * 50; // 50KB per face
        elements.statDbSize.textContent = `${dbSize} KB`;
        
        // Update uptime
        const uptimeHours = Math.floor((Date.now() - state.startTime) / (1000 * 60 * 60));
        elements.statUptime.textContent = `${uptimeHours}h`;
        
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Update recent detections
async function updateRecentDetections() {
    try {
        const response = await fetch('/detected_faces');
        const detectedFaces = await response.json();
        
        // Update state
        state.recentDetections = detectedFaces.slice(0, 5);
        
        // Update UI
        elements.recentDetections.innerHTML = '';
        
        if (state.recentDetections.length === 0) {
            elements.recentDetections.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-user-clock"></i>
                    <p>No recent detections</p>
                </div>
            `;
            return;
        }
        
        state.recentDetections.forEach(face => {
            const item = document.createElement('div');
            item.className = 'detection-item';
            
            item.innerHTML = `
                <img src="data:image/jpeg;base64,${face.image}" alt="${face.name}">
                <div class="detection-info">
                    <div class="detection-name">${face.name}</div>
                    <div class="detection-time">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            
            elements.recentDetections.appendChild(item);
        });
    } catch (error) {
        console.error('Error updating recent detections:', error);
    }
}

// Add activity log entry
function addActivity(message) {
    const activityItem = document.createElement('div');
    activityItem.className = 'activity-item';
    
    activityItem.innerHTML = `
        <div class="activity-icon">
            <i class="fas fa-info-circle"></i>
        </div>
        <div class="activity-content">
            <p>${message}</p>
            <span class="activity-time">${new Date().toLocaleTimeString()}</span>
        </div>
    `;
    
    elements.activityLog.insertBefore(activityItem, elements.activityLog.firstChild);
    
    // Keep only last 10 activities
    const items = elements.activityLog.querySelectorAll('.activity-item');
    if (items.length > 10) {
        items[items.length - 1].remove();
    }
}

// Update UI based on state
function updateUI() {
    // Update toggle button
    if (state.detecting) {
        elements.toggleBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Detection';
        elements.toggleBtn.disabled = state.operationInProgress;
        elements.detectionStatus.innerHTML = '<i class="fas fa-video"></i> Detection Active';
        elements.detectionStatus.parentElement.style.opacity = '0';
    } else {
        elements.toggleBtn.innerHTML = '<i class="fas fa-play"></i> Start Detection';
        elements.toggleBtn.disabled = state.operationInProgress;
        elements.detectionStatus.innerHTML = '<i class="fas fa-video-slash"></i> Detection Stopped';
        elements.detectionStatus.parentElement.style.opacity = '1';
    }
    
    // Update status indicator
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        statusDot.classList.toggle('stopped', !state.detecting);
        statusDot.classList.toggle('detecting', state.detecting);
    }
    
    // Update face count display
    elements.faceCount.textContent = state.faceCount;
}

// Initialize camera and video feed
async function initializeVideoFeed() {
    try {
        // First check camera status
        const statusResponse = await fetch('/camera_status');
        const statusData = await statusResponse.json();
        
        state.cameraAvailable = statusData.available;
        
        if (!state.cameraAvailable) {
            Toast.show('Camera not detected. Please connect a webcam and refresh the page.', 'warning');
            elements.detectionStatus.innerHTML = '<i class="fas fa-video-slash"></i> No Camera Detected';
            elements.toggleBtn.disabled = true;
            elements.toggleBtn.innerHTML = '<i class="fas fa-video-slash"></i> Camera Unavailable';
            return;
        }
        
        // Set video feed source (blank initially)
        elements.videoFeed.src = '/video_feed?' + new Date().getTime();
        
        // Add error handling for video feed
        elements.videoFeed.onerror = function() {
            console.error('Video feed error');
            Toast.show('Video feed error. Trying to reconnect...', 'warning');
        };
        
        elements.videoFeed.onload = function() {
            console.log('Video feed loaded');
        };
        
        elements.toggleBtn.disabled = false;
        
    } catch (error) {
        console.error('Error initializing video feed:', error);
        Toast.show('Error checking camera status', 'error');
    }
}

// Initialize the application
async function initialize() {
    try {
        console.log('Initializing application...');
        
        // Initialize video feed first
        await initializeVideoFeed();
        
        // Load initial data
        await loadKnownFaces();
        await loadStatistics();
        
        // Add event listeners
        elements.toggleBtn.addEventListener('click', toggleDetection);
        
        if (elements.refreshKnownBtn) {
            elements.refreshKnownBtn.addEventListener('click', loadKnownFaces);
        }
        
        if (elements.refreshUnknownBtn) {
            elements.refreshUnknownBtn.addEventListener('click', loadUnknownFacesSnapshot);
        }
        
        if (elements.searchFaces) {
            elements.searchFaces.addEventListener('input', renderKnownFaces);
        }
        
        // Add keyboard shortcut for toggling detection (Space key)
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !e.target.matches('input, textarea, button')) {
                e.preventDefault();
                toggleDetection();
            }
        });
        
        // Add initial activity
        addActivity('System initialized and ready');
        
        // Auto-refresh known faces every 30 seconds when on that page
        setInterval(() => {
            if (state.page === 'detectedPage') {
                loadKnownFaces();
            }
        }, 30000);
        
        console.log('Application initialized successfully');
        
    } catch (error) {
        console.error('Error during initialization:', error);
        Toast.show('Failed to initialize system. Please refresh the page.', 'error');
    }
}

// Test camera function
async function testCamera() {
    try {
        showLoading('Testing camera...');
        const response = await fetch('/test_camera');
        const data = await response.json();
        
        if (data.success) {
            Toast.show('Camera is working!', 'success');
        } else {
            Toast.show('Camera test failed: ' + data.message, 'warning');
        }
    } catch (error) {
        Toast.show('Camera test error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Make functions available globally
window.switchToPage = switchToPage;
window.registerFace = registerFace;
window.loadUnknownFacesSnapshot = loadUnknownFacesSnapshot;
window.testCamera = testCamera;
window.refreshThisFace = refreshThisFace;
window.storeFormValue = storeFormValue;

// Start initialization when DOM is loaded
document.addEventListener('DOMContentLoaded', initialize);

// Export state for debugging
window.appState = state;