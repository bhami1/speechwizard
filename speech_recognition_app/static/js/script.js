document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const fileButton = document.getElementById('file-button');
    const uploadButton = document.getElementById('upload-button');
    const fileInfo = document.getElementById('file-info');
    const selectedFileName = document.getElementById('selected-file-name');
    const fileSizeWarning = document.getElementById('file-size-warning');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const historyBtn = document.getElementById('history-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar');
    const transcriptionList = document.getElementById('transcription-list');
    const emptyState = document.getElementById('empty-state');
    
    // File handling
    fileButton.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', handleFileSelection);
    
    // Drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropArea.classList.add('dragover');
    }
    
    function unhighlight() {
        dropArea.classList.remove('dragover');
    }
    
    dropArea.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length) {
            handleFile(files[0]);
        }
    }
    
    function handleFileSelection() {
        if (fileInput.files.length) {
            handleFile(fileInput.files[0]);
        }
    }
    
    function handleFile(file) {
        // Check if file is audio
        if (!file.type.startsWith('audio/')) {
            showFlashMessage('Please select an audio file.', 'error');
            return;
        }
        
        // Display file info
        fileInfo.style.display = 'block';
        selectedFileName.textContent = file.name;
        
        // Check file size (10MB limit as example)
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            fileSizeWarning.textContent = `File size exceeds 10MB limit (${(file.size / (1024 * 1024)).toFixed(2)}MB)`;
            fileSizeWarning.style.display = 'block';
        } else {
            fileSizeWarning.style.display = 'none';
        }
        
        // Enable upload button
        uploadButton.disabled = false;
    }
    
    // Upload functionality
    uploadButton.addEventListener('click', () => {
        if (!fileInput.files.length) {
            showFlashMessage('Please select a file first.', 'error');
            return;
        }
        
        // Simulate upload and processing
        showFlashMessage('Processing your audio...', 'success');
        
        // Here you would normally send the file to your server
        // For demo purposes, we'll just simulate a success after a delay
        uploadButton.disabled = true;
        uploadButton.textContent = 'Processing...';
        
        setTimeout(() => {
            showFlashMessage('Transcription completed successfully!', 'success');
            uploadButton.textContent = 'Start Transcription';
            uploadButton.disabled = false;
            
            // Reset the file selection
            fileInfo.style.display = 'none';
            fileInput.value = '';
            
            // Add the new transcription to history
            addTranscriptionToHistory({
                id: Date.now(),
                name: selectedFileName.textContent,
                date: new Date().toLocaleString(),
                text: 'This is a sample transcription text. In a real application, this would be the actual transcribed content from your audio file.'
            });
        }, 3000);
    });
    
    // Sidebar functionality
    historyBtn.addEventListener('click', toggleSidebar);
    closeSidebarBtn.addEventListener('click', toggleSidebar);
    overlay.addEventListener('click', closeSidebar);
    
    function toggleSidebar() {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
        loadTranscriptionHistory();
    }
    
    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
    }
    
    // Flash messages
    function showFlashMessage(message, type) {
        const flashMessagesContainer = document.querySelector('.flash-messages');
        const messageElement = document.createElement('div');
        messageElement.className = `flash-message ${type}`;
        messageElement.innerHTML = `
            <span>${message}</span>
            <span class="close-btn">&times;</span>
        `;
        
        flashMessagesContainer.appendChild(messageElement);
        
        // Add close functionality
        const closeBtn = messageElement.querySelector('.close-btn');
        closeBtn.addEventListener('click', () => {
            messageElement.remove();
        });
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            messageElement.remove();
        }, 5000);
    }
    
    // Transcription history
    function loadTranscriptionHistory() {
        // In a real app, you would fetch this from your server/database
        // For demo, we'll check localStorage
        let history = JSON.parse(localStorage.getItem('transcriptionHistory')) || [];
        
        if (history.length === 0) {
            emptyState.style.display = 'block';
        } else {
            emptyState.style.display = 'none';
            
            // Clear existing items except empty state
            Array.from(transcriptionList.children).forEach(child => {
                if (child !== emptyState) {
                    child.remove();
                }
            });
            
            // Add history items
            history.forEach(item => {
                const card = createTranscriptionCard(item);
                transcriptionList.insertBefore(card, emptyState);
            });
        }
    }
    
    function createTranscriptionCard(item) {
        const card = document.createElement('div');
        card.className = 'transcription-card';
        card.innerHTML = `
            <div class="transcription-header">
                <h4>${item.name}</h4>
                <span class="transcription-date">${item.date}</span>
            </div>
            <p class="transcription-preview">${item.text.substring(0, 100)}${item.text.length > 100 ? '...' : ''}</p>
        `;
        
        // Add click event to open full transcription
        card.addEventListener('click', () => {
            // In a real app, this would open a modal or navigate to a detail page
            alert(`Full transcription for ${item.name}:\n\n${item.text}`);
        });
        
        return card;
    }
    
    function addTranscriptionToHistory(item) {
        // In a real app, this would be handled by your backend
        // For demo, we'll use localStorage
        let history = JSON.parse(localStorage.getItem('transcriptionHistory')) || [];
        history.unshift(item); // Add to beginning of array
        localStorage.setItem('transcriptionHistory', JSON.stringify(history));
    }
    
    // Initialize wave animation
    initWaveAnimation();
    
    function initWaveAnimation() {
        const container = document.getElementById('wave-animation');
        
        // Create canvas for wave animation
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        const ctx = canvas.getContext('2d');
        
        // Animation parameters
        let time = 0;
        const colors = ['rgba(0, 198, 255, 0.3)', 'rgba(0, 114, 255, 0.2)', 'rgba(255, 51, 102, 0.2)'];
        
        function drawWave(color, amplitude, frequency, speed) {
            ctx.beginPath();
            
            for (let x = 0; x < canvas.width; x++) {
                const y = amplitude * Math.sin(x * frequency + time * speed) + canvas.height / 2;
                
                if (x === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();
        }
        
        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Draw multiple waves with different parameters
            drawWave(colors[0], 30, 0.01, 1);
            drawWave(colors[1], 40, 0.015, 0.8);
            drawWave(colors[2], 25, 0.02, 1.2);
            
            time += 0.05;
            requestAnimationFrame(animate);
        }
        
        animate();
        
        // Resize canvas on window resize
        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
    }
});