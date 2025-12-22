const toggleBtn = document.getElementById('toggleBtn');
const facesText = document.getElementById('faces');
const videoFeed = document.getElementById('videoFeed');
const status = document.getElementById('status');
const statusIndicator = document.getElementById('statusIndicator');

let detecting = false
let updateInterval = null;
let lastTime = Date.now();

async function startDetection() {
    // Ask server to start detection
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

    updateInterval = setInterval(async ()=> {
        const res = await fetch("/faces_count");
        const data = await res.json();

        const now = Date.now();
        const fps = (1000 / (now - lastTime)).toFixed(1);
        lastTime = now;

        facesText.textContent = `Found ${data.faces} face${data.faces!==1?'s':''} | FPS: ${fps}`;
    }, 500);
}

async function stopDetection() {
    // Ask server to stop detection
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

    facesText.textContent = "Found 0 faces | FPS: 0";
    videoFeed.src = "";  // stop feed
    clearInterval(updateInterval);
}

toggleBtn.addEventListener("click", ()=> detecting ? stopDetection() : startDetection());

document.getElementById('registerBtn').addEventListener("click", async ()=> {
    const name = document.getElementById("nameInput").value.trim();
    const dob = document.getElementById("dobInput").value;
    const nid = document.getElementById("nidInput").value.trim();

    if (!name) { 
            status.textContent="Enter name to register."; 
            return; 
        }

    const form = new FormData();
    form.append("name", name);
    form.append("dob", dob);
    form.append("nid", nid);

    const res = await fetch("/register_face", {method:"POST", body:form});
    const data = await res.json();
    
    status.textContent = data.message;
});