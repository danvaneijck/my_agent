"""SeleniumBase UC Mode authentication for MyFitnessPal.

Uses SeleniumBase in Undetected ChromeDriver mode with Xvfb (virtual
display) to bypass Cloudflare Turnstile on the MFP login page.

UC Mode disconnects ChromeDriver during page loads and clicks, making
the browser invisible to Cloudflare's bot detection.  The
uc_gui_click_captcha() method handles the Turnstile checkbox via
pyautogui on the virtual display.

Cookies are cached to disk for reuse across restarts.
"""

from __future__ import annotations

import json
import os
import time

import requests
import structlog
from requests.cookies import RequestsCookieJar

logger = structlog.get_logger()

COOKIE_FILE = "/app/.mfp_cookies.json"
LOGIN_URL = "https://www.myfitnesspal.com/account/login"


def _cookies_to_jar(cookies: list[dict]) -> RequestsCookieJar:
    """Convert a list of Selenium cookie dicts into a RequestsCookieJar."""
    session = requests.Session()
    for c in cookies:
        session.cookies.set(
            name=c["name"],
            value=c["value"],
            domain=c.get("domain", ".myfitnesspal.com"),
            path=c.get("path", "/"),
        )
    return session.cookies


def _save_cookies(cookies: list[dict], path: str = COOKIE_FILE) -> None:
    """Persist raw cookie dicts to disk."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cookies, f)
    logger.info("mfp_cookies_saved", path=path, count=len(cookies))


def _load_cookies(path: str = COOKIE_FILE) -> list[dict] | None:
    """Load cached cookies from disk, or None if missing/invalid."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            cookies = json.loads(f.read())
        if not isinstance(cookies, list) or len(cookies) == 0:
            return None
        logger.info("mfp_cookies_loaded", path=path, count=len(cookies))
        return cookies
    except Exception:
        logger.warning("mfp_cookies_load_failed", path=path)
        return None


def _dismiss_consent_overlay(sb) -> None:
    """Dismiss the SP Consent / privacy overlay if present.

    Uses SeleniumBase driver methods.  Tries clicking inside the iframe
    first, then falls back to removing elements via JS.
    """
    driver = sb.driver

    # Strategy 1: find the consent iframe and click accept inside it
    try:
        if sb.is_element_present("iframe[id^='sp_message_iframe']"):
            iframe_el = driver.find_element("css selector", "iframe[id^='sp_message_iframe']")
            logger.info("mfp_consent_iframe_found", iframe_id=iframe_el.get_attribute("id"))
            driver.switch_to.frame(iframe_el)

            accept_selectors = [
                "button[title='OK']",
                "button[title='ACCEPT']",
                "button[title='Accept All']",
                "button[title='ACCEPT ALL']",
                "button.pm-btn-accept",
            ]
            clicked = False
            for selector in accept_selectors:
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support import expected_conditions as EC
                    from selenium.webdriver.support.ui import WebDriverWait

                    btn = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    btn.click()
                    clicked = True
                    logger.info("mfp_consent_accepted", selector=selector)
                    break
                except Exception:
                    continue

            driver.switch_to.default_content()

            if clicked:
                time.sleep(1)
                return

            logger.warning("mfp_consent_no_button_matched")
    except Exception as e:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        logger.debug("mfp_consent_iframe_strategy_failed", error=str(e))

    # Strategy 2: nuke the overlay via JavaScript
    try:
        removed = driver.execute_script("""
            let removed = 0;
            document.querySelectorAll('iframe[id^="sp_message_iframe"]').forEach(el => {
                el.remove(); removed++;
            });
            document.querySelectorAll('[class*="sp_message"], [id*="sp_message"]').forEach(el => {
                el.remove(); removed++;
            });
            document.querySelectorAll('.message-overlay, .overlay').forEach(el => {
                el.remove(); removed++;
            });
            return removed;
        """)
        logger.info("mfp_consent_js_removed", elements_removed=removed)
    except Exception:
        pass
    time.sleep(0.5)


