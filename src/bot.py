"""
Core logic for the Google Meet Bot.
"""
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from src.config import SELECTORS, BROWSER_LAUNCH_ARGS, TIMEOUTS, CHECK_INTERVAL, EMPTY_MEETING_TIMEOUT
from src.logger import setup_logger
from src.recorder import MeetingRecorder
import os
import datetime

logger = setup_logger(__name__)

class MeetBot:
    def __init__(self, meeting_url: str, auth_dir: str, headless: bool = False):
        self.meeting_url = meeting_url
        self.auth_dir = auth_dir
        self.headless = headless
        self.playwright = None
        self.browser_context = None
        self.page = None
        self.recorder = MeetingRecorder()
        
        # Ensure debug directory exists
        os.makedirs("debug_screenshots", exist_ok=True)


    def start(self, bootstrap_signin: bool = False):
        logger.info("Starting Playwright...")
        self.playwright = sync_playwright().start()

        logger.info(f"Launching browser (Headless: {self.headless}, Auth: {self.auth_dir})")
        self.browser_context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.auth_dir,
            headless=True,
            args=BROWSER_LAUNCH_ARGS,
        )
        self.browser_context.grant_permissions(permissions=["microphone", "camera"])

        self.page = self.browser_context.new_page()

        if bootstrap_signin:
            self.perform_manual_signin()
        else:
            self.join_meeting()


    def join_meeting(self):
        try:
            logger.info(f"Navigating to {self.meeting_url}")
            self.page.goto(self.meeting_url)

            # state = self._detect_auth_state()

            # if state == "AUTH_REQUIRED":
            #     raise Exception("Google account not signed in. Aborting.")

            # if state == "GUEST_NOT_ALLOWED":
            #     raise Exception("Guest flow detected. Signed-in user required.")

            # if state != "AUTHENTICATED":
            #     raise Exception(f"Unexpected Meet state: {state}")

            # logger.info("Authenticated session confirmed.")

            self._wait_for_lobby()
            self._toggle_media()
            self._enter_name()
            self._click_join_button()
            self._wait_for_successful_entry()
            
            # Start Recording
            try:
                page_title = self.page.title()
                logger.info(f"Page Title for recording: {page_title}")
                self.recorder.start_recording(window_title=page_title)
            except Exception as e:
                logger.error(f"Failed to initiate recording: {e}")

            self._keep_alive()

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout Error: {e}")
            self._save_debug_screenshot("timeout_error")
            self.stop()
        except KeyboardInterrupt:
            logger.info("User interrupted the process.")
            self.stop()
        except Exception as e:
            logger.error(f"Join aborted: {e}", exc_info=True)
            self._save_debug_screenshot("join_error")
            self.stop()
        finally:
            # Ensure we always clean up (close browser/ffmpeg) even on normal exit
            self.stop()

    def perform_manual_signin(self):
        """
        Opens Google sign-in page and waits for user to manually authenticate.
        Session will be persisted in auth_dir.
        """
        logger.info("Opening Google sign-in page for manual authentication...")

        # 1. Go to the login page
        try:
            self.page.goto("https://accounts.google.com/ServiceLogin")
        except PlaywrightTimeoutError:
            logger.error("Failed to load Google login page (network timeout).")
            return

        # 2. Check if we strictly land on a logged-in page (e.g. myaccount)
        #    Give it a moment to redirect if we have a valid cookie.
        try:
            # We wait a short bit to see if it redirects automatically to a signed-in dashboard
            self.page.wait_for_url("https://myaccount.google.com/**", timeout=5000)
            logger.info("Redirected to My Account immediately - Session is ALREADY AUTHENTICATED.")
            logger.info("No manual action required. Exiting.")
            return
        except PlaywrightTimeoutError:
            # Not already signed in (or it takes longer). Proceed to manual flow.
            pass

        # 3. Manual Wait Logic
        logger.info(">>> VNC ACTION REQUIRED <<<")
        logger.info("Browser is NOT authenticated. Please interact via VNC to sign in.")
        logger.info("Waiting for successful login (redirect to myaccount.google.com)...")

        try:
            # Successful login usually redirects to myaccount.google.com or a specific product page.
            # MyAccount is the most reliable generic post-login landing.
            self.page.wait_for_url(
                "https://myaccount.google.com/**",
                timeout=300_000  # 5 minutes
            )
            logger.info("Google account sign-in successful! Session saved.")

        except PlaywrightTimeoutError:
            logger.error("Sign-in timed out (5 minutes). Login not completed.")
            raise Exception("Manual sign-in timed out.")

    def _detect_auth_state(self) -> str:
        logger.info("Detecting authentication state...")
        self.page.wait_for_timeout(2000)

        if self.page.locator(SELECTORS["sign_in_button"]).count() > 0:
            return "AUTH_REQUIRED"

        # If name input exists → guest page → reject
        if self.page.locator(SELECTORS["name_input"]).count() > 0:
            return "GUEST_NOT_ALLOWED"

        # Authenticated users ALWAYS see Join now / Ask to join
        if self.page.locator(SELECTORS["join_confirm_text"]).count() > 0:
            return "AUTHENTICATED"

        return "UNKNOWN"



    def _wait_for_lobby(self):
        """Waits for the 'Ready to join' screen indicators (Mic button OR Name Input)."""
        logger.info("Waiting for lobby to load...")

        # 1. Handle "Permissions" popup if it appears
        try:
            if self.page.locator(SELECTORS["permissions_popup"]).is_visible(timeout=5000):
                logger.info("Permissions popup detected. Dismissing...")
                self.page.locator(SELECTORS["dismiss_permissions_btn"]).click()
                self.page.wait_for_timeout(1000)
        except Exception:
            # It's okay if it doesn't appear or we don't catch it in time
            pass
        
        # 2. Wait for either the mic button (Authenticated) OR name input (Guest)
        try:
            self.page.wait_for_selector(
                f"{SELECTORS['lobby_validation']},{SELECTORS['name_input']}", 
                state="visible",
                timeout=TIMEOUTS["page_load"]
            )
        except PlaywrightTimeoutError:
            # If standard wait fails, try to see if we are stuck on a login page
            if self.page.locator(SELECTORS['sign_in_button']).count() > 0:
                raise Exception("Stuck on Sign-In page. Auth required.")
            raise

    def _toggle_media(self):
        """Ensures Microphone and Camera are turned off."""
        self._set_media_state("microphone", SELECTORS["mic_button"], "Turn off microphone")
        self._set_media_state("camera", SELECTORS["cam_button"], "Turn off camera")

    def _enter_name(self):
        """Checks for name input field and enters a default name if present."""
        logger.info("Checking for name input field...")
        try:
            name_input = self.page.locator(SELECTORS["name_input"])
            if name_input.count() > 0 and name_input.is_visible():
                logger.info("Name input found. Entering guest name...")
                name_input.fill("Meet Bot")
                self.page.wait_for_timeout(TIMEOUTS["action_delay"])
            else:
                logger.info("No name input field found. Proceeding...")
        except Exception as e:
            logger.warning(f"Error handling name input: {e}")

    def _set_media_state(self, name, selector, off_indicator_text):
        """
        Helper to toggle media buttons.
        name: 'microphone' or 'camera'
        selector: css selector for the button
        off_indicator_text: text in aria-label that indicates the device is CURRENTLY ON (so we need to click to turn off)
        """
        logger.info(f"Checking {name} state...")
        try:
            btn = self.page.locator(selector).first
            aria_label = btn.get_attribute("aria-label") or ""
            
            # If the label says "Turn off microphone", it means it is currently ON.
            if off_indicator_text.lower() in aria_label.lower():
                logger.info(f"{name.capitalize()} is ON. Clicking to MUTE/DISABLE.")
                btn.click()
                self.page.wait_for_timeout(TIMEOUTS["action_delay"])
            else:
                logger.info(f"{name.capitalize()} is already OFF.")
        except Exception as e:
            logger.warning(f"Failed to toggle {name}: {e}")

    def _click_join_button(self):
        """Finds and clicks the join button."""
        logger.info("Attempting to join...")
        
        # Try primary selector (Text match)
        join_btn = self.page.locator(SELECTORS["join_confirm_text"])
        
        if join_btn.count() > 0:
            logger.info("Found 'Join now' / 'Ask to join' button via text match.")
            join_btn.first.click()
        else:
            logger.warning("Primary join button not found. Trying fallback selectors...")
            # Try specific Ask to Join button
            ask_btn = self.page.locator(SELECTORS["ask_to_join_button"])
            if ask_btn.count() > 0:
                 logger.info("Found 'Ask to join' button.")
                 ask_btn.first.click()
                 return

            # Try generic fallback
            fallback_btn = self.page.locator(SELECTORS["join_button_fallback"])
            if fallback_btn.count() > 0:
                logger.info("Found join button via fallback selector.")
                fallback_btn.first.click()
                return

            raise Exception("Could not find a valid 'Join' button.")

    def _wait_for_successful_entry(self):
        """Verifies that we have successfully joined the meeting."""
        logger.info("Waiting for entry confirmation...")
        self.page.wait_for_selector(
            SELECTORS["leave_call_button"], 
            timeout=TIMEOUTS["page_load"]
        )
        logger.info("Successfully joined the meeting!")

    def _keep_alive(self):
        """Keeps the script running to maintain the browser session and monitors meeting status."""
        logger.info("Bot is active. Monitoring meeting status...")
        logger.info("Press Ctrl+C to stop manually.")
        
        empty_since = None

        while True:
            time.sleep(CHECK_INTERVAL)
            
            # 1. Check if we have been disconnected (End of call screen)
            try:
                # "Returning to home screen" or "You've left the meeting"
                if self.page.get_by_text("You've left the meeting").count() > 0 or \
                   self.page.url == "about:blank": # Simple check
                    logger.info("Meeting ended detected. Exiting...")
                    break
            except Exception:
                pass

            # 2. Check if meeting is empty
            is_empty = self._is_meeting_empty()
            if is_empty:
                if empty_since is None:
                    empty_since = time.time()
                    logger.info("Meeting appears empty. Timer started.")
                
                elapsed = time.time() - empty_since
                if elapsed > EMPTY_MEETING_TIMEOUT:
                    logger.info(f"Meeting has been empty for {elapsed:.0f}s. Leaving automatically.")
                    self._leave_call()
                    break
            else:
                if empty_since is not None:
                    logger.info("Meeting is no longer empty. Timer reset.")
                    empty_since = None

    def _leave_call(self):
        """Clicks the 'Leave call' button to properly exit the meeting."""
        logger.info("Clicking 'Leave call' button...")
        try:
            self.page.locator(SELECTORS["leave_call_button"]).click()
            self.page.wait_for_timeout(2000) # Wait for "You left" screen
        except Exception as e:
            logger.warning(f"Failed to click leave button (might already be closed): {e}")

    def _is_meeting_empty(self) -> bool:
        """
        Detect if the bot is alone by hovering over the participant avatar
        and reading the People popup ('1 joined', 'Just you').
        """
        logger.info("Checking if meeting is empty via hover...")

        try:
            # --------------------------------------------------
            # 1. Hover on top-right participant/avatar area
            # --------------------------------------------------
            viewport = self.page.viewport_size
            if not viewport:
                logger.warning("Viewport size unavailable.")
                return False

            # Hover near top-right corner (where avatar + count lives)
            hover_x = viewport["width"] - 40
            hover_y = 40

            self.page.mouse.move(hover_x, hover_y)
            self.page.wait_for_timeout(300)  # allow popup to render

            # --------------------------------------------------
            # 2. Detect People popup content
            # --------------------------------------------------
            if self.page.get_by_text("Just you", exact=True).count() > 0:
                logger.info("Empty meeting detected: 'Just you' (hover popup).")
                return True

            if self.page.get_by_text("1 joined", exact=True).count() > 0:
                logger.info("Empty meeting detected: '1 joined' (hover popup).")
                return True

            # --------------------------------------------------
            # 3. Defensive fallback: any 'joined' text starting with 1
            # --------------------------------------------------
            joined_texts = self.page.locator('*:has-text("joined")')

            for i in range(joined_texts.count()):
                txt = (joined_texts.nth(i).text_content() or "").strip().lower()
                if txt.startswith("1 "):
                    logger.info(f"Empty meeting detected via hover popup: '{txt}'.")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Hover-based empty check failed: {e}")
            return False



    def _save_debug_screenshot(self, suffix="error"):
        """Saves a screenshot for debugging purposes."""
        try:
            if self.page:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"debug_screenshots/{timestamp}_{suffix}.png"
                self.page.screenshot(path=filename)
                logger.info(f"Screenshot saved to {filename}")
        except Exception as e:
            logger.warning(f"Failed to save debug screenshot: {e}")

    def stop(self):
        """Cleans up resources."""
        logger.info("Stopping bot...")
        if self.recorder:
            self.recorder.stop_recording()
        if self.browser_context:
            self.browser_context.close()
        if self.playwright:
            self.playwright.stop()
