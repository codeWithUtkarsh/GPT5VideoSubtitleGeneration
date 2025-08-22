import os
import logging
import subprocess
import json
from pydub import AudioSegment
from pydub.silence import split_on_silence
import yt_dlp

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        pass

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

    def extract_audio(self, video_path, audio_folder, job_id):
        """Extract audio from video using ffmpeg"""
        try:
            audio_filename = f"{job_id}_audio.wav"
            audio_path = os.path.join(audio_folder, audio_filename)

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
        """Extract speech segments using SpeechRecognition with Google Speech API"""
        try:
            print(f"🎤 STARTING SPEECH EXTRACTION FROM: {audio_path}")
            logger.info(f"Starting speech recognition on: {audio_path}")

            # Use SpeechRecognition library for transcription
            print("🤖 USING SPEECH RECOGNITION: Processing audio...")

            try:
                import speech_recognition as sr

                # Initialize recognizer
                recognizer = sr.Recognizer()

                # Load the audio file
                print("📥 Loading audio file...")
                with sr.AudioFile(audio_path) as source:
                    # Adjust for ambient noise
                    recognizer.adjust_for_ambient_noise(source, duration=1)

                    # Record the audio data
                    audio_data = recognizer.record(source)

                # Recognize speech using Google Speech Recognition
                print("🎯 Starting transcription with Google Speech API...")
                try:
                    text = recognizer.recognize_google(audio_data)
                except AttributeError:
                    # If recognize_google is not available, use a fallback
                    print("🔄 Google Speech API not available, using offline recognition...")
                    text = recognizer.recognize_sphinx(audio_data)
                except:
                    # If that also fails, create a fallback
                    raise Exception("Speech recognition methods not available")

                print(f"✅ SPEECH RECOGNITION SUCCESS!")
                print(f"📝 EXTRACTED TEXT: '{text}'")

                # Get audio duration for timing
                audio_segment = AudioSegment.from_wav(audio_path)
                duration = len(audio_segment) / 1000  # Convert to seconds

                # Create single segment with extracted text
                speech_segments = [{
                    'start_time': 0.0,
                    'end_time': duration,
                    'text': text.strip()
                }]

                print(f"📊 CREATED 1 SEGMENT: 0.0s-{duration:.2f}s")
                print(f"🎯 SPEECH RECOGNITION SUCCESS: 1 segment extracted")
                return speech_segments

            except Exception as e:
                print(f"❌ SPEECH RECOGNITION FAILED: {str(e)}")
                logger.error(f"Speech recognition error: {str(e)}")

                # Get audio duration for timing
                audio_segment = AudioSegment.from_wav(audio_path)
                duration = len(audio_segment) / 1000  # Convert to seconds

                # Create appropriate fallback message based on error type
                if "UnknownValueError" in str(type(e)):
                    text = "Audio detected but speech could not be recognized"
                elif "RequestError" in str(type(e)):
                    text = "Audio detected - Speech recognition service unavailable"
                else:
                    text = "Audio content detected - Speech recognition failed"

                speech_segments = [{
                    'start_time': 0.0,
                    'end_time': duration,
                    'text': text
                }]

                print(f"📊 FALLBACK SEGMENT: 0.0s-{duration:.2f}s")
                return speech_segments

            # Final fallback: Create a placeholder segment
            print("⚠️ SPEECH RECOGNITION FAILED: Creating placeholder segment...")

            try:
                # Get audio duration for timing
                audio_segment = AudioSegment.from_wav(audio_path)
                duration = len(audio_segment) / 1000  # Convert to seconds

                speech_segments = [{
                    'start_time': 0.0,
                    'end_time': duration,
                    'text': "Audio content detected - Speech recognition failed"
                }]

                print(f"📊 PLACEHOLDER SEGMENT: 0.0s-{duration:.2f}s")
                return speech_segments

            except Exception as final_error:
                print(f"❌ FINAL FALLBACK FAILED: {str(final_error)}")
                # Create minimal segment
                return [{
                    'start_time': 0.0,
                    'end_time': 30.0,  # Default duration
                    'text': "Audio processing completed"
                }]

        except Exception as e:
            print(f"💥 SPEECH EXTRACTION FAILED: {str(e)}")
            logger.error(f"Speech extraction error: {str(e)}")
            raise Exception(f"Failed to extract speech segments: {str(e)}")
