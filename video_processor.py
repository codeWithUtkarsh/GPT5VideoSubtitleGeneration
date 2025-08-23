import os
import logging
import subprocess
import json
from pydub import AudioSegment
from pydub.silence import split_on_silence
import yt_dlp
import requests
import time
import re

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
        """Extract speech segments using AIML API Whisper Large with intelligent segmentation"""
        try:
            print(f"🎤 STARTING AIML WHISPER LARGE TRANSCRIPTION FROM: {audio_path}")
            logger.info(f"Starting AIML Whisper Large transcription on: {audio_path}")

            # AIML API configuration
            base_url = "https://api.aimlapi.com/v1"
            api_key = os.environ.get("OPENAI_API_KEY", "")

            if not api_key:
                raise Exception("OPENAI_API_KEY environment variable not set")

            print("🤖 SENDING AUDIO TO AIML API...")

            # Create STT task
            def create_stt():
                url = f"{base_url}/stt/create"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                }
                data = {
                    "model": "#g1_whisper-large",
                }

                with open(audio_path, "rb") as file:
                    files = {"audio": (os.path.basename(audio_path), file, "audio/wav")}
                    response = requests.post(url, data=data, headers=headers, files=files)

                if response.status_code >= 400:
                    print(f"Error: {response.status_code} - {response.text}")
                    raise Exception(f"API Error: {response.status_code} - {response.text}")
                else:
                    response_data = response.json()
                    print(f"✅ STT TASK CREATED: {response_data}")
                    return response_data

            # Get STT result
            def get_stt(gen_id):
                url = f"{base_url}/stt/{gen_id}"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                }
                response = requests.get(url, headers=headers)
                return response.json()

            # Intelligent text segmentation
            def create_segments_from_text(transcript, total_duration):
                """Split transcript into segments based on sentences and punctuation"""
                # Split by sentences (periods, exclamation marks, question marks)
                sentence_endings = re.split(r'([.!?]+)', transcript)
                sentences = []

                for i in range(0, len(sentence_endings) - 1, 2):
                    sentence = sentence_endings[i].strip()
                    punctuation = sentence_endings[i + 1] if i + 1 < len(sentence_endings) else ""
                    if sentence:
                        sentences.append(sentence + punctuation)

                # If no sentences found, split by commas or length
                if len(sentences) <= 1:
                    # Split by commas
                    parts = [part.strip() for part in transcript.split(',') if part.strip()]
                    if len(parts) <= 1:
                        # Split by word count (max 10 words per segment)
                        words = transcript.split()
                        parts = []
                        for i in range(0, len(words), 10):
                            parts.append(' '.join(words[i:i+10]))
                    sentences = parts

                # Create segments with estimated timing
                segments = []
                if sentences:
                    segment_duration = total_duration / len(sentences)

                    for i, sentence in enumerate(sentences):
                        start_time = i * segment_duration
                        end_time = min((i + 1) * segment_duration, total_duration)

                        segments.append({
                            'start_time': start_time,
                            'end_time': end_time,
                            'text': sentence.strip()
                        })

                return segments

            # Main transcription process
            stt_response = create_stt()
            gen_id = stt_response.get("generation_id")

            if not gen_id:
                raise Exception("No generation_id received from API")

            print(f"🔄 POLLING FOR RESULTS: {gen_id}")
            start_time = time.time()
            timeout = 600

            while time.time() - start_time < timeout:
                response_data = get_stt(gen_id)

                if response_data is None:
                    raise Exception("No response from API")

                status = response_data.get("status")

                if status == "waiting" or status == "active":
                    print("Still waiting... Checking again in 10 seconds.")
                    time.sleep(10)
                else:
                    if status == "completed":
                        transcript = response_data["result"]["results"]["channels"][0]["alternatives"][0]["transcript"]
                        print(f"✅ AIML TRANSCRIPTION SUCCESS!")
                        print(f"📝 EXTRACTED TEXT: '{transcript}'")

                        # Get audio duration
                        audio_segment = AudioSegment.from_wav(audio_path)
                        duration = len(audio_segment) / 1000

                        # Create intelligent segments
                        speech_segments = create_segments_from_text(transcript, duration)

                        if speech_segments:
                            print(f"📊 CREATED {len(speech_segments)} INTELLIGENT SEGMENTS:")
                            for i, segment in enumerate(speech_segments):
                                print(f"   🎬 SEGMENT {i+1}: {segment['start_time']:.2f}s-{segment['end_time']:.2f}s")
                                print(f"       💬 TEXT: '{segment['text']}'")
                        else:
                            # Fallback to single segment
                            speech_segments = [{
                                'start_time': 0.0,
                                'end_time': duration,
                                'text': transcript.strip()
                            }]

                        return speech_segments
                    else:
                        raise Exception(f"Transcription failed with status: {status}")

            # Timeout fallback
            print("Timeout reached. Creating fallback segment.")
            audio_segment = AudioSegment.from_wav(audio_path)
            duration = len(audio_segment) / 1000

            fallback_segments = [{
                'start_time': 0.0,
                'end_time': duration,
                'text': "Audio content detected - Transcription timeout"
            }]

            return fallback_segments

        except Exception as e:
            print(f"💥 AIML TRANSCRIPTION FAILED: {str(e)}")
            logger.error(f"AIML transcription error: {str(e)}")

            # Final fallback
            try:
                audio_segment = AudioSegment.from_wav(audio_path)
                duration = len(audio_segment) / 1000

                fallback_segments = [{
                    'start_time': 0.0,
                    'end_time': duration,
                    'text': "Audio content detected - Transcription failed"
                }]

                return fallback_segments
            except:
                return [{
                    'start_time': 0.0,
                    'end_time': 30.0,
                    'text': "Audio processing completed"
                }]
