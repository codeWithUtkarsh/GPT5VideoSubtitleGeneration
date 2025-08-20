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
            # First create SRT file in a temporary location
            temp_srt_path = video_path.replace('.mov', '.srt').replace('.mp4', '.srt')
            self.create_srt_file(segments, temp_srt_path)
            
            # Verify the SRT file was created and has content
            if not os.path.exists(temp_srt_path):
                raise Exception(f"SRT file was not created: {temp_srt_path}")
            
            if os.path.getsize(temp_srt_path) == 0:
                raise Exception("SRT file is empty")
            
            # Use absolute paths to avoid path issues
            abs_video_path = os.path.abspath(video_path)
            abs_srt_path = os.path.abspath(temp_srt_path)
            abs_output_path = os.path.abspath(output_path)
            
            logger.info(f"Adding subtitles: video={abs_video_path}, srt={abs_srt_path}, output={abs_output_path}")
            
            # Try simpler approach first - drawtext filter for each subtitle segment
            filter_parts = []
            for i, segment in enumerate(segments):
                start_time = segment['start_time']
                end_time = segment['end_time']
                text = segment['translated_text'].replace("'", "\\'").replace(":", "\\:")
                
                filter_parts.append(f"drawtext=text='{text}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=h-th-10:enable='between(t,{start_time},{end_time})'")
            
            if filter_parts:
                video_filter = ",".join(filter_parts)
                
                cmd = [
                    'ffmpeg', '-y',
                    '-i', abs_video_path,
                    '-vf', video_filter,
                    '-c:a', 'copy',
                    abs_output_path
                ]
                
                logger.info(f"Running ffmpeg command: {' '.join(cmd[:6])}...")  # Log first few parts only
                
                # Run command and capture output for debugging
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info("Subtitles successfully embedded using drawtext")
                    # Clean up temp SRT file
                    if os.path.exists(temp_srt_path):
                        os.remove(temp_srt_path)
                    return output_path
                else:
                    logger.error(f"FFmpeg drawtext error: {result.stderr}")
            
            # Fallback: try with SRT file approach
            cmd_srt = [
                'ffmpeg', '-y',
                '-i', abs_video_path,
                '-vf', f"subtitles={abs_srt_path}",
                '-c:a', 'copy',
                abs_output_path
            ]
            
            result = subprocess.run(cmd_srt, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Subtitles successfully embedded using SRT file")
                # Clean up temp SRT file
                if os.path.exists(temp_srt_path):
                    os.remove(temp_srt_path)
                return output_path
            else:
                logger.error(f"FFmpeg SRT error: {result.stderr}")
                
                # Final fallback - copy video without subtitles but keep SRT
                cmd_simple = [
                    'ffmpeg', '-y',
                    '-i', abs_video_path,
                    '-c', 'copy',
                    abs_output_path
                ]
                subprocess.run(cmd_simple, capture_output=True, check=True)
                logger.warning("Created video without embedded subtitles, SRT file available separately")
                return output_path
            
        except Exception as e:
            logger.error(f"Subtitle overlay error: {str(e)}")
            # Final fallback: just copy the original video
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
