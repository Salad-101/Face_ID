// Sidebar page switching
const sidebarBtns = document.querySelectorAll('.sidebar-btn');
const pages = document.querySelectorAll('.page');

sidebarBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        sidebarBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const pageId = btn.dataset.page;
        pages.forEach(p => p.classList.remove('active'));
        document.getElementById(pageId).classList.add('active');
    });
});

// Detection logic
const toggleBtn = document.getElementById('toggleBtn');
const facesText = document.getElementById('faces');
const videoFeed = document.getElementById('videoFeed');
const statusIndicator = document.getElementById('statusIndicator');
const facesGrid = document.getElementById('facesGrid');
const unknownFacesGrid = document.getElementById('unknownFacesGrid');

let detecting = false;
let updateInterval = null;
let lastTime = Date.now();

async function startDetection() {
    const res = await fetch("/toggle_detection", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action: "start"})
    });
    const data = await res.json();
    if (!data.success) return;

    detecting = true;
    toggleBtn.textContent = "Stop Detection";
    statusIndicator.textContent = "Detecting";
    statusIndicator.classList.remove("stopped");
    statusIndicator.classList.add("detecting");

    videoFeed.src = "/video_feed";

    updateInterval = setInterval(updateFaces, 500);
}

async function stopDetection() {
    const res = await fetch("/toggle_detection", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action: "stop"})
    });
    const data = await res.json();
    if (!data.success) return;

    detecting = false;
    toggleBtn.textContent = "Start Detection";
    statusIndicator.textContent = "Stopped";
    statusIndicator.classList.remove("detecting");
    statusIndicator.classList.add("stopped");

    facesText.textContent = `Found 0 faces | FPS: 0`;
    facesGrid.innerHTML = "";
    unknownFacesGrid.innerHTML = "";
    videoFeed.src = "";
    clearInterval(updateInterval);
}

toggleBtn.addEventListener("click", () => detecting ? stopDetection() : startDetection());

// Update detected faces and unknown faces
async function updateFaces() {
    const resCount = await fetch("/faces_count");
    const countData = await resCount.json();
    const now = Date.now();
    const fps = (1000 / (now - lastTime)).toFixed(1);
    lastTime = now;

    facesText.textContent = `Found ${countData.faces} face${countData.faces!==1?'s':''} | FPS: ${fps}`;

    // Update detected faces page
    const resDetected = await fetch("/detected_faces");
    const detectedFaces = await resDetected.json();
    facesGrid.innerHTML = "";
    detectedFaces.forEach(f => {
        const card = document.createElement("div");
        card.className = "face-card";
        const img = document.createElement("img");
        img.src = `data:image/jpeg;base64,${f.image}`;
        const name = document.createElement("p");
        name.textContent = f.name || "Unknown";
        card.appendChild(img);
        card.appendChild(name);
        facesGrid.appendChild(card);
    });

    // Update register unknown page
    const resUnknown = await fetch("/unknown_faces");
    const unknownFaces = await resUnknown.json();
    unknownFacesGrid.innerHTML = "";
    unknownFaces.forEach(u => {
        const card = document.createElement("div");
        card.className = "face-card";

        const img = document.createElement("img");
        img.src = `data:image/jpeg;base64,${u.image}`;

        const form = document.createElement("form");
        form.className = "register-form";

        const nameInput = document.createElement("input");
        nameInput.type = "text";
        nameInput.name = "name";
        nameInput.placeholder = "Name";

        const dobInput = document.createElement("input");
        dobInput.type = "text";
        dobInput.name = "dob";
        dobInput.placeholder = "Date of Birth";

        const nidInput = document.createElement("input");
        nidInput.type = "text";
        nidInput.name = "nid";
        nidInput.placeholder = "National ID";

        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "Register";
        btn.onclick = async () => {
            const formData = new FormData();
            formData.append("index", u.index);
            formData.append("name", nameInput.value);
            formData.append("dob", dobInput.value);
            formData.append("nid", nidInput.value);
            const res = await fetch("/register_face", {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                updateFaces(); // refresh cards
            } else {
                alert(data.message);
            }
        };

        form.appendChild(nameInput);
        form.appendChild(dobInput);
        form.appendChild(nidInput);
        form.appendChild(btn);

        card.appendChild(img);
        card.appendChild(form);

        unknownFacesGrid.appendChild(card);
    });
}
