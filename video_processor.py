import os
import logging
import subprocess
import json
from pydub import AudioSegment
from pydub.silence import split_on_silence
import yt_dlp
import whisper

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
        """Extract speech segments using OpenAI Whisper"""
        try:
            print(f"🎤 STARTING WHISPER TRANSCRIPTION FROM: {audio_path}")
            logger.info(f"Starting Whisper transcription on: {audio_path}")

            # Load Whisper model
            print("🤖 LOADING WHISPER MODEL...")
            try:
                model = whisper.load_model("base")  # Using base model for balance of speed/accuracy
                print("✅ WHISPER MODEL LOADED SUCCESSFULLY")
            except Exception as model_error:
                print(f"❌ FAILED TO LOAD WHISPER MODEL: {str(model_error)}")
                raise Exception(f"Failed to load Whisper model: {str(model_error)}")

            # Transcribe audio with Whisper
            print("🎯 STARTING WHISPER TRANSCRIPTION...")
            try:
                result = model.transcribe(audio_path, verbose=True)

                # Extract segments with timing
                speech_segments = []

                if 'segments' in result and result['segments']:
                    print(f"📊 PROCESSING {len(result['segments'])} WHISPER SEGMENTS:")
                    for i, segment in enumerate(result['segments']):
                        start_time = segment.get('start', 0.0)
                        end_time = segment.get('end', start_time + 1.0)
                        text = segment.get('text', '').strip()

                        if text:  # Only include non-empty segments
                            speech_segments.append({
                                'start_time': start_time,
                                'end_time': end_time,
                                'text': text
                            })
                            print(f"   🎬 SEGMENT {i+1}: {start_time:.2f}s-{end_time:.2f}s")
                            print(f"       💬 TEXT: '{text}'")
                else:
                    # Fallback: use full text as single segment
                    text = result.get('text', '').strip()
                    if text:
                        # Get audio duration for timing
                        audio_segment = AudioSegment.from_wav(audio_path)
                        duration = len(audio_segment) / 1000

                        speech_segments = [{
                            'start_time': 0.0,
                            'end_time': duration,
                            'text': text
                        }]
                        print(f"📊 CREATED SINGLE SEGMENT: 0.0s-{duration:.2f}s")
                        print(f"💬 TEXT: '{text}'")
                    else:
                        raise Exception("No text extracted from audio")

                print(f"✅ WHISPER TRANSCRIPTION SUCCESS: {len(speech_segments)} segments extracted")
                return speech_segments

            except Exception as transcribe_error:
                print(f"❌ WHISPER TRANSCRIPTION FAILED: {str(transcribe_error)}")
                logger.error(f"Whisper transcription error: {str(transcribe_error)}")

                # Get audio duration for fallback
                try:
                    audio_segment = AudioSegment.from_wav(audio_path)
                    duration = len(audio_segment) / 1000

                    fallback_segments = [{
                        'start_time': 0.0,
                        'end_time': duration,
                        'text': "Audio content detected - Whisper transcription failed"
                    }]

                    print(f"📊 FALLBACK SEGMENT: 0.0s-{duration:.2f}s")
                    return fallback_segments

                except Exception as final_error:
                    print(f"❌ FINAL FALLBACK FAILED: {str(final_error)}")
                    return [{
                        'start_time': 0.0,
                        'end_time': 30.0,
                        'text': "Audio processing completed"
                    }]

        except Exception as e:
            print(f"💥 WHISPER EXTRACTION FAILED: {str(e)}")
            logger.error(f"Whisper extraction error: {str(e)}")
            raise Exception(f"Failed to extract speech segments with Whisper: {str(e)}")
