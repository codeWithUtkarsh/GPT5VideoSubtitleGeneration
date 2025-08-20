# Overview

This is a web-based video subtitle translation application that processes video files and generates translated subtitles using AI. The application accepts video uploads or YouTube URLs, extracts audio, generates transcriptions using speech recognition, translates the text using GPT models, and outputs both SRT subtitle files and videos with embedded subtitles.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Technology**: HTML5 with Bootstrap 5 for responsive design and Font Awesome for icons
- **JavaScript**: Vanilla JavaScript with class-based architecture for client-side interactions
- **Features**: Real-time progress tracking, file validation, animated UI elements
- **Design Pattern**: Single-page application with dynamic content updates

## Backend Architecture
- **Framework**: Flask web framework with Python
- **Architecture Pattern**: Modular service-oriented design with separate processors for different concerns
- **Core Components**:
  - `VideoProcessor`: Handles video download, audio extraction, and speech recognition
  - `GPTTranslator`: Manages AI-powered text translation using OpenAI API
  - `SubtitleGenerator`: Creates SRT files and embeds subtitles into videos
- **Session Management**: Flask sessions with configurable secret keys
- **File Handling**: Secure file uploads with size limits (500MB) and extension validation

## Data Processing Pipeline
1. Video input (upload or URL download via yt-dlp)
2. Audio extraction using MoviePy
3. Speech-to-text conversion using SpeechRecognition library
4. Text translation via GPT API
5. Subtitle generation (SRT format and video embedding)
6. Asynchronous processing with real-time status updates

## Security Considerations
- File extension validation for video uploads
- Secure filename handling with Werkzeug utilities
- Proxy fix middleware for proper header handling
- Configurable session secrets for production environments

# External Dependencies

## AI Services
- **OpenAI API**: GPT-based translation service accessed via AI/ML API gateway
- **Speech Recognition**: Local speech-to-text processing using Google's speech recognition service

## Media Processing Libraries
- **MoviePy**: Video and audio manipulation, clip creation
- **yt-dlp**: YouTube and video platform downloading
- **pydub**: Audio processing and manipulation
- **SpeechRecognition**: Audio-to-text conversion

## Web Framework Dependencies
- **Flask**: Core web framework
- **Werkzeug**: WSGI utilities and security helpers
- **Bootstrap 5**: Frontend CSS framework
- **Font Awesome**: Icon library

## File Format Support
- **Video Formats**: MP4, AVI, MOV, MKV, WMV, FLV, WebM
- **Subtitle Format**: SRT (SubRip Subtitle format)
- **Audio Processing**: WAV, MP3 via pydub

## Infrastructure Requirements
- File system storage for uploads and processed videos
- Environment variable configuration for API keys
- Multi-threading support for concurrent video processing