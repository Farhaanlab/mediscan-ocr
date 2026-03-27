const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadSection = document.getElementById('upload-section');
const loadingState = document.getElementById('loading-state');
const resultsSection = document.getElementById('results-section');
const resultsGrid = document.getElementById('results-grid');
const previewImage = document.getElementById('preview-image');
const scanNewBtn = document.getElementById('scan-new-btn');

// Trigger file input click
dropZone.addEventListener('click', () => fileInput.click());

// Handle drag and drop
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
});

dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length) handleFiles(files);
});

fileInput.addEventListener('change', function() {
    if (this.files.length) handleFiles(this.files);
});

function handleFiles(files) {
    const file = files[0];
    if (!file.type.startsWith('image/')) {
        alert('Please upload an image file.');
        return;
    }

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        previewImage.src = e.target.result;
        dropZone.classList.add('hidden');
        loadingState.classList.remove('hidden');
        uploadFile(file);
    };
    reader.readAsDataURL(file);
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/scan', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to scan image.');
        }

        renderResults(data);
    } catch (error) {
        alert(error.message);
        resetUI();
    }
}

function renderResults(data) {
    uploadSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    resultsGrid.innerHTML = '';

    if (!data.medicines || data.medicines.length === 0) {
        resultsGrid.innerHTML = `
            <div class="medicine-card error-card" style="grid-column: 1 / -1; text-align: center;">
                <h3>No medicines detected</h3>
                <p class="error-text">We couldn't read any clear medicine names from the image.</p>
            </div>
        `;
        return;
    }

    data.medicines.forEach((med, index) => {
        const card = document.createElement('div');
        card.className = med.matched_name ? 'medicine-card' : 'medicine-card error-card';
        card.style.animation = `fadeInUp 0.6s ease-out ${index * 0.1}s both`;

        if (med.matched_name) {
            card.innerHTML = `
                <div class="card-header">
                    <h3>${med.matched_name}</h3>
                    <div class="extracted-badge">Extracted: "${med.extracted_name}" (${med.match_score}% match)</div>
                </div>
                <div class="card-detail">
                    <label>Price</label>
                    <span class="price-tag">₹${med.price}</span>
                </div>
                <div class="card-detail">
                    <label>Composition</label>
                    <span>${med.composition}</span>
                </div>
                <div class="card-detail">
                    <label>Manufacturer</label>
                    <span>${med.manufacturer}</span>
                </div>
                <div class="card-detail">
                    <label>Pack Size</label>
                    <span>${med.pack_size}</span>
                </div>
            `;
        } else {
            card.innerHTML = `
                <div class="card-header">
                    <h3>Unknown Medicine</h3>
                    <div class="extracted-badge">Extracted: "${med.extracted_name}"</div>
                </div>
                <div class="error-text">
                    ${med.error || 'No confident match found in our database.'}
                </div>
            `;
        }
        
        resultsGrid.appendChild(card);
    });
}

function resetUI() {
    fileInput.value = '';
    dropZone.classList.remove('hidden');
    loadingState.classList.add('hidden');
    uploadSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
}

scanNewBtn.addEventListener('click', resetUI);
