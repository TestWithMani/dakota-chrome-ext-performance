"""
Dakota Marketplace login flow.

Correct order:
  1. Log in on the Dakota website (portal) with username + password
  2. Open the extension sidebar on that same page
  3. Click "Log in with Salesforce" — SSO auto-authenticates (no popup credentials)

Portal: https://dakotanetworks.my.site.com/dakotaMarketplace/s/
"""

import time
from dataclasses import dataclass

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.allure_helpers import allure_step, attach_page_info, attach_screenshot

# Dakota portal — log in here FIRST before using the extension
DAKOTA_PORTAL_URL = "https://dakotanetworks.my.site.com/dakotaMarketplace/s/"

# Salesforce login form on the Dakota website (same XPaths as the SSO popup)
LOGIN_EMAIL_XPATH = "//input[@id='loginPage:loginForm:login-email']"
LOGIN_PASSWORD_XPATH = "//input[@id='loginPage:loginForm:login-password']"
LOGIN_SUBMIT_XPATH = "//input[@id='loginPage:loginForm:login-submit']"

# Dakota extension UI inside Shadow DOM
FLOATING_BUTTON_CSS = ".dakota-floating-button"
SALESFORCE_SIGNIN_BUTTON_CSS = ".dakota-salesforce-signin-button"
LOGGED_IN_SEARCH_CSS = "#company-search"
SIDEBAR_OPEN_CSS = ".dakota-sidebar-container.open"
SIDEBAR_CLOSE_BUTTON_CSS = ".dakota-loggedin-header-button, .dakota-signin-close-button"
EXTENSION_LOADING_CSS = ".dakota-loading, .dakota-signin-loading, .dakota-loading-text"

DEFAULT_TIMEOUT = 60
PORTAL_LOGIN_TIMEOUT = 60
EXTENSION_SSO_TIMEOUT = 60
EXTENSION_FINAL_DELAY_SECONDS = 5
POST_LOGIN_STABILIZE_SEC = 1.5


@dataclass(frozen=True)
class DakotaCredentials:
    username: str
    password: str


class PortalLoginError(TimeoutException):
    """Raised when the portal rejects credentials or shows a login error."""


def _shadow_root_script(prefix: str = "") -> str:
    return f"""
        const host = document.getElementById('crxjs-app');
        const root = host?.shadowRoot;
        {prefix}
    """


def _portal_login_error_visible(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.execute_script(
            """
            const text = (document.body?.innerText || '').toLowerCase();
            return text.includes('please check your username')
                || text.includes('check your username/email')
                || text.includes('invalid username')
                || text.includes('invalid password');
            """
        )
    )


def _is_portal_home_url(url: str) -> bool:
    return "/dakotaMarketplace/s/" in url and "SigninUI" not in url and "CommunitiesLogin" not in url


def _extension_search_ready(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.execute_script(
            f"""
            {_shadow_root_script()}
            if (!root) return false;
            const signin = root.querySelector('{SALESFORCE_SIGNIN_BUTTON_CSS}');
            const search = root.querySelector('{LOGGED_IN_SEARCH_CSS}');
            const loading = root.querySelector('{EXTENSION_LOADING_CSS}');
            if (loading && loading.offsetParent !== null) return false;
            if (signin && signin.offsetParent !== null) return false;
            if (!search || search.disabled) return false;
            const style = window.getComputedStyle(search);
            return style.display !== 'none' && style.visibility !== 'hidden';
            """
        )
    )


def _extension_host_ready(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.execute_script(
            """
            const host = document.getElementById('crxjs-app');
            return !!(host && host.shadowRoot);
            """
        )
    )


def _floating_button_ready(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.execute_script(
            f"""
            {_shadow_root_script()}
            if (!root) return false;
            const btn = root.querySelector('{FLOATING_BUTTON_CSS}');
            if (!btn) return false;
            const style = window.getComputedStyle(btn);
            return style.display !== 'none' && style.visibility !== 'hidden';
            """
        )
    )


