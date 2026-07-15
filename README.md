# Multimodal AI Anti-Cheating System

A real-time, local AI-powered proctoring system that combines computer vision and natural language processing (NLP) to detect suspicious behavioral patterns during remote online interview.

---

## Tech Stack

### Backend & Core Logic
- **Framework:** FastAPI (Python) - High-performance web framework for handling asynchronous stream payloads.
- **Computer Vision:** MediaPipe Face Mesh, OpenCV-Python.
- **Speech-to-Text (STT):** Faster-Whisper (via CTranslate2 engine) - Quantized local inference processing.
- **Natural Language Processing (NLP):** Hugging Face Transformers (`GPT-2` model architecture).
- **Deep Learning Framework:** PyTorch (`torch`).
- **Audio Processing Utilities:** Pydub, Audioop-lts (compatibility bridge for Python 3.13+).
- **Core Numerics:** NumPy.

### Environment & System Dependencies
- **Package & Environment Manager:** Anaconda / Miniconda (Python 3.13+)
- **System Audio Media Codec Wrapper:** FFmpeg Binaries (Gyan.dev build compilation)

---

## Features

### 1. Visual Tracking Core
- **Webcam Real-Time Frame Tracking:** Processes video feeds dynamically using OpenCV.
- **Biometric Face Landmarks:** Tracks intricate eye structures using the MediaPipe Face Mesh API.
- **Eye Aspect Ratio (EAR):** Computes geometric vector matrices across eyelids to register irregular blink sequences or prolonged closed eyes.
- **Gaze Mapping:** Measures iris positioning vectors over a sliding historical context window to verify true peripheral gaze direction anomalies.

### 2. Audio Tracking & Language Core
- **Audio Standardization:** Utilizes `pydub` to automatically slice incoming microphone frames down into optimized 16kHz Mono audio layers.
- **Localized Speech-to-Text (STT):** Implements OpenAI’s Whisper model via a quantized `faster-whisper` CTranslate2 wrapper to pull clean text transcripts directly on the CPU.
- **Linguistic Predictability Analysis:** Feeds transcripts through a local Hugging Face Transformer language decoder (`GPT-2`) to determine cross-entropy loss metrics.
- **Perplexity Detection:** Calculates statistical perplexity markers ($PPL = e^{\text{loss}}$) to instantly flag predictable structural patterns common in AI-generated helper scripts.

---

## Project Structure

```text
anti-cheating-ai/
│
├── app.py              # Main FastAPI Web Server controller (Webcam / Audio Orchestrator)
├── eye_tracker.py      # Independent Computer Vision matrix module 
├── audio_tracker.py    # Independent Speech-to-Text & Perplexity evaluation module
├── config.py           # Universal system sensitivity settings 
├── logger.py           # Diagnostic flag event recorder
├── requirements.txt    # System dependency manifest
├── rag_engine.py       # Manages the document indexing and database setup
├── rag_chat.py         # chatbot file for functionality testing
│
├── database/           # ChromaDB store vector here
└── context_docs/       # PDF/TXT interview data
    └── interview_questions.txt

```
---

## Installation & Configuration (Windows)

### 1. Clone the project

```bash
git clone <your-repo-url>
cd anti-cheating-ai
```

### 2. Configure Local FFmpeg library for audio processing 
1. Download a stable release archive from Gyan.dev FFmpeg Builds.

2. Extract the archive and ensure your executable tools sit neatly at C:\ffmpeg\bin\.

3. Add C:\ffmpeg\bin directly into your Windows User Environment Variables Path.

### 3. Initialize Environment (Using Conda)

```bash
conda create -n anti-cheat python=3.13
conda activate anti-cheat
pip install -r requirements.txt
```
### 4. Sensitivity Configuration 

Edit config.py to balance your security layout and prevent false flags:

```text
APP_CONFIG = {
    "detection": {
        "eyes": {
            "ear_threshold": 0.25
        },
        "audio": {
            "perplexity_threshold": 45.0,
            "min_word_count": 5
        }
    }
}
```