def _seleniumbase_login(username: str, password: str) -> list[dict]:
    """Login to MyFitnessPal using SeleniumBase UC Mode.

    UC Mode (Undetected ChromeDriver) + Xvfb bypasses Cloudflare
    Turnstile by:
    - Disconnecting ChromeDriver during page loads (invisible to CF)
    - Using uc_gui_click_captcha() to click the Turnstile checkbox
      via pyautogui on the Xvfb virtual display

    Returns a list of cookie dicts on success.
    Raises RuntimeError on failure.
    """
    from seleniumbase import SB

    logger.info("mfp_uc_login_starting", url=LOGIN_URL)

    try:
        with SB(
            uc=True,
            xvfb=True,
            chromium_arg="--no-sandbox,--disable-dev-shm-usage",
            binary_location="/usr/bin/chromium",
        ) as sb:
            # Navigate using UC Mode (driver disconnected during load)
            sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=4)
            logger.info("mfp_uc_page_loaded", url=sb.get_current_url())

            # Handle Cloudflare Turnstile if it appears
            try:
                sb.uc_gui_click_captcha()
                logger.info("mfp_uc_captcha_handled")
            except Exception as e:
                logger.debug("mfp_uc_no_captcha_or_already_passed", note=str(e))

            time.sleep(2)

            # If Cloudflare redirected us to a challenge page, check and retry
            current = sb.get_current_url()
            if "/account/login" not in current:
                # CF might have redirected to a challenge — wait and check
                logger.info("mfp_uc_post_captcha_url", url=current)
                time.sleep(3)
                if "/account/login" not in sb.get_current_url():
                    # Navigate explicitly to login after clearing CF
                    sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=3)
                    time.sleep(2)

            # Dismiss privacy/consent overlay
            _dismiss_consent_overlay(sb)

            # Fill login form
            sb.wait_for_element('input[name="email"]', timeout=15)
            sb.type('input[name="email"]', username)
            sb.type('input[name="password"]', password)
            logger.info("mfp_uc_credentials_entered")

            # Submit the form
            sb.click('button[type="submit"]')
            logger.info("mfp_uc_login_submitted")

            # Wait for the page to respond
            time.sleep(5)

            # Check for error messages
            driver = sb.driver
            page_state = driver.execute_script("""
                const state = {};
                const alerts = document.querySelectorAll(
                    '[role="alert"], .MuiAlert-root, .MuiAlert-message'
                );
                state.error_messages = [];
                alerts.forEach(el => {
                    const text = el.textContent.trim();
                    if (text && text.length < 500) state.error_messages.push(text);
                });
                state.url = window.location.href;
                return state;
            """)
            logger.info("mfp_uc_post_submit_state", **page_state)

            if page_state.get("error_messages"):
                errors = "; ".join(page_state["error_messages"][:3])
                raise RuntimeError(f"MyFitnessPal login error: {errors}")

            # Wait for redirect away from login page
            timeout_end = time.time() + 25
            while time.time() < timeout_end:
                current_url = sb.get_current_url()
                if "/account/login" not in current_url:
                    break
                time.sleep(1)
            else:
                # Last resort diagnostics
                body_text = ""
                try:
                    body_text = driver.execute_script(
                        "return document.body ? document.body.innerText.substring(0, 500) : '';"
                    )
                except Exception:
                    pass
                try:
                    driver.save_screenshot("/app/.mfp_debug_screenshot.png")
                    logger.info("mfp_debug_screenshot_saved")
                except Exception:
                    pass
                raise RuntimeError(
                    f"Login did not redirect within 25s. "
                    f"Visible text: {body_text[:300]}"
                )

            # Let cookies settle
            time.sleep(3)

            cookies = driver.get_cookies()
            if not cookies:
                raise RuntimeError("Login succeeded but no cookies captured")

            logger.info(
                "mfp_uc_login_success",
                url=sb.get_current_url(),
                cookie_count=len(cookies),
            )
            return cookies

    except Exception as exc:
        logger.error("mfp_uc_login_failed", error=str(exc))
        raise RuntimeError(f"MyFitnessPal UC Mode login failed: {exc}") from exc


def get_cookiejar(
    username: str,
    password: str,
    force_refresh: bool = False,
) -> RequestsCookieJar:
    """Get an authenticated MFP cookie jar.

    Priority:
    1. Load cached cookies from disk (unless force_refresh)
    2. Perform SeleniumBase UC Mode login and cache the result
    """

    if not force_refresh:
        cached = _load_cookies()
        if cached:
            return _cookies_to_jar(cached)

    if not username or not password:
        raise RuntimeError(
            "MyFitnessPal credentials not configured. "
            "Set MFP_USERNAME and MFP_PASSWORD in .env."
        )

    cookies = _seleniumbase_login(username, password)
    _save_cookies(cookies)
    return _cookies_to_jar(cookies)


def clear_cached_cookies(path: str = COOKIE_FILE) -> None:
    """Remove cached cookie file so next call triggers fresh login."""
    if os.path.exists(path):
        os.remove(path)
        logger.info("mfp_cookies_cleared", path=path)
