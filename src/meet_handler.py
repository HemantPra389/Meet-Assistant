# import time
# from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# from .logger import setup_logger
# from .config import SELECTORS, BROWSER_LAUNCH_ARGS, TIMEOUTS


# logger = setup_logger(__name__)

# class MeetHandler:
#     def __init__(self, meeting_url: str, auth_dir: str, headless: bool = False):
#         self.meeting_url = meeting_url
#         self.auth_dir = auth_dir
#         self.headless = headless
#         self.playwright = None
#         self.browser_context = None
#         self.page = None
        
#     def start(self):
#         """Initializes the browser and starts the join flow."""
#         logger.info("Starting Playwright...")
#         self.playwright = sync_playwright().start()
        
#         logger.info(f"Launching browser (Headless={self.headless}, Auth Dir={self.auth_dir})")
#         self.browser_context = self.playwright.chromium.launch_persistent_context(
#             user_data_dir=self.auth_dir,
#             headless=self.headless,
#             args=[
#                 # "--use-fake-ui-for-media-stream",
#                 # "--use-fake-device-for-media-stream",
#                 # "--no-sandbox",
#                 # "--disable-setuid-sandbox",
#                 # "--disable-dev-shm-usage",
#                 "--disable-blink-features=AutomationControlled", # Avoids basic selenium/bot detection
#                 "--use-fake-ui-for-media-stream",  # Auto-accepts permission prompts for camera/mic
#                 "--disable-notifications",
#                 "--no-default-browser-check"
#             ]
#         )
        
#         self.page = self.browser_context.new_page()
#         self.join_meet()
    
#     def join_meet(self):
#         """Navigates to the meeting URL and joins the meeting."""
#         try:
#             logger.info(f"Navigating to {self.meeting_url}")
#             self.page.goto(self.meeting_url, wait_until="domcontentloaded")
            
#             # Check if we need to sign in
#             self._handle_authentication()

#             # 1. Wait for Lobby
#             self._wait_for_lobby()
            
#             # 2. Handle Inputs
#             self._toggle_media()

#             # 3. Enter Meeting
#             self._click_join_button()
            
#             # 4. Stay Connected
#             self._wait_for_successful_entry()
#             self._keep_alive()

#         except PlaywrightTimeoutError as e:
#             logger.error(f"Timeout Error: {e}")
#             self.stop()
#         except KeyboardInterrupt:
#             logger.info("User interrupted the process.")
#             self.stop()
#         except Exception as e:
#             logger.error(f"Unexpected error: {e}", exc_info=True)
#             self.stop()
    
#     def _wait_for_lobby(self):
#         """Waits for the 'Ready to join' screen indicators."""
#         logger.info("Waiting for lobby to load...")
#         try:
#             # Wait for the mic button is a reliable proxy for the controls loading
#             self.page.wait_for_selector(
#                 SELECTORS["lobby_validation"], 
#                 timeout=TIMEOUTS["page_load"]
#             )
#             logger.info("Lobby loaded successfully.")
#         except PlaywrightTimeoutError:
#             logger.warning("Lobby validation selector not found, but continuing...")

#     def _toggle_media(self):
#         """Ensures Microphone and Camera are turned off."""
#         self._set_media_state("microphone", SELECTORS["mic_button"], "Turn off microphone")
#         self._set_media_state("camera", SELECTORS["cam_button"], "Turn off camera")
        
#     def _set_media_state(self, name, selector, off_indicator_text):
#         """
#         Helper to toggle media buttons.
#         name: 'microphone' or 'camera'
#         selector: css selector for the button
#         off_indicator_text: text in aria-label that indicates the device is CURRENTLY ON (so we need to click to turn off)
#         """
#         logger.info(f"Checking {name} state...")
#         try:
#             btn = self.page.locator(selector).first
#             aria_label = btn.get_attribute("aria-label") or ""
            
#             # If the label says "Turn off microphone", it means it is currently ON.
#             if off_indicator_text.lower() in aria_label.lower():
#                 logger.info(f"{name.capitalize()} is ON. Clicking to MUTE/DISABLE.")
#                 btn.click()
#                 self.page.wait_for_timeout(TIMEOUTS["action_delay"])
#             else:
#                 logger.info(f"{name.capitalize()} is already OFF.")
#         except Exception as e:
#             logger.warning(f"Failed to toggle {name}: {e}")
    
#     def _handle_authentication(self):
#         """Wait for authentication to complete if needed."""
#         logger.info("Checking authentication status...")
#         try:
#             # Wait a moment for any auth redirects to happen
#             self.page.wait_for_timeout(2000)
            
#             # If we're on Google accounts page, we need to wait for user to sign in
#             if "accounts.google.com" in self.page.url:
#                 logger.info("Google Sign-in required. Please sign in in the browser window...")
#                 # Wait up to 2 minutes for user to sign in
#                 self.page.wait_for_url(lambda url: "meet.google.com" in url, timeout=120000)
#                 logger.info("Authentication completed, returning to Meet.")
#                 self.page.wait_for_timeout(2000)
#         except PlaywrightTimeoutError:
#             logger.warning("Authentication timeout, but continuing...")
#         except Exception as e:
#             logger.warning(f"Error during authentication check: {e}")
    
#     def _click_join_button(self):
#         """Finds and clicks the join button."""
#         logger.info("Attempting to join...")
        
#         # Try primary selector (Text match)
#         join_btn = self.page.locator(SELECTORS["join_confirm_text"])
        
#         if join_btn.count() > 0:
#             logger.info("Found 'Join now' / 'Ask to join' button.")
#             # Use a longer timeout and force click to handle navigation
#             try:
#                 join_btn.first.click(timeout=5000, force=True)
#                 logger.info("Join button clicked successfully.")
#                 # Wait for navigation if sign-in required
#                 self.page.wait_for_timeout(2000)
#             except PlaywrightTimeoutError:
#                 logger.info("Button click timed out, but may have triggered navigation. Waiting for page...")
#                 self.page.wait_for_timeout(3000)
#         else:
#             logger.warning("Primary join button not found. Trying fallback...")
#             # Simple fallback strategy could be added here if needed
#             raise Exception("Could not find a valid 'Join' button.")
#         try:
#             self.page.wait_for_selector(
#                 SELECTORS["leave_call_button"], 
#                 timeout=TIMEOUTS["page_load"]
#             )
#             logger.info("Successfully joined the meeting!")
#         except PlaywrightTimeoutError:
#             logger.warning("Leave button not found yet, but continuing...")
#             # Sometimes the page may still be loading, wait a bit more
#             self.page.wait_for_timeout(3000)
#             self.page.wait_for_selector(
#                 SELECTORS["leave_call_button"], 
#                 timeout=TIMEOUTS["page_load"]
#             )
#         logger.info("Successfully joined the meeting!")

#     def _keep_alive(self):
#         """Keeps the script running to maintain the browser session."""
#         logger.info("Bot is active. Press Ctrl+C to stop.")
#         while True:
#             time.sleep(1)

#     def stop(self):
#         """Cleans up resources."""
#         logger.info("Stopping bot...")
#         if self.browser_context:
#             self.browser_context.close()
#         if self.playwright:
#             self.playwright.stop()
