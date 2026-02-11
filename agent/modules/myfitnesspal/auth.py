"""Selenium-based authentication for MyFitnessPal.

Uses headless Chrome to perform the MFP login flow (which requires
captcha/JS that prevents direct HTTP auth), captures session cookies,
and caches them to a JSON file for reuse across restarts.

Based on the approach from:
https://github.com/coddingtonbear/python-myfitnesspal/issues/144
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
POST_LOGIN_INDICATOR = "/food/diary"


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


def _dismiss_consent_overlay(driver) -> None:
    """Attempt to dismiss the SP Consent / privacy overlay.

    Tries multiple strategies:
    1. Switch into the iframe and click accept/OK buttons
    2. If that fails, remove the overlay elements via JavaScript
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    # Strategy 1: find the consent iframe and click accept inside it
    try:
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "iframe[id^='sp_message_iframe']")
            )
        )
        logger.info("mfp_consent_iframe_found", iframe_id=iframe.get_attribute("id"))
        driver.switch_to.frame(iframe)

        # Try multiple button selectors — MFP uses different labels
        accept_selectors = [
            "button[title='ACCEPT']",
            "button[title='Accept']",
            "button[title='Accept All']",
            "button[title='ACCEPT ALL']",
            "button[title='OK']",
            "button.pm-btn-accept",
            # Fallback: any prominent button in the consent dialog
            "button[aria-label*='accept' i]",
            "button[aria-label*='Accept' i]",
        ]
        clicked = False
        for selector in accept_selectors:
            try:
                btn = WebDriverWait(driver, 3).until(
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
        driver.switch_to.default_content()
        logger.debug("mfp_consent_iframe_strategy_failed", error=str(e))

    # Strategy 2: nuke the overlay via JavaScript
    removed = driver.execute_script("""
        let removed = 0;
        // Remove SP consent iframes
        document.querySelectorAll('iframe[id^="sp_message_iframe"]').forEach(el => {
            el.remove(); removed++;
        });
        // Remove SP message containers / overlays
        document.querySelectorAll('[class*="sp_message"], [id*="sp_message"]').forEach(el => {
            el.remove(); removed++;
        });
        // Remove any full-screen overlay divs that block clicks
        document.querySelectorAll('.message-overlay, .overlay').forEach(el => {
            el.remove(); removed++;
        });
        return removed;
    """)
    logger.info("mfp_consent_js_removed", elements_removed=removed)
    time.sleep(0.5)


def _selenium_login(username: str, password: str) -> list[dict]:
    """Perform headless Chrome login to MyFitnessPal and return cookies.

    Raises RuntimeError on failure.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.binary_location = "/usr/bin/chromium"

    service = Service(executable_path="/usr/bin/chromedriver")

    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)

        logger.info("mfp_selenium_navigating", url=LOGIN_URL)
        driver.get(LOGIN_URL)

        wait = WebDriverWait(driver, 30)

        # Dismiss consent / privacy overlay
        _dismiss_consent_overlay(driver)

        # Fill login form
        email_input = wait.until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        password_input = driver.find_element(By.NAME, "password")

        email_input.clear()
        email_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)

        logger.info("mfp_selenium_credentials_entered")

        # Click submit — try normal click first, JS click as fallback
        submit = driver.find_element(By.XPATH, "//button[@type='submit']")
        try:
            submit.click()
        except Exception:
            # Overlay may have reappeared — remove it and use JS click
            logger.warning("mfp_selenium_submit_intercepted_retrying")
            _dismiss_consent_overlay(driver)
            driver.execute_script("arguments[0].click();", submit)

        logger.info("mfp_selenium_login_submitted")

        # Wait for redirect away from login page (indicates success)
        def login_complete(drv):
            return "/account/login" not in drv.current_url

        WebDriverWait(driver, 30).until(login_complete)

        # Give the page a moment to settle and set all cookies
        time.sleep(3)

        cookies = driver.get_cookies()
        if not cookies:
            raise RuntimeError("Selenium login succeeded but no cookies captured")

        logger.info(
            "mfp_selenium_login_success",
            url=driver.current_url,
            cookie_count=len(cookies),
        )
        return cookies

    except Exception as exc:
        logger.error("mfp_selenium_login_failed", error=str(exc))
        raise RuntimeError(f"MyFitnessPal Selenium login failed: {exc}") from exc
    finally:
        if driver:
            driver.quit()


def get_cookiejar(
    username: str,
    password: str,
    force_refresh: bool = False,
) -> RequestsCookieJar:
    """Get an authenticated MFP cookie jar.

    Priority:
    1. Load cached cookies from disk (unless force_refresh)
    2. Perform Selenium login and cache the result
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

    cookies = _selenium_login(username, password)
    _save_cookies(cookies)
    return _cookies_to_jar(cookies)


def clear_cached_cookies(path: str = COOKIE_FILE) -> None:
    """Remove cached cookie file so next call triggers fresh login."""
    if os.path.exists(path):
        os.remove(path)
        logger.info("mfp_cookies_cleared", path=path)
