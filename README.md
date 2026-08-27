# AccessLearn AI - AI-Powered Educational Accessibility Platform

![AccessLearn AI Platform](https://img.shields.io/badge/WCAG%202.1-AA%20Compliant-success?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![Celery](https://img.shields.io/badge/Celery-Async%20Pipeline-green?style=for-the-badge&logo=celery)
![AI-Powered](https://img.shields.io/badge/AI-Whisper%20%7C%20Gemini%20%7C%20Braille-blueviolet?style=for-the-badge)

**AccessLearn AI** is a modern, WCAG 2.1 AA compliant, full-stack AI platform designed to make educational audio and video lectures universally accessible to students with visual, hearing, speech, and learning disabilities.

---

## 🌟 Key Accessibility Features

### 1. 📝 Whisper Lecture Transcription
Converts uploaded lecture audio or video (`MP3`, `WAV`, `MP4`, `M4A`, `OGG`, `WebM`) into accurate timestamped transcriptions. Students can click any timestamp tag (`⏱ 01:30 - 02:15`) to jump audio playback directly to that segment.

### 2. ✨ AI Content Simplification & Study Notes
Uses **Google Gemini API** / **HuggingFace T5** to transform complex academic lectures into:
- **Plain-Language Explanations**: Removes dense jargon and uses real-world analogies.
- **Executive Summaries**: Short 3–4 sentence summaries.
- **Key Takeaways & Keywords**: Essential vocabulary with plain-language definitions.
- **Structured Study Notes**: Topic-by-topic accessible notes for cognitive learning support.

### 3. 🔊 Accessible Text-to-Speech (TTS) Audio
Synthesizes lecture notes into playable MP3 audio files with a custom WCAG-compliant player featuring:
- Play / Pause toggles
- 10s Rewind and Forward buttons
- Playback speed selection (`0.75x`, `1.0x`, `1.25x`, `1.5x`, `2.0x`)
- Accessible timeline seek bar with ARIA progress indicators
- MP3 file download option

### 4. ⠿ Braille Ready Format (.BRF) Converter
Translates text into standard **Grade 1 & Grade 2 Braille** code:
- Formatted strictly to 40 characters per line (standard `.BRF` layout for 40-cell refreshable braille displays and embossers).
- Side-by-side **Unicode Braille visual preview** (`⠿⠠⠁⠌...`) and **ASCII Braille BRF view**.
- One-click `.BRF` file download.

---

## ♿ WCAG 2.1 AA Accessibility Features

- **Contrast & Theme Modes**: Light, Dark, and High Contrast Yellow-on-Black theme options.
- **Font Size Adjuster**: Dynamic text scaling (`Small`, `Medium`, `Large`, `Extra Large`).
- **Screen Reader Announcements**: Live region (`aria-live="polite"`) announcing navigation and pipeline status updates.
- **Keyboard Shortcuts**:
  - `Alt + U`: Go to Upload Dashboard
  - `Alt + T`: Toggle High Contrast Mode
  - `Alt + H`: Go to Homepage
  - `Tab`: High contrast focus outlines (`:focus-visible`)
- **Semantic Structure**: Screen-reader friendly landmarks (`<main>`, `<nav>`, `<header>`, `role="tablist"`).

---

## 🏗️ Architecture & Technology Stack

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                        AccessLearn Responsive UI                        │
 │  Landing Page | Upload Dashboard | Processing Pipeline | Results Viewer │
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │ REST API (JSON / Multipart File)
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │                            FastAPI Backend                              │
 │  /upload | /process | /status | /transcript | /summary | /audio | /braille│
 └─────────────────┬──────────────────────────────────────┬────────────────┘
                   │ Celery Task Queue / Async Engine     │ Service Layer
 ┌─────────────────▼────────────────┐   ┌─────────────────▼────────────────┐
 │        Background Pipeline       │   │           AI Services            │
 │  1. Transcription (Whisper)      │   │ • Whisper Speech Service         │
 │  2. AI Simplification & Notes    │   │ • Gemini / T5 NLP Simplifier     │
 │  3. Text-to-Speech (gTTS)        │   │ • TTS Synthesizer (MP3 Engine)   │
 │  4. Braille Converter (.BRF)     │   │ • Braille Engine (Grade 1 & 2)   │
 └──────────────────────────────────┘   └──────────────────────────────────┘
```

- **Backend**: FastAPI (Python)
- **Asynchronous Queue**: Celery + Redis (with embedded Async Background Thread fallback for instant run on machines without Redis)
- **AI Models**: OpenAI Whisper, Google Gemini API, HuggingFace T5, gTTS, BRF Braille Engine
- **Frontend**: Vanilla HTML5, Accessible CSS3, Reactive JS Single Page Application (SPA)

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Installation
Ensure you have **Python 3.9+** installed.

Clone or navigate to the project directory and install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Environment Variables (Optional)
Create a `.env` file from `.env.example`:
```bash
# Optional: Add API keys for live AI models (system automatically uses built-in smart fallback engine if blank)
GEMINI_API_KEY="your_gemini_api_key_here"
OPENAI_API_KEY="your_openai_api_key_here"
```

### 3. Run Application
Run the launcher script:
```bash
python run.py
```

Open your browser and navigate to:
- **Web App**: `http://127.0.0.1:8000`
- **Interactive API Docs**: `http://127.0.0.1:8000/docs`

---

## 📡 API Endpoints Summary

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `POST /api/upload` | `POST` | Upload audio/video lecture file |
| `POST /api/process/{id}` | `POST` | Start asynchronous AI processing pipeline |
| `GET /api/status/{id}` | `GET` | Retrieve real-time processing status and progress |
| `GET /api/transcript/{id}` | `GET` | Get timestamped transcription data |
| `GET /api/summary/{id}` | `GET` | Get executive summary and keywords |
| `GET /api/simplified/{id}` | `GET` | Get plain-language notes and simplified explanations |
| `GET /api/audio/{id}` | `GET` | Stream or download synthesized TTS MP3 file |
| `GET /api/braille/{id}` | `GET` | Download formatted `.BRF` braille file |
| `GET /api/lectures` | `GET` | List recent processed lectures |
