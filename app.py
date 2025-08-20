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
        print("🚀 Upload request received")
        job_id = str(uuid.uuid4())
        processing_status[job_id] = {
            'status': 'uploading',
            'progress': 0,
            'message': 'Uploading file...'
        }
        
        # Use defaults - we'll parse manually if needed
        source_lang = 'auto'
        target_lang = 'en'
        video_url = ''
        
        # Parse raw request data manually to avoid Flask form parsing issues
        content_type = request.headers.get('Content-Type', '')
        print(f"📋 Content-Type: {content_type}")
        
        if 'multipart/form-data' in content_type:
            # Handle multipart form data manually
            print("📁 Handling multipart file upload...")
            
            # Get raw data
            raw_data = request.get_data()
            print(f"📊 Raw data size: {len(raw_data)} bytes")
            
            # Save raw data to temporary file for processing
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_temp_upload.dat")
            
            with open(temp_file_path, 'wb') as temp_file:
                temp_file.write(raw_data)
            
            # Extract the actual video file from multipart data
            try:
                # Find video file boundaries in the multipart data
                video_file_path = extract_video_from_multipart(raw_data, job_id)
                
                if video_file_path and os.path.exists(video_file_path):
                    print(f"✅ Video file extracted: {video_file_path}")
                    
                    threading.Thread(
                        target=process_video_from_file,
                        args=(job_id, video_file_path, source_lang, target_lang)
                    ).start()
                else:
                    return jsonify({'error': 'Failed to extract video file from upload'}), 400
            
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        elif 'application/json' in content_type:
            # Handle JSON data for URL processing
            print("🌐 Handling JSON URL request...")
            try:
                json_data = request.get_json()
                video_url = json_data.get('video_url', '').strip()
                source_lang = json_data.get('source_lang', 'auto')
                target_lang = json_data.get('target_lang', 'en')
                
                if video_url:
                    print(f"🔗 Processing URL: {video_url[:50]}...")
                    threading.Thread(
                        target=process_video_from_url,
                        args=(job_id, video_url, source_lang, target_lang)
                    ).start()
                else:
                    return jsonify({'error': 'No video URL provided'}), 400
            except Exception as json_error:
                print(f"❌ JSON parsing error: {json_error}")
                return jsonify({'error': 'Invalid JSON data'}), 400
        else:
            return jsonify({'error': 'Unsupported content type'}), 400
        
        return jsonify({'job_id': job_id})
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        print(f"💥 Upload failed: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

def extract_video_from_multipart(raw_data, job_id):
    """Extract video file from multipart form data manually"""
    try:
        import re
        
        # Convert to string for pattern matching
        data_str = raw_data.decode('latin1', errors='ignore')
        
        # Find file boundaries
        boundary_pattern = r'Content-Disposition: form-data; name="video_file"; filename="([^"]+)"'
        filename_match = re.search(boundary_pattern, data_str)
        
        if not filename_match:
            print("❌ No video file found in multipart data")
            return None
            
        filename = filename_match.group(1)
        print(f"📝 Found filename: {filename}")
        
        if not allowed_file(filename):
            print(f"❌ File type not allowed: {filename}")
            return None
        
        # Find the start of file content (after headers)
        content_start = data_str.find('\r\n\r\n', filename_match.end())
        if content_start == -1:
            print("❌ Could not find file content start")
            return None
        content_start += 4  # Skip \r\n\r\n
        
        # Find the end of file content (next boundary)
        boundary_end = data_str.find('\r\n------WebKitFormBoundary', content_start)
        if boundary_end == -1:
            boundary_end = len(data_str)
        
        # Extract file content
        file_content = raw_data[content_start:boundary_end]
        
        # Save to file
        secure_name = secure_filename(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{secure_name}")
        
        with open(file_path, 'wb') as video_file:
            video_file.write(file_content)
        
        print(f"✅ Video file saved: {file_path} ({len(file_content)} bytes)")
        return file_path
        
    except Exception as e:
        print(f"❌ Multipart extraction error: {e}")
        return None

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
