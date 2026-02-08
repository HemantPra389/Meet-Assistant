"""
Configuration settings and selectors for the Google Meet Bot.
"""

# Default Settings
# Default Settings
DEFAULT_AUTH_DIR = "./user_data"
DEFAULT_MEETING_URL = "https://meet.google.com"

# Recording Settings
FFMPEG_CMD = "ffmpeg"
# NOTE: Run `ffmpeg -list_devices true -f dshow -i dummy` to find your device name on Windows
# On Linux (Docker), 'default' usually works with PulseAudio
AUDIO_DEVICE_NAME = "default" 
RECORDINGS_DIR = "./recordings"
VIDEO_RECORDING_ENABLED = True
FRAMERATE = 30
MIN_PARTICIPANTS_TO_RECORD = 1
AUDIO_FORMAT = "wav"

# Monitoring Settings
CHECK_INTERVAL = 2  # Seconds between checks
EMPTY_MEETING_TIMEOUT = 10  # Seconds to wait before leaving an empty meeting

# Selectors
# Google Meet DOM is dynamic, but aria-labels are generally stable.
SELECTORS = {
    "mic_button": 'div[role="button"][aria-label*="microphone"]',
    "cam_button": 'div[role="button"][aria-label*="camera"]',
    "join_confirm_text": 'span:text-matches("Join now|Ask to join", "i")',
    # Fallback join button if text matching fails (more generic)
    "join_button_fallback": 'button[has-text="Join now"], button[has-text="Ask to join"]',
    "leave_call_button": 'button[aria-label="Leave call"]',
    # Ready to join text to ensure we are on the lobby page
    # Sometimes it's a heading
    "lobby_validation": 'div[role="button"][aria-label*="microphone"]',
    # Guest Name Input
    "name_input": 'input[placeholder="Your name"]',
    "ask_to_join_button": 'button:has-text("Ask to join")',
    "sign_in_button": 'button:has-text("Sign in")',
    # Detection for empty meeting (Dynamic, but often contains "No one else is here")
    "no_one_here_text": 'text="No one else is here"',
    
    # Permissions Popup
    "permissions_popup": 'text="Do you want people to see and hear you in the meeting?"',
    "dismiss_permissions_btn": 'button:has-text("Continue without microphone and camera")',
}

# Browser Launch Arguments
BROWSER_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled", # Avoids basic selenium/bot detection
    "--use-fake-ui-for-media-stream",  # Auto-accepts permission prompts for camera/mic
    "--use-fake-device-for-media-stream", # Provides a fake camera/mic device
    "--disable-notifications",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

# Timeouts (in milliseconds)
TIMEOUTS = {
    "page_load": 30000,
    "element_wait": 15000,
    "action_delay": 500  # Small sleep between actions to look natural
}
