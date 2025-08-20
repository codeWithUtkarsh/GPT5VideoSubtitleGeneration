import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import threading
from video_processor import VideoProcessor
from gpt_translator import GPTTranslator
from subtitle_generator import SubtitleGenerator

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'}

# Store processing status
processing_status = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    try:
        job_id = str(uuid.uuid4())
        processing_status[job_id] = {
            'status': 'uploading',
            'progress': 0,
            'message': 'Uploading file...'
        }
        
        # Get form data
        source_lang = request.form.get('source_lang', 'auto')
        target_lang = request.form.get('target_lang', 'en')
        video_url = request.form.get('video_url', '').strip()
        
        if video_url:
            # Process video from URL
            threading.Thread(
                target=process_video_from_url,
                args=(job_id, video_url, source_lang, target_lang)
            ).start()
        else:
            # Process uploaded file
            if 'video_file' not in request.files:
                return jsonify({'error': 'No file selected'}), 400
            
            file = request.files['video_file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
                file.save(file_path)
                
                threading.Thread(
                    target=process_video_from_file,
                    args=(job_id, file_path, source_lang, target_lang)
                ).start()
            else:
                return jsonify({'error': 'Invalid file type'}), 400
        
        return jsonify({'job_id': job_id})
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/status/<job_id>')
def get_status(job_id):
    if job_id in processing_status:
        return jsonify(processing_status[job_id])
    return jsonify({'error': 'Job not found'}), 404

@app.route('/download/<job_id>')
def download_video(job_id):
    try:
        if job_id in processing_status and processing_status[job_id]['status'] == 'completed':
            file_path = processing_status[job_id]['file_path']
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True)
        return jsonify({'error': 'File not ready or not found'}), 404
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500

def process_video_from_url(job_id, video_url, source_lang, target_lang):
    try:
        processor = VideoProcessor()
        translator = GPTTranslator()
        subtitle_gen = SubtitleGenerator()
        
        # Update status
        processing_status[job_id]['status'] = 'downloading'
        processing_status[job_id]['message'] = 'Downloading video...'
        processing_status[job_id]['progress'] = 10
        
        # Download video
        video_path = processor.download_video(video_url, app.config['UPLOAD_FOLDER'], job_id)
        
        # Check duration
        duration = processor.get_video_duration(video_path)
        if duration > 600:  # 10 minutes
            processing_status[job_id]['status'] = 'error'
            processing_status[job_id]['message'] = 'Video exceeds 10 minute limit'
            return
        
        # Extract audio
        processing_status[job_id]['message'] = 'Extracting audio...'
        processing_status[job_id]['progress'] = 30
        audio_path = processor.extract_audio(video_path)
        
        # Extract speech segments with timing
        processing_status[job_id]['message'] = 'Extracting speech segments...'
        processing_status[job_id]['progress'] = 50
        segments = processor.extract_speech_segments(audio_path)
        
        # Translate text
        processing_status[job_id]['message'] = 'Translating text...'
        processing_status[job_id]['progress'] = 70
        translated_segments = translator.translate_segments(segments, source_lang, target_lang)
        
        # Generate subtitles
        processing_status[job_id]['message'] = 'Generating subtitles...'
        processing_status[job_id]['progress'] = 85
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], f"{job_id}_subtitled.mp4")
        subtitle_gen.add_subtitles_to_video(video_path, translated_segments, output_path)
        
        # Complete
        processing_status[job_id]['status'] = 'completed'
        processing_status[job_id]['message'] = 'Video processed successfully!'
        processing_status[job_id]['progress'] = 100
        processing_status[job_id]['file_path'] = output_path
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        processing_status[job_id]['status'] = 'error'
        processing_status[job_id]['message'] = f'Processing failed: {str(e)}'

def process_video_from_file(job_id, file_path, source_lang, target_lang):
    try:
        processor = VideoProcessor()
        translator = GPTTranslator()
        subtitle_gen = SubtitleGenerator()
        
        # Update status
        processing_status[job_id]['status'] = 'processing'
        processing_status[job_id]['message'] = 'Validating video...'
        processing_status[job_id]['progress'] = 10
        
        # Check duration
        duration = processor.get_video_duration(file_path)
        if duration > 600:  # 10 minutes
            processing_status[job_id]['status'] = 'error'
            processing_status[job_id]['message'] = 'Video exceeds 10 minute limit'
            return
        
        # Extract audio
        processing_status[job_id]['message'] = 'Extracting audio...'
        processing_status[job_id]['progress'] = 30
        audio_path = processor.extract_audio(file_path)
        
        # Extract speech segments with timing
        processing_status[job_id]['message'] = 'Extracting speech segments...'
        processing_status[job_id]['progress'] = 50
        segments = processor.extract_speech_segments(audio_path)
        
        # Translate text
        processing_status[job_id]['message'] = 'Translating text...'
        processing_status[job_id]['progress'] = 70
        translated_segments = translator.translate_segments(segments, source_lang, target_lang)
        
        # Generate subtitles
        processing_status[job_id]['message'] = 'Generating subtitles...'
        processing_status[job_id]['progress'] = 85
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], f"{job_id}_subtitled.mp4")
        subtitle_gen.add_subtitles_to_video(file_path, translated_segments, output_path)
        
        # Complete
        processing_status[job_id]['status'] = 'completed'
        processing_status[job_id]['message'] = 'Video processed successfully!'
        processing_status[job_id]['progress'] = 100
        processing_status[job_id]['file_path'] = output_path
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        processing_status[job_id]['status'] = 'error'
        processing_status[job_id]['message'] = f'Processing failed: {str(e)}'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
