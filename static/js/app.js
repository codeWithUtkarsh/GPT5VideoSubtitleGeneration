// Video Subtitle Translator App
class VideoTranslatorApp {
    constructor() {
        this.currentJobId = null;
        this.pollInterval = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupVideoSourceToggle();
    }

    setupEventListeners() {
        // Form submission
        document.getElementById('videoForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFormSubmit();
        });

        // Video source toggle
        document.querySelectorAll('input[name="videoSource"]').forEach(radio => {
            radio.addEventListener('change', this.handleVideoSourceChange.bind(this));
        });

        // Download button
        document.getElementById('downloadBtn').addEventListener('click', () => {
            this.downloadVideo();
        });

        // New video button
        document.getElementById('newVideoBtn').addEventListener('click', () => {
            this.resetForm();
        });

        // Retry button
        document.getElementById('retryBtn').addEventListener('click', () => {
            this.resetForm();
        });

        // File input change
        document.getElementById('videoFile').addEventListener('change', (e) => {
            this.validateFileSize(e.target.files[0]);
        });
    }

    setupVideoSourceToggle() {
        const fileSection = document.getElementById('fileUploadSection');
        const urlSection = document.getElementById('urlInputSection');
        
        // Initially show file upload
        fileSection.classList.remove('d-none');
        urlSection.classList.add('d-none');
    }

    handleVideoSourceChange(e) {
        const fileSection = document.getElementById('fileUploadSection');
        const urlSection = document.getElementById('urlInputSection');
        
        if (e.target.value === 'file') {
            fileSection.classList.remove('d-none');
            urlSection.classList.add('d-none');
            // Clear URL input
            document.getElementById('videoUrl').value = '';
        } else {
            fileSection.classList.add('d-none');
            urlSection.classList.remove('d-none');
            // Clear file input
            document.getElementById('videoFile').value = '';
        }
    }

    validateFileSize(file) {
        if (!file) return true;

        const maxSize = 500 * 1024 * 1024; // 500MB
        
        if (file.size > maxSize) {
            this.showError('File size exceeds 500MB limit. Please choose a smaller file.');
            document.getElementById('videoFile').value = '';
            return false;
        }
        
        return true;
    }

    async handleFormSubmit() {
        try {
            // Validate form
            if (!this.validateForm()) {
                return;
            }

            // Show loading state
            this.showLoadingState();

            // Get form values
            const videoSource = document.querySelector('input[name="videoSource"]:checked').value;
            const sourceLang = document.getElementById('sourceLang').value;
            const targetLang = document.getElementById('targetLang').value;
            
            let response;

            if (videoSource === 'file') {
                // Handle file upload with multipart form data
                const fileInput = document.getElementById('videoFile');
                const videoFile = fileInput.files[0];
                
                const formData = new FormData();
                formData.append('video_file', videoFile);
                formData.append('source_lang', sourceLang);
                formData.append('target_lang', targetLang);

                response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
            } else {
                // Handle URL with JSON
                const videoUrl = document.getElementById('videoUrl').value.trim();
                
                response = await fetch('/upload', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        video_url: videoUrl,
                        source_lang: sourceLang,
                        target_lang: targetLang
                    })
                });
            }

            const result = await response.json();

            if (response.ok) {
                this.currentJobId = result.job_id;
                this.startProgressPolling();
            } else {
                this.showError(result.error || 'Upload failed');
            }

        } catch (error) {
            console.error('Form submission error:', error);
            this.showError('Failed to upload video. Please try again.');
        }
    }

    validateForm() {
        const videoSource = document.querySelector('input[name="videoSource"]:checked').value;
        
        if (videoSource === 'file') {
            const fileInput = document.getElementById('videoFile');
            if (!fileInput.files[0]) {
                this.showError('Please select a video file');
                return false;
            }
        } else {
            const urlInput = document.getElementById('videoUrl');
            if (!urlInput.value.trim()) {
                this.showError('Please enter a video URL');
                return false;
            }
            
            // Basic URL validation
            try {
                new URL(urlInput.value);
            } catch {
                this.showError('Please enter a valid URL');
                return false;
            }
        }

        // Validate language selection
        const sourceLang = document.getElementById('sourceLang').value;
        const targetLang = document.getElementById('targetLang').value;

        if (sourceLang === targetLang && sourceLang !== 'auto') {
            this.showError('Source and target languages cannot be the same');
            return false;
        }

        return true;
    }

    showLoadingState() {
        document.getElementById('uploadCard').classList.add('d-none');
        document.getElementById('progressCard').classList.remove('d-none');
        document.getElementById('resultCard').classList.add('d-none');
        document.getElementById('errorCard').classList.add('d-none');
        
        // Reset progress
        this.updateProgress(0, 'Uploading video...');
    }

    async startProgressPolling() {
        this.pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${this.currentJobId}`);
                const status = await response.json();

                if (response.ok) {
                    this.updateProgress(status.progress, status.message);

                    if (status.status === 'completed') {
                        this.handleCompletion();
                    } else if (status.status === 'error') {
                        this.handleError(status.message);
                    }
                } else {
                    this.handleError('Failed to get processing status');
                }
            } catch (error) {
                console.error('Polling error:', error);
                this.handleError('Connection error during processing');
            }
        }, 2000); // Poll every 2 seconds
    }

    updateProgress(progress, message) {
        const progressBar = document.getElementById('progressBar');
        const progressMessage = document.getElementById('progressMessage');

        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        progressBar.textContent = `${progress}%`;
        progressMessage.textContent = message;

        // Add animation class
        progressBar.classList.add('progress-bar-animated');
    }

    async handleCompletion() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }

        // Get the video URL from the server
        try {
            const response = await fetch(`/status/${this.currentJobId}`);
            const status = await response.json();
            
            if (status.video_url) {
                // Set up the video player
                const videoSource = document.getElementById('videoSource');
                const processedVideo = document.getElementById('processedVideo');
                
                videoSource.src = status.video_url;
                processedVideo.load(); // Reload the video element with new source
            }
        } catch (error) {
            console.error('Error loading video:', error);
        }

        document.getElementById('progressCard').classList.add('d-none');
        document.getElementById('resultCard').classList.remove('d-none');
    }

    handleError(message) {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }

        this.showError(message);
    }

    showError(message) {
        document.getElementById('uploadCard').classList.add('d-none');
        document.getElementById('progressCard').classList.add('d-none');
        document.getElementById('resultCard').classList.add('d-none');
        document.getElementById('errorCard').classList.remove('d-none');
        
        document.getElementById('errorMessage').textContent = message;
    }

    async downloadVideo() {
        try {
            if (!this.currentJobId) {
                this.showError('No video available for download');
                return;
            }

            // Create download link
            const downloadUrl = `/download/${this.currentJobId}`;
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = `translated_video_${this.currentJobId}.mp4`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (error) {
            console.error('Download error:', error);
            this.showError('Failed to download video');
        }
    }

    resetForm() {
        // Clear form
        document.getElementById('videoForm').reset();
        
        // Reset video source to file
        document.getElementById('fileSource').checked = true;
        this.handleVideoSourceChange({ target: { value: 'file' } });
        
        // Show upload card
        document.getElementById('uploadCard').classList.remove('d-none');
        document.getElementById('progressCard').classList.add('d-none');
        document.getElementById('resultCard').classList.add('d-none');
        document.getElementById('errorCard').classList.add('d-none');
        
        // Clear job ID
        this.currentJobId = null;
        
        // Stop polling
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new VideoTranslatorApp();
});

// Add some visual feedback for file drag and drop
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('videoFile');
    const fileInputContainer = fileInput.closest('.mb-4');

    // Drag and drop styling
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        fileInputContainer.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        fileInputContainer.addEventListener(eventName, () => {
            fileInputContainer.classList.add('border-primary', 'bg-light');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        fileInputContainer.addEventListener(eventName, () => {
            fileInputContainer.classList.remove('border-primary', 'bg-light');
        }, false);
    });

    fileInputContainer.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            // Trigger change event
            fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });
});
