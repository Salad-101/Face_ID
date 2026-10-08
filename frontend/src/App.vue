<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const pages = [
  { id: 'videoPage', label: 'Live Feed', icon: 'fa-video' },
  { id: 'detectedPage', label: 'Known Faces', icon: 'fa-user-check' },
  { id: 'registerPage', label: 'Register New', icon: 'fa-user-plus' },
  { id: 'statsPage', label: 'Statistics', icon: 'fa-chart-bar' },
]

const state = reactive({
  detecting: false,
  fps: 0,
  faceCount: 0,
  knownFaces: [],
  unknownFacesSnapshot: [],
  recentDetections: [],
  page: 'videoPage',
  fpsInterval: null,
  updateInterval: null,
  knownFacesInterval: null,
  frameCount: 0,
  startTime: Date.now(),
  operationInProgress: false,
  cameraAvailable: false,
  formValues: {},
})

const ui = reactive({
  loading: false,
  loadingMessage: 'Processing...',
  toast: null,
})

const videoFeed = ref(null)
const searchFaces = ref('')
const toastTimer = ref(null)

const filteredFaces = computed(() => {
  const term = searchFaces.value.toLowerCase().trim()
  if (!term) return state.knownFaces

  return state.knownFaces.filter(face =>
    face.name.toLowerCase().includes(term) ||
    (face.extra_data &&
      JSON.stringify(face.extra_data).toLowerCase().includes(term))
  )
})

const uptime = computed(() =>
  Math.floor((Date.now() - state.startTime) / (1000 * 60 * 60))
)

const recognitionRate = ref(0)
const dbSize = computed(() => `${state.knownFaces.length * 50} KB`)

function showToast(message, type = 'info', duration = 5000) {
  ui.toast = { message, type }
  clearTimeout(toastTimer.value)
  toastTimer.value = setTimeout(() => {
    ui.toast = null
  }, duration)
}

function addActivity(message) {
  // Kept as a simple client-side activity log.
  // If persistence is needed, this can be backed by a Flask endpoint.
  activityLog.value.unshift({
    message,
    time: new Date().toLocaleTimeString(),
  })
  activityLog.value = activityLog.value.slice(0, 10)
}

const activityLog = ref([
  {
    message: 'System initialized and ready',
    time: 'Just now',
  },
])

function switchToPage(pageId) {
  state.page = pageId
  addActivity(`Switched to ${pageId.replace('Page', '')} page`)

  if (pageId === 'detectedPage') loadKnownFaces()
  if (pageId === 'registerPage') loadUnknownFacesSnapshot()
  if (pageId === 'statsPage') loadStatistics()
}

