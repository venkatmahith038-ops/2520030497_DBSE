import re
import os
import random
import time
import asyncio
from datetime import datetime, date, timezone
from typing import Optional
import threading
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright, Page, BrowserContext
from sqlalchemy.orm import Session
from backend.database import SessionLocal, Account, Target, MessageTemplate, BotLog, MetaConnection, log_to_db, MonitoredPost, ProcessedComment, OptOut, User, get_system_setting, set_system_setting, get_workspace_settings
from backend.config import settings
from backend.security import decrypt_secret

# Global running state flag
BOT_RUNNING = False
BOT_THREAD = None
BOT_LOOP = None

# Account ids currently paused because their workspace is outside working hours.
# Used only to log the transition once rather than on every loop tick.
PAUSED_OUTSIDE_HOURS: set[int] = set()
IST = ZoneInfo("Asia/Kolkata")


def is_within_working_hours(start_value: str, end_value: str, now_ist: Optional[datetime] = None) -> bool:
    """Return whether the current IST time is inside a normal or overnight window."""
    try:
        start_minutes = int(start_value[:2]) * 60 + int(start_value[3:5])
        end_minutes = int(end_value[:2]) * 60 + int(end_value[3:5])
    except (TypeError, ValueError, IndexError):
        return True

    current = now_ist or datetime.now(IST)
    current_minutes = current.hour * 60 + current.minute
    if start_minutes == end_minutes:
        return True
    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes

def create_browser_event_loop():
    """Return an event loop capable of launching Playwright subprocesses."""
    if os.name == "nt":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()

def parse_spintax(text: str) -> str:
    """Parses spintax pattern like '{Hello|Hi|Hey} {there|friend}!'. Supports nested patterns."""
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        options = match.group(1).split('|')
        text = text.replace(match.group(0), random.choice(options), 1)
    return text

MATCH_MODE_EXACT = "exact"
MATCH_MODE_ANY = "any"
COMMENT_MATCH_MODES = (MATCH_MODE_EXACT, MATCH_MODE_ANY)


def is_exact_trigger_match(comment_text: str, trigger_keyword: str) -> bool:
    """Require the complete comment to match the configured trigger."""
    normalize = lambda value: " ".join((value or "").strip().casefold().split())
    keyword = normalize(trigger_keyword)
    return bool(keyword) and normalize(comment_text) == keyword


def comment_matches_trigger(comment_text: str, trigger_keyword: str,
                            match_mode: str = MATCH_MODE_EXACT) -> bool:
    """Decide whether a single comment should trigger outreach.

    `exact` is the consent-preserving default: the whole comment must be the
    configured keyword, so the commenter has demonstrably opted in.

    `any` replies to every comment whatever it contains — a word, a paragraph
    or a bare emoji. That is deliberately not an opt-in signal, so it is only
    ever enabled per post and never by default. Every other guard still
    applies: opt-out blocklist, daily limit, working hours, and one DM per
    person per post.
    """
    text = (comment_text or "").strip()
    if match_mode == MATCH_MODE_ANY:
        return bool(text)
    return is_exact_trigger_match(comment_text, trigger_keyword)

def is_valid_instagram_username(username: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._]{1,30}", (username or "").strip()))

async def human_type(locator, text: str):
    """Simulates real human typing with random delays between characters on a Playwright Locator."""
    await locator.focus()
    for char in text:
        await locator.type(char, delay=random.randint(50, 150))
        await asyncio.sleep(random.uniform(0.01, 0.05))

