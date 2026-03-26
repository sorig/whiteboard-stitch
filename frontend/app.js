let photos = [];         // [{name, path, data_url}]
let establishingIdx = 0; // index into photos[]
let stitchResult = null;

// --- DOM refs ---
const dropZone = document.getElementById("drop-zone");
const addPhotosBtn = document.getElementById("add-photos-btn");
const addMoreBtn = document.getElementById("add-more-btn");
const photoGrid = document.getElementById("photo-grid");
const selectionInfo = document.getElementById("selection-info");
const stitchBtn = document.getElementById("stitch-btn");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const saveBtn = document.getElementById("save-btn");

// Slider value displays
for (const id of ["canvas-scale", "detail-radius", "edge-radius", "output-quality"]) {
    const input = document.getElementById(id);
    const display = document.getElementById(id + "-val");
    input.addEventListener("input", () => { display.textContent = input.value; });
}

// Output format → show/hide quality slider
document.getElementById("output-format").addEventListener("change", (e) => {
    document.getElementById("quality-label").classList.toggle("hidden", e.target.value === "png");
});

// --- File selection ---
async function selectFiles() {
    const paths = await pywebview.api.select_files();
    if (paths && paths.length > 0) {
        await addFiles(paths);
    }
}

async function addFiles(paths) {
    const thumbnails = await pywebview.api.get_thumbnails(paths);
    // Avoid duplicates
    const existingPaths = new Set(photos.map(p => p.path));
    for (const t of thumbnails) {
        if (!existingPaths.has(t.path)) {
            photos.push(t);
        }
    }
    renderPhotos();
}

addPhotosBtn.addEventListener("click", selectFiles);
addMoreBtn.addEventListener("click", selectFiles);

// Drag and drop
dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
});

dropZone.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");

    const paths = [];
    for (const file of e.dataTransfer.files) {
        // pywebview provides full path via pywebviewFullPath
        const fullPath = file.pywebviewFullPath || file.name;
        if (/\.(jpe?g|png|heic|heif)$/i.test(fullPath)) {
            paths.push(fullPath);
        }
    }
    if (paths.length > 0) {
        await addFiles(paths);
    }
});

// Also allow clicking the entire drop zone
dropZone.addEventListener("click", (e) => {
    if (e.target === addPhotosBtn) return; // let the button handle its own click
    selectFiles();
});

// --- Render photo grid ---
function renderPhotos() {
    if (photos.length === 0) return;

    show("photos-section");
    show("settings-section");
    show("stitch-section");

    // Clamp establishing index
    if (establishingIdx >= photos.length) establishingIdx = 0;

    photoGrid.innerHTML = "";
    photos.forEach((photo, idx) => {
        const card = document.createElement("div");
        card.className = "photo-card" + (idx === establishingIdx ? " selected" : "");
        card.innerHTML = `
            ${idx === establishingIdx ? '<div class="badge">Establishing</div>' : ""}
            <img src="${photo.data_url}" alt="${photo.name}">
            <div class="photo-name">${photo.name}</div>
        `;
        card.addEventListener("click", () => {
            establishingIdx = idx;
            renderPhotos();
        });
        photoGrid.appendChild(card);
    });

    const closeCount = photos.length - 1;
    selectionInfo.textContent = `Establishing: ${photos[establishingIdx].name}  |  Close-ups: ${closeCount} photo${closeCount !== 1 ? "s" : ""}`;

    // Need at least 2 photos
    stitchBtn.disabled = photos.length < 2;

    // Hide upload zone once we have photos, show photo section
    hide("upload-section");
}

// --- Stitching ---
stitchBtn.addEventListener("click", async () => {
    const establishing = photos[establishingIdx];
    const closes = photos.filter((_, i) => i !== establishingIdx);

    const settings = {
        partition_method: document.getElementById("partition-method").value,
        canvas_scale: parseFloat(document.getElementById("canvas-scale").value),
        detail_transfer_radius: parseInt(document.getElementById("detail-radius").value),
        edge_blend_radius: parseInt(document.getElementById("edge-radius").value),
        output_format: document.getElementById("output-format").value,
        jpeg_quality: parseInt(document.getElementById("output-quality").value),
    };

    // Start stitching
    stitchBtn.disabled = true;
    hide("result-section");
    show("progress-section");
    progressFill.style.width = "0%";
    progressText.textContent = "Starting...";

    await pywebview.api.stitch(
        establishing.path,
        closes.map(c => c.path),
        settings
    );

    // Poll progress
    const poll = setInterval(async () => {
        const p = await pywebview.api.get_progress();
        progressFill.style.width = (p.fraction * 100) + "%";
        progressText.textContent = p.step;

        if (p.done) {
            clearInterval(poll);
            stitchBtn.disabled = false;
            hide("progress-section");

            if (p.result.error) {
                alert("Stitching failed: " + p.result.error);
                return;
            }

            stitchResult = p.result;
            await showResult(p.result);
        }
    }, 500);
});

// --- Results ---
async function showResult(result) {
    const imgData = await pywebview.api.get_image_data(result.stitched);
    document.getElementById("result-image").src = imgData;

    const sizeMB = await pywebview.api.get_file_size(result.stitched);
    document.getElementById("result-size").textContent = `Output: ${sizeMB} MB`;

    const homData = await pywebview.api.get_image_data(result.homographies);
    document.getElementById("diagnostics-homographies").src = homData;

    const maskData = await pywebview.api.get_image_data(result.masks);
    document.getElementById("diagnostics-masks").src = maskData;

    show("result-section");
}

saveBtn.addEventListener("click", async () => {
    if (stitchResult) {
        await pywebview.api.save_result(stitchResult.stitched);
    }
});

// --- Helpers ---
function show(id) { document.getElementById(id).classList.remove("hidden"); }
function hide(id) { document.getElementById(id).classList.add("hidden"); }
