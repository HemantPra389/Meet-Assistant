"""
Core logic for the Google Meet Bot.
"""
import time
import os
import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from src.config import SELECTORS, BROWSER_LAUNCH_ARGS, TIMEOUTS, CHECK_INTERVAL
from src.logger import setup_logger
from src.recorder import MeetingRecorder

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

        os.makedirs("debug_screenshots", exist_ok=True)

    def start(self):
        logger.info("Starting Playwright...")
        self.playwright = sync_playwright().start()

        logger.info(f"Launching browser (Headless: {self.headless})")
        self.browser_context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.auth_dir,
            headless=False,
            args=BROWSER_LAUNCH_ARGS,
        )
        # self.browser_context.grant_permissions(["microphone", "camera"])
        self.page = self.browser_context.new_page()

        self.join_meeting()

    def join_meeting(self):
        try:
            logger.info(f"Navigating to {self.meeting_url}")
            self.page.goto(self.meeting_url)
            self._save_debug_screenshot("after_navigation")
            self.page.wait_for_timeout(10000)
            self._save_debug_screenshot("after_navigation_10s")
            self._wait_for_lobby()
            self._toggle_media()
            self._enter_name()
            self._click_join_button()
            self._wait_for_successful_entry()
            self._keep_alive()

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout Error: {e}")
            self._save_debug_screenshot("timeout_error")
        except KeyboardInterrupt:
            logger.info("User interrupted the process.")
        except Exception as e:
            logger.error(f"Join aborted: {e}", exc_info=True)
            self._save_debug_screenshot("join_error")
        finally:
            self.stop()

    def _wait_for_lobby(self):
        logger.info("Waiting for lobby to load...")
        self.page.wait_for_selector(
            f"{SELECTORS['lobby_validation']},{SELECTORS['name_input']}",
            state="visible",
            timeout=TIMEOUTS["page_load"]
        )

    def _toggle_media(self):
        self._set_media_state("microphone", SELECTORS["mic_button"], "Turn off microphone")
        self._set_media_state("camera", SELECTORS["cam_button"], "Turn off camera")

    def _enter_name(self):
        logger.info("Checking for name input field...")
        try:
            name_input = self.page.locator(SELECTORS["name_input"])
            if name_input.count() > 0 and name_input.is_visible():
                name_input.fill("Meet Bot")
                self.page.wait_for_timeout(TIMEOUTS["action_delay"])
        except Exception as e:
            logger.warning(f"Name input error: {e}")

    def _set_media_state(self, name, selector, off_text):
        try:
            btn = self.page.locator(selector).first
            aria = btn.get_attribute("aria-label") or ""
            if off_text.lower() in aria.lower():
                btn.click()
                self.page.wait_for_timeout(TIMEOUTS["action_delay"])
        except Exception as e:
            logger.warning(f"{name} toggle failed: {e}")

    def _click_join_button(self):
        logger.info("Attempting to join...")
        join_btn = self.page.locator(SELECTORS["join_confirm_text"])

        if join_btn.count() > 0:
            join_btn.first.click()
            return

        for selector in ("ask_to_join_button", "join_button_fallback"):
            btn = self.page.locator(SELECTORS[selector])
            if btn.count() > 0:
                btn.first.click()
                return

        raise Exception("Join button not found")

    def _wait_for_successful_entry(self):
        self.page.wait_for_selector(
            SELECTORS["leave_call_button"],
            timeout=TIMEOUTS["page_load"]
        )
        logger.info("Successfully joined the meeting!")

    def _keep_alive(self):
        logger.info("Monitoring meeting...")
        empty_since = None
        EMPTY_GRACE = 30

        while True:
            time.sleep(CHECK_INTERVAL)

            if self.page.is_closed():
                break

            try:
                if (
                    self.page.url == "about:blank" or
                    self.page.locator("text=You've left the meeting").is_visible(timeout=500)
                ):
                    break
            except Exception:
                pass

            try:
                is_empty = self._is_meeting_empty()
            except Exception:
                continue

            now = time.monotonic()
            if is_empty:
                empty_since = empty_since or now
                if now - empty_since >= EMPTY_GRACE:
                    self._leave_call()
                    break
            else:
                empty_since = None

    def _leave_call(self):
        try:
            self.page.locator(SELECTORS["leave_call_button"]).click()
            self.page.wait_for_timeout(2000)
        except Exception:
            pass

    def _is_meeting_empty(self) -> bool:
        try:
            count = self.page.locator('[data-participant-id]').count()
            logger.info(f"Detected {count} participant(s)")
            return count <= 1
        except Exception:
            return False

    def _save_debug_screenshot(self, suffix="error"):
        try:
            if self.page:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = f"debug_screenshots/{ts}_{suffix}.png"
                self.page.screenshot(path=path)
        except Exception:
            pass

    def stop(self):
        logger.info("Stopping bot...")
        if self.recorder:
            self.recorder.stop_recording()
        if self.browser_context:
            self.browser_context.close()
        if self.playwright:
            self.playwright.stop()