async function toggleDetection() {
  if (state.operationInProgress) return

  state.operationInProgress = true
  const action = state.detecting ? 'stop' : 'start'

  try {
    const response = await fetch('/toggle_detection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    })

    const data = await response.json()

    if (!data.success) {
      showToast(data.message || 'Failed to toggle detection', 'error')
      return
    }

    state.detecting = !state.detecting

    if (state.detecting) {
      state.startTime = Date.now()
      state.frameCount = 0

      clearIntervals()

      state.fpsInterval = setInterval(calculateFPS, 1000)
      state.updateInterval = setInterval(updateDetectionInfo, 2000)

      if (videoFeed.value) {
        videoFeed.value.src = `/video_feed?${Date.now()}`
      }

      showToast(data.message || 'Face detection started', 'success')
      addActivity('Face detection started')

      if (state.page === 'registerPage') {
        setTimeout(loadUnknownFacesSnapshot, 1000)
      }
    } else {
      clearDetectionIntervals()
      state.fps = 0
      state.faceCount = 0

      showToast(data.message || 'Face detection stopped', 'info')
      addActivity('Face detection stopped')
    }
  } catch (error) {
    console.error(error)
    showToast('Network error. Please check connection.', 'error')
  } finally {
    state.operationInProgress = false
  }
}

function clearDetectionIntervals() {
  if (state.fpsInterval) {
    clearInterval(state.fpsInterval)
    state.fpsInterval = null
  }
  if (state.updateInterval) {
    clearInterval(state.updateInterval)
    state.updateInterval = null
  }
}

function clearIntervals() {
  clearDetectionIntervals()
}

function calculateFPS() {
  const elapsed = (Date.now() - state.startTime) / 1000
  state.fps = elapsed > 0 ? Math.round(state.frameCount / elapsed) : 0
  state.startTime = Date.now()
  state.frameCount = 0
}

async function updateDetectionInfo() {
  try {
    const response = await fetch('/faces_count')
    const data = await response.json()

    state.faceCount = data.faces || 0
    state.frameCount++

    await updateRecentDetections()
  } catch (error) {
    console.error('Error updating detection info:', error)
  }
}

async function loadKnownFaces() {
  try {
    const response = await fetch('/known_faces_list')
    state.knownFaces = await response.json()
  } catch (error) {
    console.error(error)
    showToast('Failed to load faces', 'error')
  }
}

async function loadUnknownFacesSnapshot() {
  try {
    const response = await fetch('/static_unknown_faces')
    state.unknownFacesSnapshot = await response.json()
  } catch (error) {
    console.error(error)
    state.unknownFacesSnapshot = []
    showToast('Failed to load unknown faces', 'error')
  }
}

function formKey(index) {
  return `face_${index}`
}

function storeFormValue(index, field, value) {
  if (!state.formValues[formKey(index)]) {
    state.formValues[formKey(index)] = {}
  }

  state.formValues[formKey(index)][field] = value
}

function getFormValue(index, field) {
  return state.formValues[formKey(index)]?.[field] || ''
}

async function refreshThisFace(snapshotIndex) {
  try {
    const response = await fetch('/update_unknown_snapshot', {
      method: 'POST',
    })

    const data = await response.json()

    if (!data.success) {
      showToast('Failed to refresh face', 'error')
      return
    }

    if (snapshotIndex < data.snapshot.length) {
      state.unknownFacesSnapshot[snapshotIndex] = data.snapshot[snapshotIndex]
      showToast('Face refreshed', 'success')
    }
  } catch (error) {
    console.error(error)
    showToast('Failed to refresh face', 'error')
  }
}

async function registerFace(face, snapshotIndex) {
  const values = state.formValues[formKey(snapshotIndex)] || {}

  if (!values.name?.trim()) {
    showToast('Name is required', 'warning')
    return
  }

  const formData = new FormData()
  formData.append('index', face.index)
  formData.append('name', values.name.trim())
  formData.append('dob', values.dob || '')
  formData.append('nid', values.nid?.trim() || '')

  ui.loading = true
  ui.loadingMessage = 'Registering face...'

  try {
    const response = await fetch('/register_face', {
      method: 'POST',
      body: formData,
    })

    const data = await response.json()

    if (data.success) {
      showToast(data.message, 'success')
      addActivity(`Registered new face: ${values.name.trim()}`)

      delete state.formValues[formKey(snapshotIndex)]

      await loadUnknownFacesSnapshot()
      await loadKnownFaces()
      await loadStatistics()
    } else {
      showToast(data.message || 'Registration failed', 'error')
    }
  } catch (error) {
    console.error(error)
    showToast('Network error. Please try again.', 'error')
  } finally {
    ui.loading = false
  }
}

async function updateRecentDetections() {
  try {
    const response = await fetch('/detected_faces')
    const faces = await response.json()
    state.recentDetections = faces.slice(0, 5)
  } catch (error) {
    console.error(error)
  }
}

async function loadStatistics() {
  try {
    if (!state.knownFaces.length) {
      await loadKnownFaces()
    }

    const response = await fetch('/detected_faces')
    const detectedFaces = await response.json()

    const knownDetected = detectedFaces.filter(
      face => face.name !== 'Unknown'
    ).length

    recognitionRate.value =
      detectedFaces.length > 0
        ? Math.round((knownDetected / detectedFaces.length) * 100)
        : 0
  } catch (error) {
    console.error(error)
  }
}

async function deleteFace(name) {
  const confirmed = window.confirm(`Remove ${name} from the database?`)
  if (!confirmed) return

  try {
    const response = await fetch('/delete_face', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })

    const data = await response.json()

    if (data.success) {
      showToast(data.message || 'Face removed', 'success')
      await loadKnownFaces()
      await loadStatistics()
    } else {
      showToast(data.message || 'Failed to remove face', 'error')
    }
  } catch (error) {
    console.error(error)
    showToast('Network error while removing face', 'error')
  }
}

