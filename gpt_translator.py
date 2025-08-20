import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class GPTTranslator:
    def __init__(self):
        # Use the user's provided API configuration
        self.api_key = os.getenv("OPENAI_API_KEY", "32654f959e4c4c4287db76beea8dcd90")
        self.client = OpenAI(
            base_url="https://api.aimlapi.com/v1",
            api_key=self.api_key,
        )
    
    def translate_segments(self, segments, source_lang, target_lang):
        """Translate all speech segments"""
        try:
            print(f"🌍 STARTING TRANSLATION: {len(segments)} segments from {source_lang} to {target_lang}")
            logger.info(f"Starting translation of {len(segments)} segments from {source_lang} to {target_lang}")
            
            if not segments:
                print("❌ NO SEGMENTS TO TRANSLATE!")
                logger.warning("No segments to translate!")
                return []
            
            translated_segments = []
            
            for i, segment in enumerate(segments):
                print(f"🔤 TRANSLATING SEGMENT {i+1}/{len(segments)}:")
                print(f"   📥 ORIGINAL: '{segment['text']}'")
                logger.info(f"Translating segment {i+1}: '{segment['text'][:50]}...'")
                
                translated_text = self.translate_text(
                    segment['text'], 
                    source_lang, 
                    target_lang
                )
                
                print(f"   📤 TRANSLATED: '{translated_text}'")
                print(f"   ⏱️  TIMING: {segment['start_time']:.2f}s - {segment['end_time']:.2f}s")
                logger.info(f"Translation result: '{translated_text[:50]}...'")
                
                translated_segment = {
                    'start_time': segment['start_time'],
                    'end_time': segment['end_time'],
                    'original_text': segment['text'],
                    'translated_text': translated_text
                }
                translated_segments.append(translated_segment)
                print(f"   ✅ SEGMENT {i+1} COMPLETE")
            
            print(f"🎯 TRANSLATION COMPLETE: {len(translated_segments)} segments successfully translated")
            logger.info(f"Successfully translated {len(translated_segments)} segments")
            return translated_segments
            
        except Exception as e:
            print(f"💥 TRANSLATION FAILED: {str(e)}")
            logger.error(f"Translation error: {str(e)}")
            raise Exception(f"Failed to translate segments: {str(e)}")
    
    def translate_text(self, text, source_lang, target_lang):
        """Translate a single text using GPT-5"""
        try:
            # Map language codes to full names for better GPT understanding
            lang_map = {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'ja': 'Japanese',
                'ko': 'Korean',
                'zh': 'Chinese',
                'ar': 'Arabic',
                'hi': 'Hindi',
                'auto': 'auto-detect'
            }
            
            source_language = lang_map.get(source_lang, source_lang)
            target_language = lang_map.get(target_lang, target_lang)
            
            if source_lang == 'auto':
                prompt = f"Translate the following text to {target_language}. Preserve the original meaning and tone. Only return the translated text, nothing else:\n\n{text}"
            else:
                prompt = f"Translate the following {source_language} text to {target_language}. Preserve the original meaning and tone. Only return the translated text, nothing else:\n\n{text}"
            
            response = self.client.chat.completions.create(
                model="openai/gpt-5-2025-08-07",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate text accurately while preserving meaning, tone, and context. Return only the translated text without any additional commentary."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            translated_text = response.choices[0].message.content
            if translated_text:
                return translated_text.strip()
            else:
                return text
            
        except Exception as e:
            logger.error(f"GPT translation error: {str(e)}")
            # Return original text if translation fails
            return text
    
    def get_supported_languages(self):
        """Return supported language codes"""
        return {
            'auto': 'Auto-detect',
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi'
        }
