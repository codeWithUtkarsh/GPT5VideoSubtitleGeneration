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
            logger.info(f"Starting speech recognition on: {audio_path}")
            
            # Load audio file
            audio = AudioSegment.from_wav(audio_path)
            logger.info(f"Audio loaded: {len(audio)}ms duration, {audio.frame_rate}Hz, {audio.dBFS}dBFS")
            
            # If audio is very quiet, adjust the silence threshold
            if audio.dBFS < -40:
                silence_thresh = audio.dBFS - 8  # More sensitive for quiet audio
            else:
                silence_thresh = audio.dBFS - 14
            
            logger.info(f"Using silence threshold: {silence_thresh}dBFS")
            
            # Split on silence to get segments
            segments = split_on_silence(
                audio,
                min_silence_len=500,   # Reduced to 0.5 seconds
                silence_thresh=silence_thresh,
                keep_silence=300  # Keep 300ms of silence
            )
            
            logger.info(f"Audio split into {len(segments)} segments")
            
            # If no segments found, treat the whole audio as one segment
            if not segments:
                logger.info("No silence-based segments found, using entire audio")
                segments = [audio]
            
            speech_segments = []
            current_time = 0
            
            for i, segment in enumerate(segments):
                # Skip very short segments
                if len(segment) < 500:  # Less than 0.5 seconds
                    current_time += len(segment)
                    continue
                    
                logger.info(f"Processing segment {i+1}/{len(segments)}: {len(segment)}ms")
                
                # Export segment to temporary file for recognition
                segment_path = f"temp_segment_{i}.wav"
                segment.export(segment_path, format="wav")
                
                try:
                    # Recognize speech in segment
                    with sr.AudioFile(segment_path) as source:
                        # Adjust for ambient noise
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                        audio_data = self.recognizer.record(source)
                        text = self.recognizer.recognize_google(audio_data)
                    
                    logger.info(f"Segment {i+1} recognized: '{text}'")
                    
                    if text.strip():
                        speech_segments.append({
                            'start_time': current_time / 1000,  # Convert to seconds
                            'end_time': (current_time + len(segment)) / 1000,
                            'text': text.strip()
                        })
                
                except sr.UnknownValueError:
                    logger.info(f"Segment {i+1}: No speech recognized")
                except sr.RequestError as e:
                    logger.error(f"Speech recognition request error for segment {i+1}: {e}")
                except Exception as e:
                    logger.error(f"Error processing segment {i+1}: {e}")
                
                finally:
                    # Clean up temporary file
                    if os.path.exists(segment_path):
                        os.remove(segment_path)
                
                current_time += len(segment)
            
            logger.info(f"Total speech segments extracted: {len(speech_segments)}")
            for i, seg in enumerate(speech_segments):
                logger.info(f"Segment {i+1}: {seg['start_time']:.2f}s-{seg['end_time']:.2f}s: '{seg['text'][:50]}...'")
            
            return speech_segments
            
        except Exception as e:
            logger.error(f"Speech extraction error: {str(e)}")
            raise Exception(f"Failed to extract speech segments: {str(e)}")