async function initializeVideoFeed() {
  try {
    const response = await fetch('/camera_status')
    const data = await response.json()

    state.cameraAvailable = data.available

    if (!state.cameraAvailable) {
      showToast(
        'Camera not detected. Please connect a webcam and refresh the page.',
        'warning'
      )
      return
    }

    if (videoFeed.value) {
      videoFeed.value.src = `/video_feed?${Date.now()}`
    }
  } catch (error) {
    console.error(error)
    showToast('Error checking camera status', 'error')
  }
}

function handleVideoError() {
  showToast('Video feed error. Trying to reconnect...', 'warning')
}

async function testCamera() {
  ui.loading = true
  ui.loadingMessage = 'Testing camera...'

  try {
    const response = await fetch('/test_camera')
    const data = await response.json()

    if (data.success) {
      showToast('Camera is working!', 'success')
    } else {
      showToast(`Camera test failed: ${data.message}`, 'warning')
    }
  } catch (error) {
    showToast(`Camera test error: ${error.message}`, 'error')
  } finally {
    ui.loading = false
  }
}

function handleKeydown(event) {
  if (
    event.code === 'Space' &&
    !['INPUT', 'TEXTAREA', 'BUTTON'].includes(event.target.tagName)
  ) {
    event.preventDefault()
    toggleDetection()
  }
}

