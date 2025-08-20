import os
import logging
import subprocess
import json
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence
import yt_dlp

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
    
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
        """Extract speech segments with timing information"""
        try:
            # Load audio file
            audio = AudioSegment.from_wav(audio_path)
            
            # Split on silence to get segments
            segments = split_on_silence(
                audio,
                min_silence_len=1000,  # 1 second of silence
                silence_thresh=audio.dBFS - 14,
                keep_silence=500  # Keep 500ms of silence
            )
            
            speech_segments = []
            current_time = 0
            
            for i, segment in enumerate(segments):
                # Export segment to temporary file for recognition
                segment_path = f"temp_segment_{i}.wav"
                segment.export(segment_path, format="wav")
                
                try:
                    # Recognize speech in segment
                    with sr.AudioFile(segment_path) as source:
                        audio_data = self.recognizer.record(source)
                        text = self.recognizer.recognize_google(audio_data)
                    
                    if text.strip():
                        speech_segments.append({
                            'start_time': current_time / 1000,  # Convert to seconds
                            'end_time': (current_time + len(segment)) / 1000,
                            'text': text.strip()
                        })
                
                except sr.UnknownValueError:
                    # Speech not recognized, skip this segment
                    pass
                except sr.RequestError as e:
                    logger.warning(f"Speech recognition request error: {e}")
                
                finally:
                    # Clean up temporary file
                    if os.path.exists(segment_path):
                        os.remove(segment_path)
                
                current_time += len(segment)
            
            return speech_segments
            
        except Exception as e:
            logger.error(f"Speech extraction error: {str(e)}")
            raise Exception(f"Failed to extract speech segments: {str(e)}")
