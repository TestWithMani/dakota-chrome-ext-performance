"""
Pytest configuration and shared fixtures.

conftest.py is a special pytest file — you do NOT import it yourself.
Pytest automatically loads it and makes the fixtures available to every test.

Fixtures provided here:
  - extension_paths   : paths to the .crx and unpacked extension folder
  - chrome_driver     : Chrome WebDriver with the Dakota extension installed
  - installed_ext_id  : the runtime extension ID assigned by Chrome
  - logged_in_driver    : Chrome logged into portal + extension (for performance tests)
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from download_extension import (
    CRX_FILE,
    EXTENSION_ID,
    EXTENSION_NAME,
    UNPACKED_DIR,
    download_extension,
)
from pages.dakota_auth import DakotaCredentials, login_to_dakota
from pages.dakota_performance import DakotaPerformance

# How long (in seconds) to wait for pages and elements before failing a test
DEFAULT_TIMEOUT = 20

# Project root folder
PROJECT_ROOT = Path(__file__).resolve().parent


def is_headless_mode() -> bool:
    """
    True when Chrome should run without a visible window (CI / Jenkins).

    Set DAKOTA_HEADLESS=1 explicitly, or rely on common CI env vars.
    """
    if os.environ.get("DAKOTA_HEADLESS", "").strip().lower() in {"1", "true", "yes"}:
        return True
    if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}:
        return True
    if os.environ.get("JENKINS_URL"):
        return True
    return False


# ---------------------------------------------------------------------------
# Helper functions (used by fixtures and tests)
# ---------------------------------------------------------------------------


def ensure_extension_ready() -> Path:
    """
    Make sure the extension is downloaded and unpacked.
    Downloads it automatically if the unpacked folder is missing.
    """
    manifest = UNPACKED_DIR / "manifest.json"
    if not manifest.exists():
        print("\nExtension not found — downloading now...")
        return download_extension()
    return UNPACKED_DIR


def read_manifest(unpacked_dir: Path) -> dict:
    """Read manifest.json from the unpacked extension folder."""
    manifest_path = unpacked_dir / "manifest.json"
    with manifest_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_popup_relative_path(manifest: dict) -> str | None:
    """
    Find the popup HTML file path from manifest.json.

    Chrome extensions can declare the popup in different places depending on
    Manifest V2 vs V3:
      - MV3: "action" -> "default_popup"
      - MV2: "browser_action" or "page_action" -> "default_popup"

    Note: Dakota Marketplace does NOT define a popup. It injects a sidebar UI
    into web pages via a content script instead.
    """
    for key in ("action", "browser_action", "page_action"):
        section = manifest.get(key, {})
        popup = section.get("default_popup")
        if popup:
            return popup
    return None


def build_extension_url(extension_id: str, relative_path: str = "") -> str:
    """
    Build a chrome-extension:// URL.

    Examples:
      chrome-extension://<id>/
      chrome-extension://<id>/manifest.json
    """
    base = f"chrome-extension://{extension_id}/"
    if not relative_path:
        return base
    return base + relative_path.lstrip("/")


def create_chrome_options(user_data_dir: Path) -> Options:
    """
    Build ChromeOptions for extension testing on modern Chrome (137+).

    Chrome removed the old --load-extension command-line flag.
    We use WebDriver BiDi instead (enabled below) and install the extension
    after the browser starts via driver.webextension.install().

    Chrome also requires a dedicated user-data-dir when BiDi extension
    debugging is enabled.

    In Jenkins / CI, set DAKOTA_HEADLESS=1 (or CI=true / JENKINS_URL) to use
    --headless=new, which supports extensions on Chrome 109+.
    """
    options = Options()

    # Required for WebDriver BiDi + extension install on Chrome/Edge
    options.enable_bidi = True
    options.enable_webextensions = True
    options.add_argument(f"--user-data-dir={user_data_dir}")

    headless = is_headless_mode()
    if headless:
        # New headless mode — required for extension + content scripts in CI
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    else:
        options.add_argument("--start-maximized")

    # Recommended flags for automation (local dev and CI/Jenkins)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options


def install_extension(driver: webdriver.Chrome, unpacked_extension_path: Path) -> str:
    """
    Install the unpacked extension using WebDriver BiDi.

    Returns the extension ID assigned at runtime (this may differ from the
    Chrome Web Store ID when loading an unpacked copy).
    """
    result = driver.webextension.install(path=str(unpacked_extension_path))
    if isinstance(result, dict):
        return result["extension"]
    return result


def wait_for_extension_page(driver: webdriver.Chrome, url: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    """
    Wait until navigating to a chrome-extension:// URL succeeds.

    We consider the page loaded when document.readyState is 'complete'.
    """
    driver.get(url)
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def is_extension_loaded(driver: webdriver.Chrome, extension_id: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Check whether the extension is installed by opening manifest.json
    inside the browser and verifying we get valid JSON back.
    """
    manifest_url = build_extension_url(extension_id, "manifest.json")
    try:
        wait_for_extension_page(driver, manifest_url, timeout)
        body_text = driver.find_element("tag name", "body").text.strip()
        if not body_text:
            return False
        parsed = json.loads(body_text)
        return parsed.get("name") is not None or parsed.get("manifest_version") is not None
    except (TimeoutException, json.JSONDecodeError, Exception):
        return False


