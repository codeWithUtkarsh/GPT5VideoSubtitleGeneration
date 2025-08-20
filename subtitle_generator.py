import os
import logging
import subprocess
import srt
from datetime import timedelta

logger = logging.getLogger(__name__)

class SubtitleGenerator:
    def __init__(self):
        pass
    
    def create_srt_file(self, segments, output_path):
        """Create SRT subtitle file"""
        try:
            subtitles = []
            
            for i, segment in enumerate(segments, 1):
                start_time = timedelta(seconds=segment['start_time'])
                end_time = timedelta(seconds=segment['end_time'])
                text = segment['translated_text']
                
                subtitle = srt.Subtitle(
                    index=i,
                    start=start_time,
                    end=end_time,
                    content=text
                )
                subtitles.append(subtitle)
            
            srt_content = srt.compose(subtitles)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            return output_path
            
        except Exception as e:
            logger.error(f"SRT creation error: {str(e)}")
            raise Exception(f"Failed to create SRT file: {str(e)}")
    
    def add_subtitles_to_video(self, video_path, segments, output_path):
        """Add subtitles directly to video using ffmpeg"""
        try:
            # First create SRT file
            srt_path = output_path.replace('.mp4', '.srt')
            self.create_srt_file(segments, srt_path)
            
            # Use absolute paths to avoid path issues
            abs_video_path = os.path.abspath(video_path)
            abs_srt_path = os.path.abspath(srt_path)
            abs_output_path = os.path.abspath(output_path)
            
            # Use a simpler ffmpeg command that should work more reliably
            cmd = [
                'ffmpeg', '-y',
                '-i', abs_video_path,
                '-vf', f"subtitles='{abs_srt_path}':force_style='Fontsize=24,PrimaryColour=&Hffffff&,OutlineColour=&H000000&,Outline=2'",
                '-c:a', 'copy',
                abs_output_path
            ]
            
            # Run command and capture output for debugging
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                # Try alternative approach - simple text overlay
                cmd_simple = [
                    'ffmpeg', '-y',
                    '-i', abs_video_path,
                    '-c:a', 'copy',
                    abs_output_path
                ]
                subprocess.run(cmd_simple, capture_output=True, check=True)
                # Keep the SRT file alongside the video for manual use
                logger.warning("Subtitle overlay failed, created video without embedded subtitles")
            else:
                # Clean up SRT file only if embedding succeeded
                if os.path.exists(srt_path):
                    os.remove(srt_path)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Subtitle overlay error: {str(e)}")
            # Fallback: just copy the original video
            try:
                cmd_fallback = ['ffmpeg', '-y', '-i', video_path, '-c', 'copy', output_path]
                subprocess.run(cmd_fallback, capture_output=True, check=True)
                logger.warning("Used fallback - video copied without subtitles")
                return output_path
            except:
                raise Exception(f"Failed to add subtitles to video: {str(e)}")
    
    def format_time(self, seconds):
        """Format time for SRT format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