def _sso_clicked_and_pending(driver: webdriver.Chrome) -> bool:
    """True while SSO is still in progress after clicking sign-in."""
    return bool(
        driver.execute_script(
            f"""
            {_shadow_root_script()}
            if (!root) return false;
            const signin = root.querySelector('{SALESFORCE_SIGNIN_BUTTON_CSS}');
            const search = root.querySelector('{LOGGED_IN_SEARCH_CSS}');
            const loading = root.querySelector('{EXTENSION_LOADING_CSS}');
            if (search && !search.disabled) return false;
            if (loading && loading.offsetParent !== null) return true;
            if (signin && signin.offsetParent !== null) return true;
            return false;
            """
        )
    )


def click_shadow_button(driver: webdriver.Chrome, css_selector: str) -> None:
    """Click an element inside Dakota's Shadow DOM."""
    clicked = driver.execute_script(
        """
        const host = document.getElementById('crxjs-app');
        if (!host || !host.shadowRoot) return false;
        const el = host.shadowRoot.querySelector(arguments[0]);
        if (!el) return false;
        el.click();
        return true;
        """,
        css_selector,
    )
    if not clicked:
        raise TimeoutException(f"Could not find or click Shadow DOM element: {css_selector}")


def is_sidebar_open(driver: webdriver.Chrome) -> bool:
    """True when the Dakota sidebar is visible."""
    return driver.execute_script(
        f"""
        const host = document.getElementById('crxjs-app');
        return !!host?.shadowRoot?.querySelector('{SIDEBAR_OPEN_CSS}');
        """
    )


def wait_for_portal_login_form(driver: webdriver.Chrome, timeout: int = PORTAL_LOGIN_TIMEOUT) -> None:
    """Wait until the Dakota portal login form is ready for input."""
    wait = WebDriverWait(driver, timeout)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    wait.until(EC.visibility_of_element_located((By.XPATH, LOGIN_EMAIL_XPATH)))
    wait.until(EC.element_to_be_clickable((By.XPATH, LOGIN_EMAIL_XPATH)))
    wait.until(EC.element_to_be_clickable((By.XPATH, LOGIN_PASSWORD_XPATH)))
    wait.until(EC.element_to_be_clickable((By.XPATH, LOGIN_SUBMIT_XPATH)))