def is_content_script_active(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Verify Dakota's content script injected its host element on the current page.

    Dakota renders UI inside a Shadow DOM attached to #crxjs-app, so a plain
    document.getElementById('dakota-app-root') check on the page will fail.
    """
    script = """
        const host = document.getElementById('crxjs-app');
        return !!(host && host.shadowRoot);
    """
    try:
        WebDriverWait(driver, timeout).until(lambda d: d.execute_script(script))
        return True
    except TimeoutException:
        return False


def pause_for_visual_inspection(seconds: int, message: str) -> None:
    """Keep the browser open so you can see the extension on screen."""
    if seconds <= 0:
        return
    print(f"\n[VISUAL PAUSE] {message}")
    print(f"               Waiting {seconds} seconds — look at the Chrome window now.\n")
    time.sleep(seconds)


def open_demo_page_with_extension(driver: webdriver.Chrome) -> None:
    """
    Open a normal web page where Dakota injects its floating button / sidebar.

    The extension does NOT appear as a classic toolbar popup. Look at the
    bottom-right corner of the page for the Dakota floating button.
    """
    driver.get("https://example.com")
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    is_content_script_active(driver)
    # Extra moment for React UI and the floating button to render
    time.sleep(2)


def click_dakota_floating_button(driver: webdriver.Chrome) -> bool:
    """Click the Dakota floating button inside the Shadow DOM (opens sidebar)."""
    return driver.execute_script(
        """
        const host = document.getElementById('crxjs-app');
        if (!host || !host.shadowRoot) return false;
        const btn = host.shadowRoot.querySelector('.dakota-floating-button');
        if (!btn) return false;
        btn.click();
        return true;
        """
    )


# ---------------------------------------------------------------------------
# Pytest CLI options
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    """Add --pause and --keep-open flags for visual debugging."""
    parser.addoption(
        "--pause",
        action="store",
        default=None,
        type=int,
        help="Keep Chrome open N seconds before/after each test (e.g. --pause 30)",
    )
    parser.addoption(
        "--keep-open",
        action="store_true",
        default=False,
        help="Wait for Enter in the terminal before closing Chrome",
    )


@pytest.fixture
def pause_seconds(request) -> int:
    """
    Seconds to pause for visual inspection.

    Priority: --pause flag > DAKOTA_PAUSE_SECONDS env var > 0
    """
    cli_value = request.config.getoption("--pause")
    if cli_value is not None:
        return max(0, int(cli_value))
    return max(0, int(os.environ.get("DAKOTA_PAUSE_SECONDS", "0")))


@pytest.fixture
def keep_open(request) -> bool:
    """True when --keep-open is passed or DAKOTA_KEEP_OPEN=1."""
    if request.config.getoption("--keep-open"):
        return True
    return os.environ.get("DAKOTA_KEEP_OPEN", "").strip() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def extension_paths() -> dict:
    """
    Session-scoped fixture: download extension once for the whole test run.

    Returns a dictionary with useful paths and metadata.
    """
    unpacked = ensure_extension_ready()
    manifest = read_manifest(unpacked)
    popup_path = get_popup_relative_path(manifest)

    return {
        "store_extension_id": EXTENSION_ID,
        "extension_name": EXTENSION_NAME,
        "crx_file": CRX_FILE,
        "unpacked_dir": unpacked,
        "manifest": manifest,
        "popup_relative_path": popup_path,
        "has_popup": popup_path is not None,
    }


@pytest.fixture
def chrome_profile_dir():
    """
    Temporary Chrome profile directory for one test.
    Cleaned up automatically after the test finishes.
    """
    profile_dir = Path(tempfile.mkdtemp(prefix="dakota-chrome-"))
    yield profile_dir
    shutil.rmtree(profile_dir, ignore_errors=True)


@pytest.fixture
def chrome_driver(extension_paths, chrome_profile_dir, pause_seconds, keep_open) -> webdriver.Chrome:
    """
    Function-scoped fixture: fresh Chrome browser with Dakota installed.

    Usage in a test:
        def test_something(chrome_driver, installed_ext_id):
            url = f"chrome-extension://{installed_ext_id}/manifest.json"
            chrome_driver.get(url)

    To SEE the extension on screen, run:
        pytest --pause 30
        pytest --keep-open
        pytest -m visual --pause 45
    """
    options = create_chrome_options(chrome_profile_dir)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Install once and save the runtime ID on the driver for other fixtures/tests
    driver.dakota_extension_id = install_extension(driver, extension_paths["unpacked_dir"])
    time.sleep(2)  # give Chrome time to register the extension

    # Open a demo page so Dakota UI is visible (floating button, bottom-right)
    open_demo_page_with_extension(driver)

    pause_for_visual_inspection(
        pause_seconds,
        "Dakota should be visible on example.com — look for the floating button "
        "at the bottom-right of the page (not in the Chrome toolbar).",
    )

    yield driver

    if keep_open:
        input("\n[KEEP-OPEN] Press Enter in this terminal to close Chrome...\n")
    else:
        pause_for_visual_inspection(
            pause_seconds,
            "Test finished — browser will close shortly.",
        )
    driver.quit()


@pytest.fixture
def installed_ext_id(chrome_driver) -> str:
    """
    The extension ID Chrome assigned when the unpacked extension was installed.

    Important: this is often NOT the same as the Chrome Web Store ID
    (pkjcjmhoaajnghcgbkkdfgakcbdnpefj) unless you install from the store.
    """
    return chrome_driver.dakota_extension_id


def load_dakota_credentials() -> DakotaCredentials:
    """
    Load test credentials from environment variables or credentials.env.

    Priority: env vars > credentials.env file
    """
    creds_file = PROJECT_ROOT / "credentials.env"
    if creds_file.exists():
        for line in creds_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    username = os.environ.get("DAKOTA_USERNAME", "").strip()
    password = os.environ.get("DAKOTA_PASSWORD", "").strip()

    if not username or not password:
        raise RuntimeError(
            "Dakota credentials not found. Set DAKOTA_USERNAME and DAKOTA_PASSWORD "
            "environment variables or create a credentials.env file in the project root."
        )

    return DakotaCredentials(username=username, password=password)


@pytest.fixture(scope="session")
def dakota_credentials() -> DakotaCredentials:
    """Salesforce / Dakota login credentials for auth tests."""
    return load_dakota_credentials()


@pytest.fixture
def wait(chrome_driver) -> WebDriverWait:
    """A WebDriverWait instance tied to the current browser."""
    return WebDriverWait(chrome_driver, DEFAULT_TIMEOUT)


@pytest.fixture(scope="session")
def performance_profile_dir():
    """Stable Chrome profile for one performance test session."""
    profile_dir = Path(tempfile.mkdtemp(prefix="dakota-perf-"))
    yield profile_dir
    shutil.rmtree(profile_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def logged_in_driver(extension_paths, performance_profile_dir, dakota_credentials):
    """
    Chrome with extension installed + portal login + extension SSO.

    Used by all performance timing tests. Opens the Dakota website first,
    then uses the extension for company search/actions.
    """
    options = create_chrome_options(performance_profile_dir)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.dakota_extension_id = install_extension(driver, extension_paths["unpacked_dir"])
    time.sleep(1)  # brief pause for Chrome to register the unpacked extension

    login_to_dakota(driver, dakota_credentials, final_extension_delay=False)

    yield driver
    driver.quit()


@pytest.fixture
def dakota_performance(logged_in_driver) -> DakotaPerformance:
    """Performance helper bound to the logged-in browser session."""
    perf = DakotaPerformance(logged_in_driver)
    perf.ensure_logged_in_on_portal(load_dakota_credentials())
    return perf


def pytest_sessionstart(session):
    from utils.performance_config import PERFORMANCE_REPORT_TEST_NAMES
    from utils.search_report import initialize_performance_report_for_session

    if any(item.name in PERFORMANCE_REPORT_TEST_NAMES for item in session.items):
        initialize_performance_report_for_session()


def pytest_collection_modifyitems(items):
    order = {
        "test_dakota_search_time": 1,
        "test_company_detail_loading_time": 2,
        "test_company_contacts_loading_time": 3,
        "test_company_type_specific_tab_loading_time": 4,
        "test_search_load_more_time": 5,
    }
    items.sort(key=lambda item: order.get(item.name, 99))
