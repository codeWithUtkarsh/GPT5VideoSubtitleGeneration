#!/usr/bin/env python3
"""
Simple HTTP server for video subtitle translation
Uses basic HTTP server instead of Flask to avoid upload issues
"""

import os
import json
import uuid
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import cgi
import tempfile
import shutil

from video_processor import VideoProcessor
from gpt_translator import GPTTranslator
from subtitle_generator import SubtitleGenerator

# Global status storage
processing_status = {}

class VideoUploadHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/' or self.path == '/index.html':
            self.serve_index()
        elif self.path.startswith('/static/'):
            self.serve_static_file()
        elif self.path.startswith('/status/'):
            self.handle_status()
        elif self.path.startswith('/download/'):
            self.handle_download()
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/upload':
            self.handle_upload()
        else:
            self.send_error(404)
    
    def serve_index(self):
        """Serve the main HTML page"""
        try:
            with open('templates/index.html', 'r') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except FileNotFoundError:
            self.send_error(404, "HTML template not found")
    
    def serve_static_file(self):
        """Serve static files (CSS, JS)"""
        try:
            file_path = self.path[1:]  # Remove leading /
            
            # Determine content type
            if file_path.endswith('.css'):
                content_type = 'text/css'
            elif file_path.endswith('.js'):
                content_type = 'application/javascript'
            else:
                content_type = 'text/plain'
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except FileNotFoundError:
            self.send_error(404, "Static file not found")
    
    def handle_status(self):
        """Handle status requests"""
        job_id = self.path.split('/')[-1]
        
        if job_id in processing_status:
            status = processing_status[job_id]
            self.send_json_response(status)
        else:
            self.send_error(404, "Job not found")
    
    def handle_download(self):
        """Handle download requests"""
        job_id = self.path.split('/')[-1]
        
        if job_id in processing_status and processing_status[job_id]['status'] == 'completed':
            file_path = processing_status[job_id]['file_path']
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp4')
                    self.send_header('Content-Disposition', f'attachment; filename="subtitled_video_{job_id}.mp4"')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                except Exception as e:
                    print(f"Download error: {e}")
        
        self.send_error(404, "File not ready or not found")
    
    def handle_upload(self):
        """Handle video upload with simple parsing"""
        try:
            print("🚀 Upload request received")
            
            job_id = str(uuid.uuid4())
            processing_status[job_id] = {
                'status': 'uploading',
                'progress': 0,
                'message': 'Processing upload...'
            }
            
            content_type = self.headers.get('Content-Type', '')
            print(f"📋 Content-Type: {content_type}")
            
            if 'multipart/form-data' in content_type:
                # Handle file upload
                print("📁 Processing file upload...")
                
                # Parse multipart data with simple approach
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': content_type,
                    }
                )
                
                # Get form fields
                source_lang = form.getvalue('source_lang', 'auto')
                target_lang = form.getvalue('target_lang', 'en')
                
                # Get uploaded file
                if 'video_file' in form:
                    fileitem = form['video_file']
                    
                    if fileitem.filename:
                        print(f"📝 Uploaded file: {fileitem.filename}")
                        
                        # Save uploaded file
                        os.makedirs('uploads', exist_ok=True)
                        filename = f"{job_id}_{fileitem.filename}"
                        file_path = os.path.join('uploads', filename)
                        
                        # Write file data
                        with open(file_path, 'wb') as output_file:
                            shutil.copyfileobj(fileitem.file, output_file)
                        
                        print(f"✅ File saved: {file_path}")
                        
                        # Start processing in background
                        threading.Thread(
                            target=process_video_file,
                            args=(job_id, file_path, source_lang, target_lang)
                        ).start()
                        
                        # Return success response
                        self.send_json_response({'job_id': job_id})
                        return
                
                self.send_error(400, "No video file found")
                
            elif 'application/json' in content_type:
                # Handle JSON URL request
                print("🌐 Processing URL request...")
                
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length).decode('utf-8')
                
                data = json.loads(post_data)
                video_url = data.get('video_url', '').strip()
                source_lang = data.get('source_lang', 'auto')
                target_lang = data.get('target_lang', 'en')
                
                if video_url:
                    print(f"🔗 Processing URL: {video_url[:50]}...")
                    
                    # Start processing in background
                    threading.Thread(
                        target=process_video_url,
                        args=(job_id, video_url, source_lang, target_lang)
                    ).start()
                    
                    # Return success response
                    self.send_json_response({'job_id': job_id})
                    return
                else:
                    self.send_error(400, "No video URL provided")
            else:
                self.send_error(400, "Unsupported content type")
        
        except Exception as e:
            print(f"💥 Upload error: {e}")
            self.send_error(500, f"Upload failed: {str(e)}")
    
    def send_json_response(self, data):
        """Send JSON response"""
        json_data = json.dumps(data).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(json_data)))
        self.end_headers()
        self.wfile.write(json_data)


