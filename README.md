# Meet Assistant

Meet Assistant is a powerful Python-based automation tool designed to interact with Google Meet. It provides functionality for automated joining, recording, and managing meeting sessions programmatically.

## Features

- **Automated Joining**: Seamlessly join Google Meet sessions using browser automation.
- **Meeting Recording**: Capture audio and video of the meeting sessions.
- **API Control**: Manage the bot and its actions via a RESTful API built with FastAPI.
- **Headless Operation**: Support for running in headless environments (e.g., Docker, servers).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/HemantPra389/Meet-Assistant.git
    cd Meet-Assistant
    ```

2.  **Set up a virtual environment (optional but recommended):**
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # Linux/MacOS
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright browsers:**
    ```bash
    playwright install
    ```

5.  **FFmpeg:**
    Ensure FFmpeg is installed and accessible in your system's PATH for recording functionality.

## Usage

### Running the API Server

Start the backend server to control the assistant:

```bash
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

### Running the Bot Standalone

You can also run the bot script directly for testing or single-session use:

```bash
python src/main.py --meeting-url "https://meet.google.com/abc-xyz-def"
```

## Structure

- `src/`: Core source code.
    - `bot.py`: Main logic for browser automation.
    - `recorder.py`: Handling of audio/video recording.
    - `api.py`: FastAPI application entry point.
    - `config.py`: Configuration settings.
- `user_data/`: Directory for storing browser profiles and session data.
- `recordings/`: Output directory for meeting recordings.

## Disclaimer

This tool is for educational and productivity purposes. Please ensure you have permission to record meetings and comply with all applicable privacy laws and Google's Terms of Service when using this software.