class InstagramBot:
    def __init__(self, account_username: str, proxy: Optional[dict] = None):
        self.username = account_username
        self.user_data_dir = os.path.abspath(os.path.join(settings.USER_DATA_DIR, account_username))
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.proxy = proxy

    async def init_browser(self, headless: bool = False, persistent: bool = True) -> BrowserContext:
        """Initializes a browser context.

        Interactive and automation sessions use a persistent Chromium profile.
        Read-only verification uses an isolated context so it cannot lock that
        profile and prevent a visible login browser from opening.
        """
        self.playwright = await async_playwright().start()
        
        # User agent spoofing to sound more like a standard human browser
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # Check if storage state exists (uploaded cookies/localStorage)
        storage_state_file = os.path.join(self.user_data_dir, "storage_state.json")
        cookies_to_add = []
        if os.path.exists(storage_state_file):
            try:
                import json
                with open(storage_state_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                    if isinstance(state_data, dict):
                        cookies_to_add = state_data.get("cookies", [])
                    elif isinstance(state_data, list):
                        cookies_to_add = state_data
            except Exception as e:
                print(f"Error reading storage_state.json: {e}")
            
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        if persistent:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=headless,
                user_agent=user_agent,
                viewport={"width": 1280, "height": 720},
                proxy=self.proxy,
                args=launch_args,
            )
        else:
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                proxy=self.proxy,
                args=launch_args,
            )
            self.context = await self.browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1280, "height": 720},
            )
        
        # Inject cookies post-launch since storage_state is not supported in launch_persistent_context
        if cookies_to_add:
            try:
                # Clean up cookies to only pass valid keys and strip None/null values
                cleaned_cookies = []
                for cookie in cookies_to_add:
                    if not isinstance(cookie, dict):
                        continue
                    cleaned_cookie = {}
                    for k in ["name", "value", "url", "domain", "path", "expires", "httpOnly", "secure", "sameSite"]:
                        if k in cookie and cookie[k] is not None:
                            cleaned_cookie[k] = cookie[k]
                    cleaned_cookies.append(cleaned_cookie)
                await self.context.add_cookies(cleaned_cookies)
            except Exception as e:
                print(f"Error injecting cookies to browser context: {e}")
        
        # Use the default page created by persistent context instead of opening a new blank tab
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        # Execute JS to bypass navigator.webdriver detection
        await self.page.add_init_script(
            "const newProto = navigator.__proto__; delete newProto.webdriver; navigator.__proto__ = newProto;"
        )
        
        return self.context

    async def close_browser(self):
        """Closes browser context and playwright object."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"Error closing browser: {e}")
        finally:
            self.context = None
            self.browser = None
            self.playwright = None
            self.page = None

    async def check_login_status(self, navigate: bool = True) -> bool:
        """Checks if logged in by looking for dashboard indicators. If navigate=True, navigates to Instagram home first."""
        if not self.page:
            return False
        
        try:
            if navigate:
                log_to_db("INFO", f"Navigating to check Instagram login status for {self.username}...")
                try:
                    await self.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
                except Exception as goto_err:
                    log_to_db("WARNING", f"Navigation to check Instagram login status timed out or failed: {str(goto_err)}")
                await asyncio.sleep(4)
            
            current_url = self.page.url
            logged_out_paths = ("/accounts/login", "/challenge/", "/accounts/suspended/")
            if any(path in current_url for path in logged_out_paths):
                log_to_db("WARNING", f"Instagram requires authentication at: {current_url}")
                return False

            # Ask Instagram for the current user. This is more stable than UI
            # selectors, which change frequently and differ by account rollout.
            try:
                current_user = await self.page.evaluate("""
                    async () => {
                        const endpoints = [
                            '/api/v1/accounts/edit/web_form_data/',
                            '/api/v1/web/accounts/current_user/?__a=1'
                        ];
                        for (const endpoint of endpoints) {
                            try {
                                const response = await fetch(endpoint, {
                                    credentials: 'include',
                                    headers: {'X-IG-App-ID': '936619743392459'}
                                });
                                if (!response.ok) continue;
                                const data = await response.json();
                                const user = data?.form_data || data?.user;
                                if (user?.username || user?.pk || user?.id) return user;
                            } catch (_) {}
                        }
                        return null;
                    }
                """)
                if current_user:
                    verified_username = str(current_user.get("username", "")).lstrip("@").lower()
                    expected_username = self.username.lstrip("@").lower()
                    if verified_username and verified_username != expected_username:
                        log_to_db(
                            "WARNING",
                            f"Imported session belongs to @{verified_username}, not @{expected_username}.",
                        )
                        return False
                    log_to_db("INFO", f"Instagram API confirmed an active session for {self.username}.")
                    return True
            except Exception as api_error:
                log_to_db("WARNING", f"Instagram current-user check was unavailable: {api_error!r}")

            # DOM fallback for UI variants where the current-user endpoint is unavailable.
            logged_in_indicators = [
                'svg[aria-label="Direct"]',
                'svg[aria-label="Messenger"]',
                'svg[aria-label="New post"]',
                'svg[aria-label="Home"]',
                'svg[aria-label="Search"]',
                'a[href*="/direct/inbox/"]',
                'a[href="/accounts/edit/"]',
                'a[href^="/direct/"]',
            ]
            
            for selector in logged_in_indicators:
                if await self.page.locator(selector).is_visible():
                    log_to_db("INFO", f"User {self.username} is logged in successfully.")
                    return True
                    
            # Check if login form fields are visible
            login_form = await self.page.locator('input[name="username"]').is_visible()
            if login_form:
                log_to_db("WARNING", f"Login form input detected on page. User is logged out.")
                return False
                
            # If no logged in indicators are visible, strictly treat as not logged in
            return False
        except Exception as e:
            log_to_db("ERROR", f"Error checking login status: {type(e).__name__}: {e!r}")
            return False

    async def run_manual_login_session(self) -> bool:
        """Launches a visible browser window so the user can perform manual login/2FA."""
        log_to_db("INFO", f"Launching manual login browser window for {self.username}...")
        success = False
        browser_started = False
        try:
            await self.init_browser(headless=False)
            browser_started = True
            await self.page.goto("https://www.instagram.com/accounts/login/", wait_until="load")
            log_to_db("INFO", "Please perform the login in the opened browser window. Do not close it until completed.")
            
            # Wait for user to log in manually - we poll login state every 3 seconds
            # Or run until browser window is closed
            # Increased limit to 360 iterations (18 minutes) to give ample time for captchas/verification
            for _ in range(360): 
                if self.page.is_closed():
                    log_to_db("WARNING", "Login browser window closed by user.")
                    break
                
                # Check login state WITHOUT navigating away (so user can type password/2FA undisturbed)
                is_logged = await self.check_login_status(navigate=False)
                if is_logged:
                    log_to_db("SUCCESS", f"Successfully logged into account {self.username}! Saving session...")
                    await asyncio.sleep(8) # Give it extra time to write session cookies to local storage
                    success = True
                    break
                await asyncio.sleep(3)
                
        except Exception as e:
            log_to_db("ERROR", f"Manual login process failed: {type(e).__name__}: {e!r}")
            if not browser_started:
                raise
        finally:
            await self.close_browser()
            log_to_db("INFO", "Manual login browser window closed.")
            
        return success

    async def send_direct_message(self, target_username: str, message: str) -> bool:
        """Sends a direct message to a target username.
        Strategy 1: Profile 'Message' button (public/following accounts).
        Strategy 2: Three dots ... -> 'Send message' (private accounts).
        Strategy 3: Direct inbox compose (last resort fallback)."""
        if not self.page:
            raise Exception("Browser not initialized.")

        log_to_db("INFO", f"Navigating to profile: https://www.instagram.com/{target_username}/")
        try:
            try:
                await self.page.goto(f"https://www.instagram.com/{target_username}/", wait_until="domcontentloaded", timeout=25000)
            except Exception as goto_err:
                log_to_db("WARNING", f"Navigation to profile timed out or failed, continuing: {str(goto_err)}")
            await asyncio.sleep(random.uniform(3.0, 5.0))

            body_text = await self.page.inner_text("body")
            if "Sorry, this page isn't available" in body_text or "Page Not Found" in body_text:
                raise Exception("Profile not found or page unavailable.")

            dm_ready = False
            strategy1_clicked = False

            # Strategy 1: Click 'Message' button on profile (public / already-following)
            message_button = await self._find_message_button()
            if message_button:
                log_to_db("INFO", "Clicking 'Message' button on profile...")
                await message_button.click()
                strategy1_clicked = True
                await asyncio.sleep(random.uniform(4.0, 6.0))
                await self._dismiss_popups()
                dm_ready = await self._check_dm_input_exists()
                if not dm_ready:
                    log_to_db("WARNING", "Message button clicked but DM input did not appear.")

            # Strategy 2: Three dots menu -> 'Send message' (works for private accounts)
            if not dm_ready:
                if strategy1_clicked:
                    log_to_db("INFO", f"Re-navigating to @{target_username}'s profile for three dots approach...")
                    try:
                        await self.page.goto(f"https://www.instagram.com/{target_username}/", wait_until="domcontentloaded", timeout=25000)
                    except Exception:
                        pass
                    await asyncio.sleep(random.uniform(3.0, 5.0))
                log_to_db("INFO", f"Trying three dots menu -> Send message for @{target_username}...")
                if await self._send_via_three_dots_menu():
                    dm_ready = await self._check_dm_input_exists()

            # Strategy 3: Direct inbox compose (last resort)
            if not dm_ready:
                log_to_db("INFO", f"Falling back to Direct inbox compose for @{target_username}...")
                dm_ready = await self._send_via_direct_inbox(target_username)

            if not dm_ready:
                raise Exception(f"Could not open DM thread with @{target_username} via any method.")

            await self._type_and_send_message(target_username, message)
            return True
        except Exception as e:
            log_to_db("ERROR", f"Failed to send DM to {target_username}: {str(e)}")
            raise e

    async def _find_message_button(self):
        """Finds the Message button on a profile page. Uses exact text match to avoid
        false-matching 'Messages' nav link or 'Send message' menu items."""
        selectors = [
            "//div[text()='Message']",
            "//button[text()='Message']",
            'button:text-is("Message")',
            'div[role="button"]:text-is("Message")',
        ]

        for sel in selectors:
            loc = self.page.locator(sel)
            if await loc.count() > 0:
                for i in range(await loc.count()):
                    item = loc.nth(i)
                    if await item.is_visible():
                        return item
        return None

    async def _check_dm_input_exists(self) -> bool:
        """Quick check (with short wait) whether a DM input field is visible on the page."""
        await self._dismiss_popups()

        dm_selectors = [
            'div[contenteditable="true"][aria-label="Message"]',
            'div[contenteditable="true"][aria-placeholder*="Message"]',
            'div[contenteditable="true"][role="textbox"]',
            'div[role="textbox"]',
            'div[contenteditable="true"]',
            'textarea[placeholder*="Message"]',
            'p[placeholder*="Message"]',
        ]

        # Two quick passes with a short wait between
        for attempt in range(2):
            for sel in dm_selectors:
                loc = self.page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    if await loc.nth(i).is_visible():
                        return True
            if attempt == 0:
                await asyncio.sleep(random.uniform(2.0, 3.0))
                await self._dismiss_popups()

        return False

    async def _send_via_three_dots_menu(self) -> bool:
        """Clicks the three dots (...) menu on a profile page and selects 'Send message'.
        This is the primary method for private accounts."""
        try:
            dots_button = None
            dots_selectors = [
                'svg[aria-label="Options"]',
                'button:has(svg[aria-label="Options"])',
                'div[role="button"]:has(svg[aria-label="Options"])',
                'svg[aria-label="More options"]',
                'button:has(svg[aria-label="More options"])',
                'div[role="button"]:has(svg[aria-label="More options"])',
            ]

            for sel in dots_selectors:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    for i in range(await loc.count()):
                        item = loc.nth(i)
                        if await item.is_visible():
                            dots_button = item
                            break
                if dots_button:
                    break

            if not dots_button:
                log_to_db("WARNING", "Three dots menu button not found on profile.")
                return False

            log_to_db("INFO", "Clicking three dots (...) menu...")
            await dots_button.click()
            await asyncio.sleep(random.uniform(2.0, 3.5))

            send_msg_btn = None
            send_selectors = [
                "//button[text()='Send message']",
                "//button[text()='Send Message']",
                "//div[text()='Send message']",
                "//span[text()='Send message']",
                'button:has-text("Send message")',
                'div[role="button"]:has-text("Send message")',
                'button:has-text("Send Message")',
                'div[role="button"]:has-text("Send Message")',
            ]

            for sel in send_selectors:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    for i in range(await loc.count()):
                        item = loc.nth(i)
                        if await item.is_visible():
                            send_msg_btn = item
                            break
                if send_msg_btn:
                    break

            if not send_msg_btn:
                log_to_db("WARNING", "'Send message' not found in three dots menu.")
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(1.0)
                return False

            log_to_db("INFO", "Clicking 'Send message' from three dots menu...")
            await send_msg_btn.click()
            await asyncio.sleep(random.uniform(4.0, 6.0))
            await self._dismiss_popups()
            return True

        except Exception as e:
            log_to_db("WARNING", f"Three dots menu approach failed: {e}")
            return False

    async def _send_via_direct_inbox(self, target_username: str) -> bool:
        """Navigates to Direct inbox, composes a new message, and searches for the target user.
        This is the most reliable method for private accounts."""
        try:
            # Step 1: Navigate to the direct inbox
            log_to_db("INFO", "Navigating to Direct inbox...")
            try:
                await self.page.goto("https://www.instagram.com/direct/inbox/", wait_until="domcontentloaded", timeout=25000)
            except Exception:
                pass
            await asyncio.sleep(random.uniform(3.0, 5.0))
            await self._dismiss_popups()

            # Step 2: Click the "New message" / compose button (pencil icon)
            compose_btn = None
            compose_selectors = [
                'svg[aria-label="New message"]',
                'div[role="button"]:has(svg[aria-label="New message"])',
                'a[href="/direct/new/"]',
                'svg[aria-label="New Message"]',
                'div[role="button"]:has(svg[aria-label="New Message"])',
                'button:has(svg[aria-label="New message"])',
                'button:has(svg[aria-label="New Message"])',
                # Compose pencil icon - sometimes aria-label differs
                'svg[aria-label="Compose"]',
                'div[role="button"]:has(svg[aria-label="Compose"])',
            ]
            for sel in compose_selectors:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    for i in range(await loc.count()):
                        item = loc.nth(i)
                        if await item.is_visible():
                            compose_btn = item
                            break
                if compose_btn:
                    break

            if compose_btn:
                log_to_db("INFO", "Clicking 'New message' compose button...")
                await compose_btn.click()
                await asyncio.sleep(random.uniform(2.0, 3.0))
            else:
                # Fallback: try navigating directly to /direct/new/
                log_to_db("INFO", "Compose button not found, navigating to /direct/new/ ...")
                try:
                    await self.page.goto("https://www.instagram.com/direct/new/", wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(3.0, 5.0))

            await self._dismiss_popups()

            # Step 3: Find the "To:" / search input field for recipients
            search_input = None
            search_selectors = [
                'input[placeholder="Search..."]',
                'input[placeholder="Search…"]',
                'input[placeholder*="Search"]',
                'input[name="queryBox"]',
                'input[aria-label*="Search"]',
                'input[aria-label*="search"]',
            ]
            for sel in search_selectors:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    for i in range(await loc.count()):
                        item = loc.nth(i)
                        if await item.is_visible():
                            search_input = item
                            break
                if search_input:
                    break

            # If no search input found, try any visible text input in a dialog
            if not search_input:
                dialog_inputs = self.page.locator('div[role="dialog"] input[type="text"]')
                if await dialog_inputs.count() > 0:
                    for i in range(await dialog_inputs.count()):
                        if await dialog_inputs.nth(i).is_visible():
                            search_input = dialog_inputs.nth(i)
                            break

            if not search_input:
                log_to_db("ERROR", "Could not find recipient search input in Direct inbox compose.")
                return False

            # Step 4: Type the username to search
            log_to_db("INFO", f"Searching for @{target_username} in Direct compose...")
            await search_input.click()
            await asyncio.sleep(0.5)
            await search_input.fill("")
            await asyncio.sleep(0.3)
            await human_type(search_input, target_username)
            await asyncio.sleep(random.uniform(3.0, 5.0))

            # Step 5: Click on the matching user from search results
            # Instagram shows results as a list - we need to click the right one
            # The result items typically contain the username in a span and may have a checkbox/radio
            user_clicked = False

            # Try clicking a result item that contains the username text
            result_selectors = [
                f'div[role="dialog"] span:text-is("{target_username}")',
                f'//span[translate(text(),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="{target_username.lower()}"]',
                f'span:text-is("{target_username}")',
            ]

            for sel in result_selectors:
                try:
                    loc = self.page.locator(sel)
                    if await loc.count() > 0:
                        for i in range(await loc.count()):
                            item = loc.nth(i)
                            if await item.is_visible():
                                await item.click()
                                user_clicked = True
                                log_to_db("INFO", f"Selected @{target_username} from search results.")
                                break
                except Exception:
                    continue
                if user_clicked:
                    break

            # Fallback: click a row only when one of its leaf elements is an
            # exact username match. Never click the first or a partial match.
            if not user_clicked:
                log_to_db("INFO", "Looking for an exact username result row...")
                try:
                    result_rows = self.page.locator('div[role="dialog"] div[role="none"], div[role="dialog"] label, div[role="dialog"] div[style*="cursor: pointer"]')
                    if await result_rows.count() > 0:
                        for i in range(await result_rows.count()):
                            row = result_rows.nth(i)
                            leaf_texts = await row.locator('span, div').evaluate_all(
                                "els => els.filter(el => el.children.length === 0).map(el => (el.textContent || '').trim().toLowerCase())"
                            )
                            if target_username.lower() in leaf_texts:
                                await row.click()
                                user_clicked = True
                                log_to_db("INFO", f"Clicked exact result row for @{target_username}.")
                                break
                except Exception as e:
                    log_to_db("WARNING", f"Result row click fallback failed: {e}")

            if not user_clicked:
                log_to_db("ERROR", f"User @{target_username} not found in Direct compose search results.")
                return False

            await asyncio.sleep(random.uniform(1.5, 2.5))

            # Step 6: Click "Chat" or "Next" button to open the conversation
            next_btn = None
            next_selectors = [
                "//div[text()='Chat']",
                "//button[text()='Chat']",
                "//div[text()='Next']",
                "//button[text()='Next']",
                "div[role='button']:has-text('Chat')",
                "div[role='button']:has-text('Next')",
                "div[role='dialog'] div[role='button']:has-text('Chat')",
                "div[role='dialog'] div[role='button']:has-text('Next')",
            ]

            for sel in next_selectors:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    for i in range(await loc.count()):
                        item = loc.nth(i)
                        if await item.is_visible():
                            next_btn = item
                            break
                if next_btn:
                    break

            if next_btn:
                log_to_db("INFO", "Clicking 'Chat'/'Next' to open conversation...")
                await next_btn.click()
                await asyncio.sleep(random.uniform(3.0, 5.0))
            else:
                log_to_db("WARNING", "No 'Chat'/'Next' button found after selecting user, proceeding...")
                await asyncio.sleep(2.0)

            await self._dismiss_popups()

            # Step 7: Confirm DM input is ready
            dm_ready = await self._check_dm_input_exists()
            if dm_ready:
                log_to_db("INFO", "DM input ready via Direct inbox compose.")
                return True

            # Sometimes Instagram shows a "Send message request" confirmation for private accounts
            # Check for and accept any confirmation dialog
            confirm_selectors = [
                'button:has-text("Send message")',
                'button:has-text("Send Message")',
                'div[role="button"]:has-text("Send message")',
                'button:has-text("OK")',
                'button:has-text("Got it")',
            ]
            for sel in confirm_selectors:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    for i in range(await loc.count()):
                        item = loc.nth(i)
                        if await item.is_visible():
                            await item.click()
                            log_to_db("INFO", "Accepted message request confirmation dialog.")
                            await asyncio.sleep(2.0)
                            break
                    break

            dm_ready = await self._check_dm_input_exists()
            if dm_ready:
                return True

            log_to_db("WARNING", "DM input still not found after Direct inbox compose flow.")
            return False

        except Exception as e:
            log_to_db("ERROR", f"Direct inbox compose approach failed: {e}")
            return False

    async def _type_and_send_message(self, target_username: str, message: str):
        """Finds the DM input box, types the message, and sends it."""

        await self._dismiss_popups()

        dm_input_selectors = [
            'div[contenteditable="true"][aria-label="Message"]',
            'div[contenteditable="true"][aria-placeholder*="Message"]',
            'div[contenteditable="true"][role="textbox"]',
            'div[aria-placeholder*="Message"]',
            'div[role="textbox"]',
            'textarea[placeholder*="Message"]',
            'textarea[placeholder*="message"]',
            'p[placeholder*="Message"]',
            'div[contenteditable="true"]',
        ]

        input_box = None
        for attempt in range(6):
            for sel in dm_input_selectors:
                loc = self.page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    item = loc.nth(i)
                    if await item.is_visible():
                        # Avoid matching the "To:" search field in compose dialog
                        aria = await item.get_attribute("aria-label") or ""
                        placeholder = await item.get_attribute("aria-placeholder") or await item.get_attribute("placeholder") or ""
                        tag = await item.evaluate("el => el.tagName.toLowerCase()")
                        if "search" in aria.lower() or "search" in placeholder.lower():
                            continue
                        if tag == "input":
                            continue
                        input_box = item
                        break
                if input_box:
                    break

            if input_box:
                break

            log_to_db("INFO", f"DM input not found yet (attempt {attempt + 1}/6). Dismissing popups and waiting...")
            await self._dismiss_popups()

            # Also try accepting any "message request" prompt
            try:
                for confirm_sel in ['button:has-text("Send message")', 'button:has-text("OK")', 'button:has-text("Got it")']:
                    btn = self.page.locator(confirm_sel)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click()
                        log_to_db("INFO", "Accepted a confirmation prompt while waiting for DM input.")
                        await asyncio.sleep(2.0)
                        break
            except Exception:
                pass

            await asyncio.sleep(random.uniform(2.5, 4.0))

        if not input_box:
            raise Exception("Direct message input field not found.")

        log_to_db("INFO", f"Typing message to {target_username}...")
        await input_box.click()
        await asyncio.sleep(1.0)

        await human_type(input_box, message)
        await asyncio.sleep(random.uniform(1.0, 2.0))

        log_to_db("INFO", "Sending message...")
        await self.page.keyboard.press("Enter")
        await asyncio.sleep(3.0)

        log_to_db("SUCCESS", f"Message successfully sent to {target_username}!")

    async def _dismiss_popups(self):
        """Dismisses common Instagram popups that block interaction (notifications, cookies, etc.)."""
        try:
            # Common dismiss button selectors for Instagram popups
            dismiss_selectors = [
                "//button[text()='Not Now']",
                "//button[text()='Not now']",
                "//button[text()='Cancel']",
                "//button[text()='Dismiss']",
                "//button[text()='Close']",
                "//button[text()='Turn Off']",
                "//button[text()='Maybe Later']",
                "//a[text()='Not Now']",
                "//a[text()='Not now']",
                'button:has-text("Not Now")',
                'button:has-text("Not now")',
                'div[role="button"]:has-text("Not Now")',
                # Close X buttons on dialog overlays
                'div[role="dialog"] button svg[aria-label="Close"]',
                'div[role="dialog"] button:has(svg[aria-label="Close"])',
            ]
            
            for sel in dismiss_selectors:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    for i in range(await loc.count()):
                        item = loc.nth(i)
                        if await item.is_visible():
                            await item.click()
                            log_to_db("INFO", f"Dismissed popup using: {sel}")
                            await asyncio.sleep(1.0)
                            return  # One popup at a time
        except Exception:
            pass  # Silently ignore popup dismissal errors

    async def perform_random_activity(self):
        """Simulates human interaction (scrolling home feed) to reduce bot footprint."""
        if not self.page:
            return
        log_to_db("INFO", "Performing random human-like activity (scrolling home feed)...")
        try:
            await self.page.goto("https://www.instagram.com/", wait_until="load")
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Scroll down slowly
            for _ in range(random.randint(2, 5)):
                scroll_amount = random.randint(300, 700)
                await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                await asyncio.sleep(random.uniform(2.0, 5.0))
        except Exception as e:
            log_to_db("WARNING", f"Failed random activity: {e}")

    async def _scrape_post_comments_legacy(self, post_url: str, trigger_keyword: str, own_username: str = "") -> list:
        """Navigates to post_url, ensures the comment drawer is open, and extracts comments.
        own_username is excluded from results to avoid DMing yourself."""
        if not self.page:
            raise Exception("Browser not initialized.")
        
        log_to_db("INFO", f"Checking comments on post: {post_url}")
        comments_found = []
        try:
            try:
                await self.page.goto(post_url, wait_until="domcontentloaded", timeout=25000)
            except Exception as goto_err:
                log_to_db("WARNING", f"Navigation to post timed out or failed, continuing: {str(goto_err)}")
            await asyncio.sleep(random.uniform(4.0, 6.0))
            
            # Instagram Reels/Posts on Web often hide the comments drawer by default.
            # Let's check if the comments container is open. If not, click the comment button.
            try:
                # Look for comment input box or scrollable comment list container
                comment_input = self.page.locator('textarea[placeholder*="comment"], textarea[placeholder*="Comment"]')
                if await comment_input.count() == 0:
                    # Click the comment drawer button (usually button containing the comment svg icon)
                    comment_btn = self.page.locator('button:has(svg[aria-label="Comment"]), svg[aria-label="Comment"]').first
                    if await comment_btn.is_visible():
                        log_to_db("INFO", "Comments drawer seems closed. Clicking Comment button to open drawer...")
                        await comment_btn.click(force=True)
                        await asyncio.sleep(3.0)
            except Exception as click_err:
                log_to_db("WARNING", f"Could not trigger comment drawer button: {click_err}")
            
            try:
                # Scroll comment area if possible to load more comments
                comment_container = self.page.locator('div[style*="overflow-y: scroll"], ul[role="list"]')
                if await comment_container.count() > 0:
                    await comment_container.first.evaluate("el => el.scrollTop = el.scrollHeight")
                    await asyncio.sleep(2.0)
            except Exception:
                pass
                
            # Run the comment scraper
            raw_comments = await self.page.evaluate("""(ownUser) => {
                const results = [];
                const seen = new Set();
                const navNames = new Set([
                    'instagram','home','search','explore','messages','profile',
                    'notifications','reels','direct','create','threads','accounts',
                    'about','p','reel','stories','tv','tags','tagged','saved',
                    'ar','developer','legal','privacy','safety','blog'
                ]);

                // Strategy 1: Find comments via <article> > <ul> > <li> structure
                const article = document.querySelector('article');
                if (article) {
                    const uls = article.querySelectorAll('ul');
                    for (const ul of uls) {
                        const lis = ul.querySelectorAll(':scope > li');
                        if (lis.length < 1) continue;

                        for (const li of lis) {
                            // Each comment <li> should contain a profile link
                            const links = li.querySelectorAll('a[href^="/"]');
                            let username = '';
                            for (const link of links) {
                                const href = link.getAttribute('href') || '';
                                const parts = href.replace(/^\\//, '').replace(/\\/$/, '').split('/');
                                if (parts.length === 1 && parts[0] && !navNames.has(parts[0].toLowerCase())) {
                                    username = parts[0];
                                    break;
                                }
                            }
                            if (!username) continue;
                            if (ownUser && username.toLowerCase() === ownUser.toLowerCase()) continue;

                            // Get all text spans in this <li>
                            const spans = li.querySelectorAll('span');
                            let commentText = '';
                            for (const span of spans) {
                                if (span.querySelector('span')) continue;
                                const val = (span.textContent || '').trim();
                                if (!val) continue;
                                if (val.toLowerCase() === username.toLowerCase()) continue;
                                if (/^(reply|see translation|verified|follow)$/i.test(val)) continue;
                                if (/view (\\d+ )?repl/i.test(val)) continue;
                                if (/hide repl/i.test(val)) continue;
                                if (/^\\d+[wdhms]$/.test(val)) continue;
                                if (/^\\d+ (likes?|replies?|days?|weeks?|hours?|minutes?)$/i.test(val)) continue;
                                if (/^(liked by|author|edited)$/i.test(val)) continue;
                                if (val.length > 500) continue;
                                commentText = val;
                                break;
                            }

                            if (commentText) {
                                const key = username.toLowerCase() + '::' + commentText.toLowerCase();
                                if (!seen.has(key)) {
                                    seen.add(key);
                                    results.push({ username, commentText });
                                }
                            }
                        }
                    }
                }

                // Strategy 2: If strategy 1 found nothing, try finding any element
                // that has both a profile link and nearby text content
                if (results.length === 0) {
                    const allLinks = document.querySelectorAll('a[href^="/"]');
                    for (const link of allLinks) {
                        const href = link.getAttribute('href') || '';
                        const parts = href.replace(/^\\//, '').replace(/\\/$/, '').split('/');
                        if (parts.length !== 1 || !parts[0]) continue;
                        const username = parts[0];
                        if (navNames.has(username.toLowerCase())) continue;
                        if (ownUser && username.toLowerCase() === ownUser.toLowerCase()) continue;

                        // Walk up to find a reasonable comment container
                        let container = link;
                        for (let depth = 0; depth < 8; depth++) {
                            container = container.parentElement;
                            if (!container) break;
                            const tag = container.tagName.toLowerCase();
                            if (tag === 'li' || tag === 'div') {
                                const text = (container.textContent || '').trim();
                                if (text.length > 20 && text.length < 1000) {
                                    // Check if this looks like a comment (has username + some other text)
                                    const spans = container.querySelectorAll('span');
                                    let commentText = '';
                                    for (const span of spans) {
                                        if (span.querySelector('span')) continue;
                                        const val = (span.textContent || '').trim();
                                        if (!val || val.length < 1) continue;
                                        if (val.toLowerCase() === username.toLowerCase()) continue;
                                        if (/^(reply|see translation|verified|follow)$/i.test(val)) continue;
                                        if (/view (\\d+ )?repl/i.test(val)) continue;
                                        if (/^\\d+[wdhms]$/.test(val)) continue;
                                        if (/^\\d+ (likes?|replies?)$/i.test(val)) continue;
                                        if (val.length > 500) continue;
                                        commentText = val;
                                        break;
                                    }
                                    if (commentText) {
                                        const key = username.toLowerCase() + '::' + commentText.toLowerCase();
                                        if (!seen.has(key)) {
                                            seen.add(key);
                                            results.push({ username, commentText });
                                        }
                                        break;
                                    }
                                }
                            }
                        }
                    }
                }

                return results;
            }""", own_username)
            
            for item in raw_comments:
                uname = item["username"]
                text = item["commentText"]
                if own_username and uname.lower() == own_username.lower():
                    continue
                if trigger_keyword.lower() in text.lower():
                    comments_found.append((uname, text))
                        
            unique_comments = list(set(comments_found))
            log_to_db("INFO", f"Scraped comments. Found {len(unique_comments)} comments matching trigger '{trigger_keyword}'")
            return unique_comments
            
        except Exception as e:
            log_to_db("ERROR", f"Error scraping comments on {post_url}: {str(e)}")
            return []

    async def scrape_post_comments(self, post_url: str, trigger_keyword: str, own_username: str = "",
                                   match_mode: str = MATCH_MODE_EXACT) -> list:
        """Load correctly mapped comment authors/text and apply the match mode.

        Instagram's media API is preferred because each comment object contains
        its own author. The DOM fallback is deliberately strict and returns no
        recipient when a comment container is ambiguous.
        """
        if not self.page:
            raise Exception("Browser not initialized.")

        log_to_db("INFO", f"Checking comments on post: {post_url}")
        try:
            try:
                await self.page.goto(post_url, wait_until="domcontentloaded", timeout=25000)
            except Exception as goto_error:
                log_to_db("WARNING", f"Navigation to post failed, continuing: {goto_error!r}")
            await asyncio.sleep(random.uniform(3.0, 5.0))

            try:
                comment_button = self.page.locator(
                    'button:has(svg[aria-label="Comment"]), svg[aria-label="Comment"]'
                ).first
                if await comment_button.is_visible():
                    await comment_button.click(force=True)
                    await asyncio.sleep(3.0)
            except Exception as drawer_error:
                log_to_db("WARNING", f"Could not open comments drawer: {drawer_error!r}")

            shortcode_match = re.search(r"/(?:p|reel|tv)/([^/?#]+)", post_url)
            shortcode = shortcode_match.group(1) if shortcode_match else ""
            result = {"ok": False, "comments": [], "error": "Post shortcode missing"}

            if shortcode:
                result = await self.page.evaluate("""async (shortcode) => {
                    const headers = {'X-IG-App-ID': '936619743392459'};
                    const comments = [];
                    const seen = new Set();
                    const add = (items) => {
                        for (const item of (items || [])) {
                            const username = item?.user?.username;
                            const commentText = item?.text;
                            if (!username || typeof commentText !== 'string') continue;
                            const key = `${username.toLowerCase()}::${commentText}`;
                            if (seen.has(key)) continue;
                            seen.add(key);
                            const commentPermalink = item?.pk ? `/p/${shortcode}/c/${item.pk}/` : '';
                            comments.push({username, commentText, commentPermalink});
                        }
                    };
                    try {
                        const infoResponse = await fetch(
                            `/api/v1/media/shortcode/${encodeURIComponent(shortcode)}/info/`,
                            {credentials: 'include', headers}
                        );
                        if (!infoResponse.ok) {
                            return {ok: false, comments: [], error: `Media info HTTP ${infoResponse.status}`};
                        }
                        const info = await infoResponse.json();
                        const media = info?.items?.[0];
                        const mediaId = media?.pk || media?.id;
                        if (!mediaId) return {ok: false, comments: [], error: 'Media id missing'};
                        add(media?.preview_comments);

                        let cursor = '';
                        for (let page = 0; page < 3; page++) {
                            const suffix = cursor ? `&min_id=${encodeURIComponent(cursor)}` : '';
                            const response = await fetch(
                                `/api/v1/media/${encodeURIComponent(mediaId)}/comments/?can_support_threading=true&permalink_enabled=false${suffix}`,
                                {credentials: 'include', headers}
                            );
                            if (!response.ok) {
                                if (comments.length) break;
                                return {ok: false, comments: [], error: `Comments HTTP ${response.status}`};
                            }
                            const data = await response.json();
                            add(data?.comments);
                            cursor = data?.next_min_id || '';
                            if (!cursor) break;
                        }
                        return {ok: true, comments, error: ''};
                    } catch (error) {
                        return {ok: false, comments: [], error: String(error)};
                    }
                }""", shortcode)

            raw_comments = result.get("comments", [])
            if result.get("ok"):
                log_to_db("INFO", f"Loaded {len(raw_comments)} mapped comments from Instagram's media API.")
            else:
                log_to_db("WARNING", f"Comments API unavailable; using strict DOM fallback: {result.get('error')}")
                raw_comments = await self.page.evaluate("""() => {
                    const output = [];
                    const seen = new Set();
                    const reserved = new Set(['p', 'reel', 'explore', 'direct', 'accounts']);
                    for (const link of document.querySelectorAll('a[href^="/"]')) {
                        const path = (link.getAttribute('href') || '').replace(/^\//, '').replace(/\/$/, '');
                        const label = (link.textContent || '').trim().replace(/^@/, '');
                        if (!path || path.includes('/') || reserved.has(path.toLowerCase()) ||
                            label.toLowerCase() !== path.toLowerCase()) continue;

                        const username = path;
                        let commentText = '';
                        let commentPermalink = '';
                        let ancestor = link.parentElement;
                        // In Instagram's current DOM the nearest comment body is
                        // a sibling of the author/time header. Only accept a
                        // single text-only sibling; links, times and buttons make
                        // the container ambiguous and therefore unsafe.
                        for (let depth = 0; ancestor && depth < 7; depth++, ancestor = ancestor.parentElement) {
                            const candidates = [...ancestor.children].filter(child =>
                                !child.contains(link) &&
                                !child.querySelector('a[href], time, [role="button"]') &&
                                !(child.getAttribute('role') === 'button')
                            ).map(child => (child.textContent || '').trim()).filter(text =>
                                text && !/^(reply|like|see translation|follow|verified)$/i.test(text)
                            );
                            if (candidates.length === 1) {
                                commentText = candidates[0];
                                const permalink = ancestor.querySelector('a[href*="/c/"]');
                                commentPermalink = permalink?.getAttribute('href') || '';
                                break;
                            }
                        }
                        if (!commentText) continue;
                        const key = `${username.toLowerCase()}::${commentText}`;
                        if (!seen.has(key)) {
                            seen.add(key);
                            output.push({username, commentText, commentPermalink});
                        }
                    }
                    return output;
                }""")

            matched = []
            seen = set()
            for item in raw_comments:
                username = str(item.get("username", "")).strip()
                comment_text = str(item.get("commentText", ""))
                comment_permalink = str(item.get("commentPermalink", "")).strip()
                key = (username.casefold(), comment_text.casefold())
                if key in seen:
                    continue
                seen.add(key)
                if own_username and username.casefold() == own_username.casefold():
                    continue
                if is_valid_instagram_username(username) and comment_matches_trigger(comment_text, trigger_keyword, match_mode):
                    matched.append((username, comment_text, comment_permalink))

            criteria = "any comment" if match_mode == MATCH_MODE_ANY else f"exact trigger '{trigger_keyword}'"
            log_to_db("INFO", f"Found {len(matched)} comments matching {criteria}.")
            return matched
        except Exception as error:
            log_to_db("ERROR", f"Safe comment scrape failed for {post_url}: {type(error).__name__}: {error!r}")
            return []

    async def reply_to_comment(self, comment_permalink: str, username: str) -> bool:
        """Post a public confirmation reply to one exact source comment."""
        if not self.page or not is_valid_instagram_username(username):
            return False
        if not re.fullmatch(r"/(?:p|reel)/[A-Za-z0-9_-]+/c/\d+/?", comment_permalink or ""):
            log_to_db("WARNING", f"Cannot reply to @{username}: safe comment permalink is unavailable.")
            return False

        reply_text = f"@{username} We've sent the link to your DM. Please check your messages."
        try:
            await self.page.goto(
                f"https://www.instagram.com{comment_permalink}",
                wait_until="domcontentloaded",
                timeout=25000,
            )
            await asyncio.sleep(4.0)

            try:
                comment_button = self.page.locator(
                    'button:has(svg[aria-label="Comment"]), svg[aria-label="Comment"]'
                ).first
                if await comment_button.is_visible():
                    await comment_button.click(force=True)
                    await asyncio.sleep(3.0)
            except Exception:
                pass

            reply_clicked = await self.page.evaluate("""(permalink) => {
                const commentId = (permalink.match(/\/c\/(\d+)/) || [])[1];
                const links = [...document.querySelectorAll('a[href]')].filter(link => {
                    const href = link.getAttribute('href') || '';
                    return href === permalink || (commentId && href.includes(`/c/${commentId}/`));
                });
                for (const link of links) {
                    let node = link.parentElement;
                    for (let depth = 0; node && depth < 10; depth++, node = node.parentElement) {
                        const button = [...node.querySelectorAll('[role="button"], button')]
                            .find(item => (item.textContent || '').trim() === 'Reply');
                        if (button) {
                            button.click();
                            return true;
                        }
                    }
                }
                return false;
            }""", comment_permalink)
            if not reply_clicked:
                log_to_db("WARNING", f"Reply control was not found for @{username}.")
                return False
            await asyncio.sleep(1.0)

            input_box = self.page.locator(
                'textarea[placeholder*="comment" i], textarea[aria-label*="comment" i]'
            ).first
            if not await input_box.is_visible():
                log_to_db("WARNING", f"Comment reply input was not found for @{username}.")
                return False
            await input_box.fill(reply_text)

            post_button = self.page.locator(
                'button:text-is("Post"), div[role="button"]:text-is("Post")'
            ).first
            if not await post_button.is_visible():
                log_to_db("WARNING", f"Comment Post button was not found for @{username}.")
                return False
            await post_button.click()
            await asyncio.sleep(2.0)
            log_to_db("SUCCESS", f"Posted DM confirmation reply to @{username}'s source comment.")
            return True
        except Exception as error:
            log_to_db("WARNING", f"Public comment reply failed for @{username}: {type(error).__name__}: {error!r}")
            return False

    # The background worker runner loop
async def bot_worker_loop():
    global BOT_RUNNING
    log_to_db("INFO", "Starting background Bot Worker Loop...")
    
    while BOT_RUNNING:
        db = SessionLocal()
        try:
            # 1. Check if the engine is switched on (system-wide, admin controlled)
            if get_system_setting(db, "status") != "running":
                log_to_db("INFO", "Bot status is not set to 'running' in settings. Stopping loop.")
                BOT_RUNNING = False
                break

            # Fetch connected accounts only for users who have activated their automation
            active_user_ids = [u.id for u in db.query(User).filter(User.automation_active == True).all()]
            if not active_user_ids:
                db.close()
                await asyncio.sleep(10)
                continue

            active_accounts = db.query(Account).filter(
                Account.status == "connected",
                Account.user_id.in_(active_user_ids)
            ).all()
            if not active_accounts:
                db.close()
                await asyncio.sleep(10)
                continue

            bot_action_taken = False

            # Iterate through connected accounts sequentially to avoid resource hogging and IP blocks
            for active_account in active_accounts:
                if not BOT_RUNNING:
                    break

                # 2. Config is per-tenant: limits, pacing and working hours all
                # belong to the account's workspace, never to the whole engine.
                ws_settings = get_workspace_settings(db, active_account.workspace_id)
                daily_limit = max(1, int(ws_settings["daily_limit"]))
                min_delay = max(10, int(ws_settings["min_delay"]))
                max_delay = max(min_delay, int(ws_settings["max_delay"]))

                work_start = ws_settings["working_hours_start"]
                work_end = ws_settings["working_hours_end"]
                if not is_within_working_hours(work_start, work_end):
                    # Say so once per pause, not every 30s tick. Without this the
                    # dashboard reads "running" while nothing happens and there is
                    # no way to tell a paused schedule from a broken worker.
                    if active_account.id not in PAUSED_OUTSIDE_HOURS:
                        PAUSED_OUTSIDE_HOURS.add(active_account.id)
                        log_to_db(
                            "INFO",
                            f"@{active_account.username}: outside working hours "
                            f"({work_start}-{work_end} IST, now {datetime.now(IST):%H:%M}). "
                            f"Paused until the window reopens."
                        )
                    continue
                if active_account.id in PAUSED_OUTSIDE_HOURS:
                    PAUSED_OUTSIDE_HOURS.discard(active_account.id)
                    log_to_db("INFO", f"@{active_account.username}: inside working hours again, resuming.")

                # Official mode is tenant-specific. Never let one customer's
                # Meta connection pause Playwright for every other workspace.
                official_connection = db.query(MetaConnection).filter(
                    MetaConnection.workspace_id == active_account.workspace_id,
                    MetaConnection.status == "connected",
                    MetaConnection.is_active == True,
                ).first()
                if official_connection:
                    continue

                # Parse proxy details
                proxy_config = None
                if active_account.proxy_host and active_account.proxy_port:
                    proxy_config = {
                        "server": f"http://{active_account.proxy_host}:{active_account.proxy_port}"
                    }
                    if active_account.proxy_username and active_account.proxy_password:
                        proxy_config["username"] = active_account.proxy_username
                        proxy_config["password"] = decrypt_secret(active_account.proxy_password)

                # 3. Check today's send count (targets + comments)
                now_ist = datetime.now(IST)
                today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
                sent_targets = db.query(Target).filter(
                    Target.status == "sent", 
                    Target.sent_at >= today_start,
                    Target.account_id == active_account.id
                ).count()
                
                # Fetch monitored posts associated with this account
                active_posts = db.query(MonitoredPost).filter(
                    MonitoredPost.is_active == True,
                    MonitoredPost.account_id == active_account.id
                ).all()
                active_post_ids = [p.id for p in active_posts]

                sent_comments = 0
                if active_post_ids:
                    sent_comments = db.query(ProcessedComment).filter(
                        ProcessedComment.status == "sent", 
                        ProcessedComment.processed_at >= today_start,
                        ProcessedComment.post_id.in_(active_post_ids)
                    ).count()
                
                total_sent_today = sent_targets + sent_comments
                if total_sent_today >= daily_limit:
                    log_to_db("WARNING", f"Daily sending limit reached for @{active_account.username} ({total_sent_today}/{daily_limit}). Skipping...")
                    continue

                account_action_taken = False

                # --- Phase A: Comment-to-DM Trigger Checks ---
                if active_posts:
                    bot = InstagramBot(active_account.username, proxy=proxy_config)
                    try:
                        await bot.init_browser(headless=settings.HEADLESS)
                        logged_in = await bot.check_login_status()
                        if not logged_in:
                            is_login_page = False
                            try:
                                current_url = bot.page.url if bot.page else ""
                                is_login_page = "accounts/login" in current_url or (bot.page and await bot.page.locator('input[name="username"]').is_visible())
                            except Exception:
                                pass
                            
                            if is_login_page:
                                log_to_db("ERROR", f"Account {active_account.username} requires re-authentication (login page detected).")
                                active_account.status = "verification_needed"
                                db.commit()
                            else:
                                log_to_db("WARNING", f"Login verification check failed for {active_account.username} (transient timeout).")
                                
                            await bot.close_browser()
                            continue
                            
                        for post in active_posts:
                            comments = await bot.scrape_post_comments(
                                post.post_url, post.trigger_keyword,
                                own_username=active_account.username,
                                match_mode=getattr(post, "match_mode", MATCH_MODE_EXACT),
                            )
                            log_to_db("INFO", f"Scraped trigger comments for @{active_account.username} on post {post.id}: {comments}")
                            
                            for username, comment_text, comment_permalink in comments:
                                if not BOT_RUNNING:
                                    break
                                if not is_valid_instagram_username(username) or not comment_matches_trigger(
                                    comment_text, post.trigger_keyword, getattr(post, "match_mode", MATCH_MODE_EXACT)
                                ):
                                    log_to_db("ERROR", f"[SAFETY] Refused invalid or mismatched comment recipient @{username}.")
                                    continue
                                
                                # 1. Opt-out keyword check (this tenant's word list)
                                opt_out_keywords = [
                                    k.strip().lower()
                                    for k in ws_settings["opt_out_keywords"].split(",")
                                    if k.strip()
                                ]
                                if comment_text.strip().lower() in opt_out_keywords:
                                    exists = db.query(OptOut).filter(
                                        OptOut.username == username.lower(),
                                        OptOut.user_id == active_account.user_id,
                                        OptOut.workspace_id == active_account.workspace_id
                                    ).first()
                                    if not exists:
                                        db.add(OptOut(username=username.lower(), user_id=active_account.user_id, workspace_id=active_account.workspace_id))
                                        db.commit()
                                        log_to_db("WARNING", f"[COMPLIANCE] Auto-blocked @{username} due to unsubscribe comment.")
                                    continue

                                # 2. Blocklist check
                                blocked = db.query(OptOut).filter(
                                    OptOut.username == username.lower(),
                                    OptOut.user_id == active_account.user_id,
                                    OptOut.workspace_id == active_account.workspace_id
                                ).first()
                                if blocked:
                                    log_to_db("WARNING", f"[COMPLIANCE] Ignored trigger comment: @{username} is in the blocklist.")
                                    continue

                                # Check if already processed
                                existing = db.query(ProcessedComment).filter(
                                    ProcessedComment.username == username,
                                    ProcessedComment.post_id == post.id
                                ).first()
                                
                                if existing and existing.status == "sent":
                                    continue
                                
                                if existing and existing.status == "failed":
                                    log_to_db("INFO", f"Retrying failed DM to @{username}...")
                                    db.delete(existing)
                                    db.commit()
                                
                                log_to_db("INFO", f"New trigger comment detected from @{username}. Preparing DM outreach...")
                                raw_msg = post.template.content
                                replaced_msg = raw_msg.replace("@username", f"@{username}").replace("{username}", username)
                                parsed_message = parse_spintax(replaced_msg)
                                
                                try:
                                    if bot.page is None or bot.page.is_closed():
                                        await bot.close_browser()
                                        await bot.init_browser(headless=settings.HEADLESS)
                                        logged_in = await bot.check_login_status()
                                        if not logged_in:
                                            raise Exception("Re-login failed after page crash.")
                                    
                                    success = await bot.send_direct_message(username, parsed_message)
                                    if success:
                                        db.add(ProcessedComment(
                                            username=username,
                                            post_id=post.id,
                                            comment_text=comment_text,
                                            status="sent",
                                            processed_at=datetime.utcnow()
                                        ))
                                        log_to_db("SUCCESS", f"Sent trigger comment DM to @{username} from @{active_account.username}")
                                        await bot.reply_to_comment(comment_permalink, username)
                                    else:
                                        raise Exception("DM delivery routine returned False.")
                                except Exception as dm_err:
                                    db.add(ProcessedComment(
                                        username=username,
                                        post_id=post.id,
                                        comment_text=comment_text,
                                        status="failed",
                                        processed_at=datetime.utcnow()
                                    ))
                                    log_to_db("ERROR", f"Comment DM failed to @{username}: {dm_err}")
                                
                                db.commit()
                                account_action_taken = True
                                bot_action_taken = True
                                
                                # human delay spacer
                                delay = random.randint(min_delay, max_delay)
                                log_to_db("INFO", f"Sleeping for {delay} seconds between comment triggers...")
                                for _ in range(delay):
                                    if not BOT_RUNNING:
                                        break
                                    await asyncio.sleep(1)
                                        
                        await bot.close_browser()
                    except Exception as loop_err:
                        log_to_db("ERROR", f"Scraper logic failed for @{active_account.username}: {type(loop_err).__name__}: {loop_err!r}")
                        await bot.close_browser()

                # --- Phase B: Standard Queue Checks ---
                if not account_action_taken and BOT_RUNNING:
                    next_target = db.query(Target).filter(
                        Target.status == "pending",
                        Target.account_id == active_account.id
                    ).first()
                    
                    if next_target:
                        # Blocklist check
                        blocked = db.query(OptOut).filter(
                            OptOut.username == next_target.username.lower(),
                            OptOut.user_id == active_account.user_id,
                            OptOut.workspace_id == active_account.workspace_id
                        ).first()
                        if blocked:
                            log_to_db("WARNING", f"[COMPLIANCE] Skipping target queue: @{next_target.username} has opted out.")
                            next_target.status = "failed"
                            next_target.error_message = "Blocked: User has opted out / unsubscribed."
                            db.commit()
                            continue
                            
                        # Select template
                        templates = db.query(MessageTemplate).filter(
                            MessageTemplate.is_active == True,
                            MessageTemplate.user_id == active_account.user_id,
                            MessageTemplate.workspace_id == active_account.workspace_id
                        ).all()
                        
                        if templates:
                            selected_template = random.choice(templates)
                            raw_msg = selected_template.content
                            replaced_msg = raw_msg.replace("@username", f"@{next_target.username}").replace("{username}", next_target.username)
                            parsed_message = parse_spintax(replaced_msg)
                            
                            next_target.status = "sending"
                            db.commit()
                            
                            bot = InstagramBot(active_account.username, proxy=proxy_config)
                            await bot.init_browser(headless=settings.HEADLESS)
                            
                            try:
                                logged_in = await bot.check_login_status()
                                if logged_in:
                                    success = await bot.send_direct_message(next_target.username, parsed_message)
                                    if success:
                                        next_target.status = "sent"
                                        next_target.sent_at = datetime.utcnow()
                                        next_target.message_sent = parsed_message
                                        next_target.error_message = None
                                        log_to_db("SUCCESS", f"Successfully completed DM task for @{next_target.username} via @{active_account.username}")
                                    else:
                                        raise Exception("Direct message dispatch failed.")
                                        
                                    await bot.perform_random_activity()
                                else:
                                    is_login_page = False
                                    try:
                                        current_url = bot.page.url if bot.page else ""
                                        is_login_page = "accounts/login" in current_url or (bot.page and await bot.page.locator('input[name="username"]').is_visible())
                                    except Exception:
                                        pass
                                    
                                    if is_login_page:
                                        log_to_db("ERROR", f"Account {active_account.username} requires re-authentication.")
                                        active_account.status = "verification_needed"
                                    else:
                                        log_to_db("WARNING", f"Login verification check failed for {active_account.username}.")
                                    next_target.status = "pending"
                            except Exception as queue_err:
                                log_to_db("ERROR", f"Queue action failed: {queue_err}")
                                next_target.status = "failed"
                                next_target.error_message = str(queue_err)
                                next_target.sent_at = datetime.utcnow()
                            finally:
                                db.commit()
                                await bot.close_browser()
                                
                            bot_action_taken = True
                            
                            # human delay spacer
                            delay = random.randint(min_delay, max_delay)
                            log_to_db("INFO", f"Sleeping for {delay} seconds between target queue sends...")
                            for _ in range(delay):
                                if not BOT_RUNNING:
                                    break
                                await asyncio.sleep(1)
                        else:
                            log_to_db("ERROR", f"No active message templates found for user {active_account.user_id}. Create one first.")
            
            # If all accounts were idle, sleep for a short bit
            if not bot_action_taken and BOT_RUNNING:
                await asyncio.sleep(30)

        except Exception as e:
            log_to_db("ERROR", f"Bot execution loop encountered an error: {type(e).__name__}: {e!r}")
            await asyncio.sleep(10)
        finally:
            db.close()
            
    log_to_db("INFO", "Bot Worker Loop has shut down.")

def start_bot_background():
    """Starts the bot loop in a separate thread."""
    global BOT_RUNNING, BOT_THREAD, BOT_LOOP
    if BOT_RUNNING or (BOT_THREAD and BOT_THREAD.is_alive()):
        return False
        
    db = SessionLocal()
    try:
        set_system_setting(db, "status", "running")
        db.commit()
    finally:
        db.close()
        
    BOT_RUNNING = True
    
    def run_async_loop():
        global BOT_LOOP
        BOT_LOOP = create_browser_event_loop()
        asyncio.set_event_loop(BOT_LOOP)
        BOT_LOOP.run_until_complete(bot_worker_loop())
        BOT_LOOP.close()
        
    BOT_THREAD = threading.Thread(target=run_async_loop, daemon=True)
    BOT_THREAD.start()
    return True

def stop_bot_background(persist: bool = True):
    """Signal the bot loop to stop.

    `persist` records the stop as the administrator's decision. A process
    shutting down must pass persist=False: the stored status is the operator's
    intent, and a restart or crash is not an instruction to stay off.
    """
    global BOT_RUNNING, BOT_LOOP
    if not BOT_RUNNING:
        return False

    BOT_RUNNING = False

    if not persist:
        return True

    try:
        db = SessionLocal()
        try:
            set_system_setting(db, "status", "stopped")
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[WARNING] DB update during stop failed (bot still stopped): {e}")

    return True