def process_video_file(job_id, file_path, source_lang, target_lang):
    """Process uploaded video file"""
    try:
        print(f"🎬 Starting video processing for job: {job_id}")
        
        processor = VideoProcessor()
        translator = GPTTranslator()
        subtitle_gen = SubtitleGenerator()
        
        # Update status
        processing_status[job_id].update({
            'status': 'processing',
            'progress': 10,
            'message': 'Extracting audio from video...'
        })
        
        # Check duration first
        duration = processor.get_video_duration(file_path)
        if duration > 600:  # 10 minutes
            processing_status[job_id].update({
                'status': 'error',
                'message': f'Video duration ({duration/60:.1f} minutes) exceeds 10-minute limit'
            })
            return
        
        # Extract audio
        processing_status[job_id].update({
            'progress': 25,
            'message': 'Processing audio...'
        })
        
        audio_path = processor.extract_audio(file_path)
        
        # Extract speech segments
        processing_status[job_id].update({
            'progress': 50,
            'message': 'Extracting speech from audio...'
        })
        
        speech_segments = processor.extract_speech_segments(audio_path)
        
        if not speech_segments:
            processing_status[job_id].update({
                'status': 'error',
                'message': 'No speech detected in video'
            })
            return
        
        # Translate segments
        processing_status[job_id].update({
            'progress': 75,
            'message': 'Translating text...'
        })
        
        translated_segments = translator.translate_segments(
            speech_segments, source_lang, target_lang
        )
        
        # Generate subtitles and video
        processing_status[job_id].update({
            'progress': 90,
            'message': 'Creating subtitled video...'
        })
        
        # Create output path
        os.makedirs('processed', exist_ok=True)
        output_path = os.path.join('processed', f"{job_id}_subtitled.mp4")
        
        subtitle_gen.add_subtitles_to_video(
            file_path, translated_segments, output_path
        )
        
        # Complete
        processing_status[job_id].update({
            'status': 'completed',
            'progress': 100,
            'message': 'Video processing completed!',
            'file_path': output_path
        })
        
        print(f"✅ Video processing completed for job: {job_id}")
        
    except Exception as e:
        print(f"❌ Processing error for job {job_id}: {e}")
        processing_status[job_id].update({
            'status': 'error',
            'message': f'Processing failed: {str(e)}'
        })


def process_video_url(job_id, video_url, source_lang, target_lang):
    """Process video from URL"""
    try:
        print(f"🌐 Starting URL processing for job: {job_id}")
        
        processor = VideoProcessor()
        translator = GPTTranslator()
        subtitle_gen = SubtitleGenerator()
        
        # Update status
        processing_status[job_id].update({
            'status': 'downloading',
            'progress': 10,
            'message': 'Downloading video...'
        })
        
        # Download video
        os.makedirs('uploads', exist_ok=True)
        video_path = processor.download_video(video_url, 'uploads', job_id)
        
        # Continue with same processing as file upload
        process_video_file(job_id, video_path, source_lang, target_lang)
        
    except Exception as e:
        print(f"❌ URL processing error for job {job_id}: {e}")
        processing_status[job_id].update({
            'status': 'error',
            'message': f'URL processing failed: {str(e)}'
        })


def run_server():
    """Run the HTTP server"""
    server_address = ('0.0.0.0', 5000)
    httpd = HTTPServer(server_address, VideoUploadHandler)
    
    print("🌐 Video Subtitle Translator Server")
    print("🚀 Server running on http://0.0.0.0:5000")
    print("📁 Ready for video uploads!")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.server_close()


if __name__ == "__main__":
    run_server()