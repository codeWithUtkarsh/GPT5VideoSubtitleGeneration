import os
import logging
import subprocess
import json
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence
import yt_dlp
import whisper

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Load Whisper model (more accurate than Google Speech Recognition)
        print("🤖 Loading Whisper AI model for speech recognition...")
        self.whisper_model = whisper.load_model("base")
        print("✅ Whisper model loaded successfully!")
    
    def download_video(self, url, output_dir, job_id):
        """Download video from URL using yt-dlp"""
        try:
            output_path = os.path.join(output_dir, f"{job_id}_downloaded.%(ext)s")
            
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': output_path,
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find the downloaded file
            for file in os.listdir(output_dir):
                if file.startswith(f"{job_id}_downloaded"):
                    return os.path.join(output_dir, file)
            
            raise Exception("Downloaded file not found")
            
        except Exception as e:
            logger.error(f"Video download error: {str(e)}")
            raise Exception(f"Failed to download video: {str(e)}")
    
    def get_video_duration(self, video_path):
        """Get video duration in seconds using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-show_entries',
                'format=duration', '-of', 'csv=p=0', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Duration check error: {str(e)}")
            raise Exception(f"Failed to get video duration: {str(e)}")
    
    def extract_audio(self, video_path):
        """Extract audio from video using ffmpeg"""
        try:
            audio_path = video_path.rsplit('.', 1)[0] + '.wav'
            
            # Use ffmpeg to extract audio
            cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-ac', '1', '-ar', '16000', '-f', 'wav', audio_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            
            return audio_path
            
        except Exception as e:
            logger.error(f"Audio extraction error: {str(e)}")
            raise Exception(f"Failed to extract audio: {str(e)}")
    
    def extract_speech_segments(self, audio_path):
        """Extract speech segments with timing information using Whisper AI"""
        try:
            print(f"🎤 STARTING SPEECH EXTRACTION FROM: {audio_path}")
            logger.info(f"Starting speech recognition on: {audio_path}")
            
            # Method 1: OpenAI Whisper (Most Accurate)
            print("🤖 TRYING WHISPER AI: Most accurate speech recognition...")
            try:
                result = self.whisper_model.transcribe(audio_path, word_timestamps=True)
                
                print(f"✅ WHISPER SUCCESS!")
                print(f"📝 WHISPER DETECTED TEXT: '{result['text']}'")
                print(f"🌐 WHISPER DETECTED LANGUAGE: {result.get('language', 'unknown')}")
                
                # Extract segments with timing from Whisper
                speech_segments = []
                
                if 'segments' in result:
                    for i, segment in enumerate(result['segments']):
                        text = segment['text'].strip()
                        if text:
                            segment_info = {
                                'start_time': segment['start'],
                                'end_time': segment['end'], 
                                'text': text
                            }
                            speech_segments.append(segment_info)
                            print(f"📋 WHISPER SEGMENT {i+1}: {segment_info['start_time']:.2f}s-{segment_info['end_time']:.2f}s = '{text}'")
                else:
                    # Fallback: Use entire text with audio duration
                    audio_segment = AudioSegment.from_wav(audio_path)
                    duration = len(audio_segment) / 1000
                    
                    speech_segments = [{
                        'start_time': 0.0,
                        'end_time': duration,
                        'text': result['text'].strip()
                    }]
                    print(f"📊 WHISPER SINGLE SEGMENT: 0.0s-{duration:.2f}s")
                
                if speech_segments:
                    print(f"🎯 WHISPER SUCCESS: {len(speech_segments)} segments extracted")
                    return speech_segments
                
            except Exception as e:
                print(f"❌ WHISPER FAILED: {str(e)}")
            
            # Method 2: Google Speech Recognition (Fallback)
            print("🔍 TRYING GOOGLE SPEECH API: Fallback method...")
            try:
                with sr.AudioFile(audio_path) as source:
                    audio_data = self.recognizer.record(source)
                    text = self.recognizer.recognize_google(audio_data)
                
                print(f"✅ GOOGLE SPEECH SUCCESS!")
                print(f"📝 GOOGLE EXTRACTED TEXT: '{text}'")
                
                # Get audio duration for timing
                audio_segment = AudioSegment.from_wav(audio_path)
                duration = len(audio_segment) / 1000  # Convert to seconds
                
                speech_segments = [{
                    'start_time': 0.0,
                    'end_time': duration,
                    'text': text.strip()
                }]
                
                print(f"📊 GOOGLE SEGMENT: 0.0s-{duration:.2f}s")
                return speech_segments
                
            except sr.UnknownValueError:
                print("❌ GOOGLE SPEECH FAILED: No speech detected")
            except sr.RequestError as e:
                print(f"❌ GOOGLE SPEECH ERROR: {e}")
            
            # Method 3: Segment-based approach with Google (Final fallback)
            print("🔄 TRYING SEGMENT-BASED GOOGLE SPEECH: Final attempt...")
            
            # Load audio file
            audio = AudioSegment.from_wav(audio_path)
            print(f"📊 AUDIO INFO: {len(audio)}ms duration, {audio.frame_rate}Hz, {audio.dBFS:.1f}dBFS")
            
            # Split on silence to get segments
            segments = split_on_silence(
                audio,
                min_silence_len=300,   # 0.3 seconds
                silence_thresh=audio.dBFS - 10,
                keep_silence=200  # Keep 200ms of silence
            )
            
            print(f"📈 AUDIO SPLIT INTO {len(segments)} SEGMENTS")
            
            # If no segments found, treat the whole audio as one segment
            if not segments:
                print("⚠️ NO SEGMENTS FOUND, USING ENTIRE AUDIO")
                segments = [audio]
            
            speech_segments = []
            current_time = 0
            
            for i, segment in enumerate(segments):
                # Skip very short segments
                if len(segment) < 200:  # Less than 0.2 seconds
                    current_time += len(segment)
                    continue
                
                print(f"🔍 PROCESSING SEGMENT {i+1}/{len(segments)}: {len(segment)}ms")
                
                # Export segment to temporary file for recognition
                segment_path = f"temp_segment_{i}.wav"
                segment.export(segment_path, format="wav")
                
                try:
                    with sr.AudioFile(segment_path) as source:
                        audio_data = self.recognizer.record(source)
                        text = self.recognizer.recognize_google(audio_data)
                    
                    print(f"✅ SEGMENT {i+1} TEXT: '{text}'")
                    
                    if text.strip():
                        segment_info = {
                            'start_time': current_time / 1000,  # Convert to seconds
                            'end_time': (current_time + len(segment)) / 1000,
                            'text': text.strip()
                        }
                        speech_segments.append(segment_info)
                        print(f"💾 SAVED SEGMENT: {segment_info['start_time']:.2f}s-{segment_info['end_time']:.2f}s")
                
                except sr.UnknownValueError:
                    print(f"❌ SEGMENT {i+1}: No speech recognized")
                except sr.RequestError as e:
                    print(f"❌ SEGMENT {i+1} ERROR: {e}")
                except Exception as e:
                    print(f"❌ SEGMENT {i+1} EXCEPTION: {e}")
                
                finally:
                    # Clean up temporary file
                    if os.path.exists(segment_path):
                        os.remove(segment_path)
                
                current_time += len(segment)
            
            print(f"🎯 FINAL RESULT: {len(speech_segments)} speech segments extracted")
            for i, seg in enumerate(speech_segments):
                print(f"📋 SEGMENT {i+1}: {seg['start_time']:.2f}s-{seg['end_time']:.2f}s = '{seg['text']}'")
            
            return speech_segments
            
        except Exception as e:
            print(f"💥 SPEECH EXTRACTION FAILED: {str(e)}")
            logger.error(f"Speech extraction error: {str(e)}")
            raise Exception(f"Failed to extract speech segments: {str(e)}")