onMounted(async () => {
  await initializeVideoFeed()
  await loadKnownFaces()
  await loadStatistics()

  state.knownFacesInterval = setInterval(() => {
    if (state.page === 'detectedPage') loadKnownFaces()
  }, 30000)

  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  clearDetectionIntervals()

  if (state.knownFacesInterval) {
    clearInterval(state.knownFacesInterval)
  }

  clearTimeout(toastTimer.value)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="min-h-screen bg-dark-bg text-white">
    <!-- Sidebar -->
    <nav
      class="fixed inset-x-0 bottom-0 z-50 flex h-20 border-t border-border bg-card-bg
             md:inset-y-0 md:right-auto md:h-screen md:w-20 md:flex-col md:border-r md:border-t-0
             lg:w-[250px]"
    >
      <div
        class="hidden h-20 items-center gap-3 border-b border-border px-6 text-2xl font-bold text-primary
               lg:flex"
      >
        <i class="fas fa-robot text-[28px]"></i>
        <span>FaceRec</span>
      </div>

      <div class="flex flex-1 items-center justify-around md:flex-col md:justify-start md:gap-2 md:py-5">
        <button
          v-for="page in pages"
          :key="page.id"
          @click="switchToPage(page.id)"
          :title="page.label"
          class="group flex h-full flex-1 items-center justify-center gap-4 border-t-4 border-transparent
                 px-4 text-text-secondary transition hover:bg-primary/10 hover:text-white
                 md:h-auto md:flex-none md:w-full md:border-l-4 md:border-t-0 md:py-4
                 lg:justify-start"
          :class="state.page === page.id
            ? 'border-primary bg-primary/15 text-primary'
            : ''"
        >
          <i :class="['fas', page.icon, 'w-6 text-center text-xl']"></i>
          <span class="hidden text-sm font-medium lg:inline">{{ page.label }}</span>
        </button>
      </div>

      <div class="hidden border-t border-border p-5 md:block">
        <div class="flex items-center gap-3 text-sm text-text-secondary">
          <span
            class="h-2.5 w-2.5 rounded-full"
            :class="state.detecting ? 'status-pulse bg-success' : 'bg-danger'"
          ></span>
          <span class="hidden lg:inline">System Status</span>
        </div>
      </div>
    </nav>

    <!-- Main -->
    <main class="pb-24 md:ml-20 md:pb-6 lg:ml-[250px]">
      <div class="p-4 md:p-6">
        <!-- Live Feed -->
        <section v-if="state.page === 'videoPage'" class="page-enter">
          <header class="mb-8">
            <h1 class="flex items-center gap-4 text-2xl font-bold md:text-[32px]">
              <i class="fas fa-video text-primary"></i>
              Live Face Detection
            </h1>
            <p class="mt-2 text-text-secondary">
              Real-time face detection and recognition from webcam feed
            </p>
          </header>

          <div class="mb-8 grid gap-6 xl:grid-cols-[2fr_1fr]">
            <div class="rounded-xl border border-border bg-card-bg p-6">
              <div
                class="relative mb-6 aspect-[4/3] overflow-hidden rounded-lg bg-black"
              >
                <img
                  ref="videoFeed"
                  src=""
                  alt="Camera Feed"
                  class="h-full w-full object-cover"
                  @error="handleVideoError"
                />

                <div
                  class="absolute inset-0 flex items-center justify-center bg-black/70 transition-opacity"
                  :class="state.detecting ? 'pointer-events-none opacity-0' : 'opacity-100'"
                >
                  <div class="flex items-center gap-3 rounded-lg bg-black/80 px-6 py-4 text-lg">
                    <i class="fas fa-video-slash"></i>
                    Detection Stopped
                  </div>
                </div>
              </div>

              <div class="flex flex-col gap-6">
                <button
                  class="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-8 py-4
                         text-lg font-semibold transition hover:-translate-y-0.5 hover:bg-primary-dark
                         disabled:cursor-not-allowed disabled:opacity-60"
                  :disabled="!state.cameraAvailable || state.operationInProgress"
                  @click="toggleDetection"
                >
                  <i
                    class="fas"
                    :class="state.operationInProgress
                      ? 'fa-spinner fa-spin'
                      : state.detecting ? 'fa-stop' : 'fa-play'"
                  ></i>
                  {{
                    state.operationInProgress
                      ? state.detecting ? 'Stopping...' : 'Starting...'
                      : state.detecting ? 'Stop Detection' : 'Start Detection'
                  }}
                </button>

                <div class="grid gap-4 sm:grid-cols-2">
                  <div class="flex items-center gap-4 rounded-lg border border-border bg-primary/10 p-5">
                    <i class="fas fa-users text-[28px] text-primary"></i>
                    <div>
                      <span class="block text-sm text-text-secondary">Faces Detected</span>
                      <span class="text-[32px] font-bold">{{ state.faceCount }}</span>
                    </div>
                  </div>

                  <div class="flex items-center gap-4 rounded-lg border border-border bg-primary/10 p-5">
                    <i class="fas fa-tachometer-alt text-[28px] text-primary"></i>
                    <div>
                      <span class="block text-sm text-text-secondary">FPS</span>
                      <span class="text-[32px] font-bold">{{ state.fps }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-xl border border-border bg-card-bg p-6">
              <h3 class="mb-5 flex items-center gap-3 font-semibold">
                <i class="fas fa-history text-primary"></i>
                Recent Detections
              </h3>

              <div class="flex flex-col gap-3">
                <div
                  v-if="!state.recentDetections.length"
                  class="py-12 text-center text-text-secondary"
                >
                  <i class="fas fa-user-clock mb-5 text-5xl text-text-muted/50"></i>
                  <p>No recent detections</p>
                </div>

                <div
                  v-for="face in state.recentDetections"
                  :key="`${face.name}-${face.image}`"
                  class="flex items-center gap-4 rounded-lg bg-white/5 p-4"
                >
                  <img
                    :src="`data:image/jpeg;base64,${face.image}`"
                    :alt="face.name"
                    class="h-12 w-12 rounded-full border-2 border-primary object-cover"
                  />
                  <div>
                    <div class="font-semibold">{{ face.name }}</div>
                    <div class="text-xs text-text-muted">
                      {{ new Date().toLocaleTimeString() }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Known Faces -->
        <section v-else-if="state.page === 'detectedPage'" class="page-enter">
          <header class="mb-8">
            <h1 class="flex items-center gap-4 text-2xl font-bold md:text-[32px]">
              <i class="fas fa-user-check text-primary"></i>
              Known Faces Database
            </h1>
            <p class="mt-2 text-text-secondary">All registered faces in the system</p>
          </header>

          <div class="mb-6 flex flex-wrap items-center gap-4">
            <button
              @click="loadKnownFaces"
              class="inline-flex items-center gap-2 rounded-lg border border-border bg-card-hover
                     px-6 py-3 font-semibold transition hover:-translate-y-0.5 hover:bg-white/10"
            >
              <i class="fas fa-sync-alt"></i>
              Refresh List
            </button>

            <div class="relative w-full max-w-xs">
              <i class="fas fa-search absolute left-4 top-1/2 -translate-y-1/2 text-text-muted"></i>
              <input
                v-model="searchFaces"
                type="text"
                placeholder="Search faces..."
                class="w-full rounded-lg border border-border bg-card-hover py-3 pl-12 pr-4
                       text-white outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </div>

            <span class="rounded-lg bg-card-hover px-4 py-2 text-sm text-text-secondary">
              {{ filteredFaces.length }} face{{ filteredFaces.length === 1 ? '' : 's' }}
            </span>
          </div>

          <div
            v-if="!state.knownFaces.length"
            class="rounded-xl border border-border bg-card-bg py-16 text-center"
          >
            <i class="fas fa-user-slash mb-6 text-6xl text-text-muted/50"></i>
            <h3 class="mb-3 text-2xl font-semibold">No Faces Registered</h3>
            <p class="mb-6 text-text-secondary">
              Go to the "Register New" tab to add faces to the database.
            </p>
            <button
              @click="switchToPage('registerPage')"
              class="rounded-lg bg-primary px-6 py-3 font-semibold"
            >
              <i class="fas fa-user-plus mr-2"></i>
              Register First Face
            </button>
          </div>

          <div v-else-if="!filteredFaces.length" class="py-16 text-center text-text-secondary">
            <i class="fas fa-search mb-5 text-5xl text-text-muted/50"></i>
            <h3 class="mb-2 text-xl font-semibold text-white">No Faces Found</h3>
            <p>No faces match your search criteria.</p>
          </div>

          <div v-else class="grid gap-6 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
            <article
              v-for="face in filteredFaces"
              :key="face.name"
              class="overflow-hidden rounded-xl border border-border bg-card-bg transition
                     hover:-translate-y-1 hover:border-primary hover:shadow-2xl"
            >
              <img
                :src="`data:image/jpeg;base64,${face.image}`"
                :alt="face.name"
                class="h-52 w-full object-cover"
              />

              <div class="p-5">
                <h3 class="mb-3 text-xl font-bold">{{ face.name }}</h3>

                <div v-if="face.extra_data" class="mb-4 flex flex-col gap-2 text-sm text-text-secondary">
                  <div v-if="face.extra_data.dob" class="flex gap-2">
                    <i class="fas fa-birthday-cake w-4 text-primary"></i>
                    <span>DOB: {{ face.extra_data.dob }}</span>
                  </div>

                  <div v-if="face.extra_data.national_id" class="flex gap-2">
                    <i class="fas fa-id-card w-4 text-primary"></i>
                    <span>ID: {{ face.extra_data.national_id }}</span>
                  </div>

                  <div v-if="face.extra_data.registered_at" class="flex gap-2">
                    <i class="fas fa-calendar-alt w-4 text-primary"></i>
                    <span>
                      Registered:
                      {{ new Date(face.extra_data.registered_at).toLocaleDateString() }}
                    </span>
                  </div>
                </div>

                <button
                  @click="deleteFace(face.name)"
                  class="rounded-lg border border-border bg-card-hover px-4 py-2 text-sm font-semibold
                         transition hover:bg-white/10"
                >
                  <i class="fas fa-trash mr-2"></i>
                  Remove
                </button>
              </div>
            </article>
          </div>
        </section>

        <!-- Register -->
        <section v-else-if="state.page === 'registerPage'" class="page-enter">
          <header class="mb-8">
            <h1 class="flex items-center gap-4 text-2xl font-bold md:text-[32px]">
              <i class="fas fa-user-plus text-primary"></i>
              Register New Faces
            </h1>
            <p class="mt-2 text-text-secondary">
              Register unknown faces detected in the live feed
            </p>
          </header>

          <div class="mb-6 flex flex-wrap items-center gap-4">
            <button
              @click="loadUnknownFacesSnapshot"
              class="inline-flex items-center gap-2 rounded-lg border border-border bg-card-hover
                     px-6 py-3 font-semibold transition hover:-translate-y-0.5 hover:bg-white/10"
            >
              <i class="fas fa-sync-alt"></i>
              Check for New Faces
            </button>

            <div class="flex items-center gap-2 rounded-lg bg-info/10 px-4 py-3 text-sm text-info">
              <i class="fas fa-info-circle"></i>
              Start detection in Live Feed tab to see unknown faces here
            </div>
          </div>

          <div
            v-if="!state.unknownFacesSnapshot.length"
            class="rounded-xl border border-border bg-card-bg py-12 text-center"
          >
            <i class="fas fa-user-friends mb-6 text-6xl text-text-muted/50"></i>
            <h3 class="mb-3 text-2xl font-semibold">No Unknown Faces Detected</h3>
            <p class="mx-auto mb-6 max-w-md text-text-secondary">
              {{
                state.detecting
                  ? 'Make sure faces are visible in the camera.'
                  : 'Start face detection in the Live Feed tab to see unknown faces here.'
              }}
            </p>
            <button
              v-if="!state.detecting"
              @click="switchToPage('videoPage')"
              class="rounded-lg bg-primary px-6 py-3 font-semibold"
            >
              <i class="fas fa-video mr-2"></i>
              Go to Live Feed
            </button>
            <button
              v-else
              @click="loadUnknownFacesSnapshot"
              class="rounded-lg bg-primary px-6 py-3 font-semibold"
            >
              <i class="fas fa-sync-alt mr-2"></i>
              Refresh List
            </button>
          </div>

          <div v-else class="grid gap-6 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
            <article
              v-for="(face, index) in state.unknownFacesSnapshot"
              :key="`${face.index}-${index}`"
              class="overflow-hidden rounded-xl border border-border bg-card-bg"
            >
              <div class="relative">
                <img
                  :src="`data:image/jpeg;base64,${face.image}`"
                  alt="Unknown Face"
                  class="h-52 w-full object-cover"
                />
                <span class="absolute left-3 top-3 flex h-6 w-6 items-center justify-center rounded-full
                             bg-primary text-xs font-bold">
                  {{ index + 1 }}
                </span>
              </div>

              <div class="p-5">
                <h3 class="mb-1 text-xl font-bold">Unknown Face #{{ face.index + 1 }}</h3>
                <p class="mb-4 text-sm text-text-muted">
                  Snapshot taken at {{ new Date().toLocaleTimeString() }}
                </p>

                <form @submit.prevent="registerFace(face, index)" class="flex flex-col gap-3">
                  <label class="text-sm text-text-secondary">
                    <span class="mb-1 block font-medium">
                      <i class="fas fa-user mr-1"></i> Name *
                    </span>
                    <input
                      :value="getFormValue(index, 'name')"
                      @input="storeFormValue(index, 'name', $event.target.value)"
                      type="text"
                      placeholder="Enter full name"
                      required
                      class="w-full rounded-lg border border-border bg-card-hover px-4 py-3 text-white
                             outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                  </label>

                  <label class="text-sm text-text-secondary">
                    <span class="mb-1 block font-medium">
                      <i class="fas fa-birthday-cake mr-1"></i> Date of Birth
                    </span>
                    <input
                      :value="getFormValue(index, 'dob')"
                      @input="storeFormValue(index, 'dob', $event.target.value)"
                      type="date"
                      class="w-full rounded-lg border border-border bg-card-hover px-4 py-3 text-white
                             outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                  </label>

                  <label class="text-sm text-text-secondary">
                    <span class="mb-1 block font-medium">
                      <i class="fas fa-id-card mr-1"></i> National ID
                    </span>
                    <input
                      :value="getFormValue(index, 'nid')"
                      @input="storeFormValue(index, 'nid', $event.target.value)"
                      type="text"
                      placeholder="Optional"
                      class="w-full rounded-lg border border-border bg-card-hover px-4 py-3 text-white
                             outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                  </label>

                  <div class="mt-2 grid grid-cols-2 gap-2">
                    <button
                      type="submit"
                      class="rounded-lg bg-primary px-3 py-2.5 text-sm font-semibold transition
                             hover:bg-primary-dark"
                    >
                      <i class="fas fa-save mr-1"></i>
                      Register Face
                    </button>

                    <button
                      type="button"
                      @click="refreshThisFace(index)"
                      class="rounded-lg border border-border bg-card-hover px-3 py-2.5 text-sm
                             font-semibold hover:bg-white/10"
                    >
                      <i class="fas fa-sync mr-1"></i>
                      Refresh
                    </button>
                  </div>
                </form>
              </div>
            </article>
          </div>

          <div class="mt-8 rounded-xl border border-border bg-card-bg p-6">
            <h3 class="mb-4 flex items-center gap-3 font-semibold">
              <i class="fas fa-lightbulb text-warning"></i>
              Tips for Better Registration
            </h3>

            <ul class="grid gap-3 sm:grid-cols-2">
              <li v-for="tip in [
                'Ensure good lighting on the face',
                'Face should be clearly visible and not obstructed',
                'Use a clear, recent photo for best results',
                'Enter accurate information for better identification'
              ]" :key="tip" class="rounded-lg bg-white/5 px-4 py-3 text-text-secondary">
                <span class="mr-2 font-bold text-success">✓</span>{{ tip }}
              </li>
            </ul>
          </div>
        </section>

        <!-- Statistics -->
        <section v-else-if="state.page === 'statsPage'" class="page-enter">
          <header class="mb-8">
            <h1 class="flex items-center gap-4 text-2xl font-bold md:text-[32px]">
              <i class="fas fa-chart-bar text-primary"></i>
              System Statistics
            </h1>
            <p class="mt-2 text-text-secondary">
              Analytics and system performance metrics
            </p>
          </header>

          <div class="mb-8 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
            <div
              v-for="stat in [
                { icon: 'fa-users', title: 'Total Registered', value: state.knownFaces.length, note: 'Faces in database', tone: 'primary' },
                { icon: 'fa-check-circle', title: 'Recognition Rate', value: `${recognitionRate}%`, note: 'Successful identifications', tone: 'success' },
                { icon: 'fa-database', title: 'Database Size', value: dbSize, note: 'Storage used', tone: 'warning' },
                { icon: 'fa-clock', title: 'Uptime', value: `${uptime}h`, note: 'System running time', tone: 'info' }
              ]"
              :key="stat.title"
              class="flex items-center gap-5 rounded-xl border border-border bg-card-bg p-6"
            >
              <div
                class="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl text-[28px]"
                :class="{
                  'bg-primary/20 text-primary': stat.tone === 'primary',
                  'bg-success/20 text-success': stat.tone === 'success',
                  'bg-warning/20 text-warning': stat.tone === 'warning',
                  'bg-info/20 text-info': stat.tone === 'info'
                }"
              >
                <i :class="['fas', stat.icon]"></i>
              </div>
              <div>
                <h3 class="text-sm text-text-secondary">{{ stat.title }}</h3>
                <div class="text-[30px] font-bold">{{ stat.value }}</div>
                <p class="text-sm text-text-muted">{{ stat.note }}</p>
              </div>
            </div>
          </div>

          <div class="rounded-xl border border-border bg-card-bg p-6">
            <h3 class="mb-5 flex items-center gap-3 font-semibold">
              <i class="fas fa-history text-primary"></i>
              Recent Activity
            </h3>

            <div class="flex flex-col gap-3">
              <div
                v-for="(activity, index) in activityLog"
                :key="`${activity.time}-${index}`"
                class="flex items-start gap-4 rounded-lg bg-white/5 p-4"
              >
                <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/20 text-primary">
                  <i class="fas fa-info-circle"></i>
                </div>
                <div>
                  <p>{{ activity.message }}</p>
                  <span class="text-xs text-text-muted">{{ activity.time }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>

    <!-- Toast -->
    <Transition
      enter-active-class="transition duration-300"
      enter-from-class="translate-x-full opacity-0"
      leave-active-class="transition duration-300"
      leave-to-class="translate-x-full opacity-0"
    >
      <div
        v-if="ui.toast"
        class="fixed right-6 top-6 z-[1000] flex min-w-[300px] max-w-[400px] items-center gap-3
               rounded-lg border-l-4 bg-card-bg px-6 py-4 shadow-2xl"
        :class="{
          'border-success': ui.toast.type === 'success',
          'border-danger': ui.toast.type === 'error',
          'border-warning': ui.toast.type === 'warning',
          'border-primary': ui.toast.type === 'info'
        }"
      >
        <i
          class="fas text-xl"
          :class="{
            'fa-check-circle text-success': ui.toast.type === 'success',
            'fa-exclamation-circle text-danger': ui.toast.type === 'error',
            'fa-exclamation-triangle text-warning': ui.toast.type === 'warning',
            'fa-info-circle text-primary': ui.toast.type === 'info'
          }"
        ></i>
        <div class="flex-1 text-sm">{{ ui.toast.message }}</div>
        <button @click="ui.toast = null" class="text-text-muted hover:text-white">
          <i class="fas fa-times"></i>
        </button>
      </div>
    </Transition>

    <!-- Loading Overlay -->
    <div
      v-if="ui.loading"
      class="fixed inset-0 z-[2000] flex items-center justify-center bg-dark-bg/90"
    >
      <div class="text-center">
        <i class="fas fa-spinner fa-spin mb-6 text-5xl text-primary"></i>
        <p>{{ ui.loadingMessage }}</p>
      </div>
    </div>
  </div>
</template>