def open_dakota_sidebar(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Click the floating button to open the extension sidebar."""
    if is_sidebar_open(driver):
        return
    WebDriverWait(driver, timeout).until(lambda d: _floating_button_ready(d))
    click_shadow_button(driver, FLOATING_BUTTON_CSS)
    WebDriverWait(driver, timeout).until(lambda d: is_sidebar_open(d))


def click_extension_login_button(driver: webdriver.Chrome, timeout: int = EXTENSION_SSO_TIMEOUT) -> None:
    """Click 'Log in with Salesforce' in the extension (.dakota-salesforce-signin-button)."""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(
            f"""
            {_shadow_root_script()}
            if (!root) return false;
            const btn = root.querySelector('{SALESFORCE_SIGNIN_BUTTON_CSS}');
            if (!btn) return false;
            const style = window.getComputedStyle(btn);
            return style.display !== 'none' && style.visibility !== 'hidden';
            """
        )
    )
    click_shadow_button(driver, SALESFORCE_SIGNIN_BUTTON_CSS)


def fill_portal_login_form(
    driver: webdriver.Chrome,
    credentials: DakotaCredentials,
    timeout: int = PORTAL_LOGIN_TIMEOUT,
) -> None:
    """Enter username and password on the Dakota website login page."""
    wait_for_portal_login_form(driver, timeout=timeout)
    wait = WebDriverWait(driver, timeout)

    email_input = wait.until(EC.element_to_be_clickable((By.XPATH, LOGIN_EMAIL_XPATH)))
    password_input = wait.until(EC.element_to_be_clickable((By.XPATH, LOGIN_PASSWORD_XPATH)))
    submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, LOGIN_SUBMIT_XPATH)))

    email_input.clear()
    email_input.send_keys(credentials.username)
    password_input.clear()
    password_input.send_keys(credentials.password)
    submit_button.click()


def wait_for_portal_logged_in(driver: webdriver.Chrome, timeout: int = PORTAL_LOGIN_TIMEOUT) -> None:
    """Wait until the Dakota portal home page loads after website login."""
    end = time.monotonic() + timeout

    def _portal_ready(_driver: webdriver.Chrome) -> bool:
        if _portal_login_error_visible(_driver):
            raise PortalLoginError(
                "Portal login failed — invalid username or password. "
                "Check DAKOTA_USERNAME / DAKOTA_PASSWORD."
            )
        if not _is_portal_home_url(_driver.current_url):
            return False
        if _driver.execute_script("return document.readyState") != "complete":
            return False
        return True

    WebDriverWait(driver, timeout).until(_portal_ready)

    # Give Salesforce community shell a moment to finish client-side routing.
    stabilize_deadline = min(time.monotonic() + POST_LOGIN_STABILIZE_SEC, end)
    while time.monotonic() < stabilize_deadline:
        if _portal_login_error_visible(driver):
            raise PortalLoginError("Portal login failed after redirect.")
        if not _is_portal_home_url(driver.current_url):
            time.sleep(0.25)
            continue
        break

    wait_for_extension_on_page(driver, timeout=max(int(end - time.monotonic()), 5))


def wait_for_extension_logged_in(
    driver: webdriver.Chrome,
    timeout: int = EXTENSION_SSO_TIMEOUT,
) -> None:
    """Wait until the extension shows the logged-in UI (search ready, sign-in gone)."""
    WebDriverWait(driver, timeout).until(lambda d: _extension_search_ready(d))
    _wait_extension_stable(driver, timeout=min(timeout, 15))


def wait_for_extension_on_page(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Wait until the Dakota content script injects and the floating button is ready."""
    WebDriverWait(driver, timeout).until(lambda d: _extension_host_ready(d))
    WebDriverWait(driver, timeout).until(lambda d: _floating_button_ready(d))


def wait_for_extension_sso_complete(driver: webdriver.Chrome, timeout: int = EXTENSION_SSO_TIMEOUT) -> None:
    """
    After clicking extension sign-in, wait for SSO to finish.

    Waits while sign-in/loading UI is visible, then until company search is ready.
    """
    # Brief window where click is registered but SSO has not started yet.
    WebDriverWait(driver, 10).until(
        lambda d: _sso_clicked_and_pending(d) or _extension_search_ready(d)
    )

    if not _extension_search_ready(driver):
        WebDriverWait(driver, timeout).until(lambda d: _extension_search_ready(d))

    _wait_extension_stable(driver, timeout=min(timeout, 15))


def _wait_extension_stable(driver: webdriver.Chrome, timeout: int = 10) -> None:
    """Require search-ready state to hold briefly so React/SSO does not race the next step."""
    deadline = time.monotonic() + timeout
    stable_since: float | None = None

    while time.monotonic() < deadline:
        if _extension_search_ready(driver):
            if stable_since is None:
                stable_since = time.monotonic()
            if time.monotonic() - stable_since >= POST_LOGIN_STABILIZE_SEC:
                return
        else:
            stable_since = None
        time.sleep(0.25)

    raise TimeoutException(
        "Extension login UI did not stabilize — company search was not consistently ready."
    )


def close_dakota_sidebar(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Close the extension sidebar so the floating button is visible again."""
    if not is_sidebar_open(driver):
        return

    closed = driver.execute_script(
        f"""
        const host = document.getElementById('crxjs-app');
        const root = host?.shadowRoot;
        if (!root) return false;
        const closeBtn = root.querySelector('{SIDEBAR_CLOSE_BUTTON_CSS}');
        if (!closeBtn) return false;
        closeBtn.click();
        return true;
        """
    )
    if not closed:
        raise TimeoutException("Could not find sidebar close button.")

    WebDriverWait(driver, timeout).until(lambda d: not is_sidebar_open(d))


def click_extension_again_with_delay(
    driver: webdriver.Chrome,
    delay_seconds: int = EXTENSION_FINAL_DELAY_SECONDS,
) -> None:
    """
    After login tests: close sidebar, click the extension floating button again,
    then wait so you can see the UI on screen.
    """
    close_dakota_sidebar(driver)
    open_dakota_sidebar(driver)
    wait_for_extension_logged_in(driver)
    print(f"\n[EXTENSION] Opened again — waiting {delay_seconds} seconds...\n")
    time.sleep(delay_seconds)


def login_to_dakota_portal(
    driver: webdriver.Chrome,
    credentials: DakotaCredentials,
    portal_url: str = DAKOTA_PORTAL_URL,
    timeout: int = PORTAL_LOGIN_TIMEOUT,
) -> None:
    """
    Step 1 — Log in on the Dakota website.

    Opens the portal URL, fills username/password, and waits for the home page.
    """
    with allure_step(driver, "Open Dakota portal"):
        driver.get(portal_url)
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        attach_page_info(driver)

    if "SigninUI" in driver.current_url or driver.find_elements(By.XPATH, LOGIN_EMAIL_XPATH):
        with allure_step(driver, "Fill portal login form"):
            wait_for_portal_login_form(driver, timeout=timeout)
            fill_portal_login_form(driver, credentials, timeout=timeout)
        with allure_step(driver, "Wait for portal home page"):
            wait_for_portal_logged_in(driver, timeout=timeout)
    elif _is_portal_home_url(driver.current_url):
        with allure_step(driver, "Portal session already active"):
            wait_for_extension_on_page(driver, timeout=timeout)
    else:
        attach_screenshot(driver, "Unexpected portal URL")
        raise TimeoutException(f"Unexpected portal URL after navigation: {driver.current_url}")


def authenticate_extension_via_sso(
    driver: webdriver.Chrome,
    timeout: int = EXTENSION_SSO_TIMEOUT,
) -> None:
    """
    Step 2 — Open extension and click login (auto SSO).

    Must be called AFTER login_to_dakota_portal() on the same browser session.
    """
    with allure_step(driver, "Wait for extension on portal page"):
        wait_for_extension_on_page(driver, timeout=timeout)
    with allure_step(driver, "Open extension sidebar"):
        open_dakota_sidebar(driver, timeout=timeout)
    with allure_step(driver, "Click Log in with Salesforce"):
        click_extension_login_button(driver, timeout=timeout)
    with allure_step(driver, "Wait for extension SSO"):
        wait_for_extension_sso_complete(driver, timeout=timeout)
    with allure_step(driver, "Verify extension search is ready"):
        open_dakota_sidebar(driver, timeout=timeout)
        wait_for_extension_logged_in(driver, timeout=timeout)


def login_to_dakota(
    driver: webdriver.Chrome,
    credentials: DakotaCredentials,
    portal_url: str = DAKOTA_PORTAL_URL,
    timeout: int = PORTAL_LOGIN_TIMEOUT,
    *,
    final_extension_delay: bool = True,
) -> None:
    """
    Full flow: portal login → open extension → click login → auto SSO.

    Set final_extension_delay=False for performance tests (skips the 5s demo pause).
    """
    with allure_step(driver, "Portal + extension login", screenshot=False):
        login_to_dakota_portal(driver, credentials, portal_url=portal_url, timeout=timeout)
        authenticate_extension_via_sso(driver, timeout=EXTENSION_SSO_TIMEOUT)
    if final_extension_delay:
        with allure_step(driver, "Re-open extension after login"):
            click_extension_again_with_delay(driver)
    else:
        attach_screenshot(driver, "Logged in — extension ready")
