"""
Tests for the Dakota Marketplace Chrome extension.

Run all tests:
    pytest

Run only smoke tests:
    pytest -m smoke

Run a single test:
    pytest tests/test_dakota.py::test_extension_is_loaded -v
"""

import json
import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from conftest import (
    build_extension_url,
    click_dakota_floating_button,
    get_popup_relative_path,
    is_content_script_active,
    is_extension_loaded,
    wait_for_extension_page,
)

# Mark every test in this file as an "extension" test (see pytest.ini)
pytestmark = pytest.mark.extension


# ---------------------------------------------------------------------------
# 1. Tests that do NOT need a browser (fast checks)
# ---------------------------------------------------------------------------


def test_extension_files_exist(extension_paths):
    """
    Verify the .crx file and unpacked folder exist on disk.

    If this fails, run:  python download_extension.py
    """
    assert extension_paths["crx_file"].exists(), (
        f".crx file missing at {extension_paths['crx_file']}. "
        "Run: python download_extension.py"
    )
    assert extension_paths["unpacked_dir"].exists(), (
        f"Unpacked folder missing at {extension_paths['unpacked_dir']}. "
        "Run: python download_extension.py"
    )

    manifest_file = extension_paths["unpacked_dir"] / "manifest.json"
    assert manifest_file.exists(), "manifest.json not found inside unpacked extension."


def test_manifest_describes_dakota_extension(extension_paths):
    """
    Read manifest.json from disk and confirm it is the Dakota extension.

    Dakota Marketplace uses a content-script sidebar (no toolbar popup).
  If default_popup is missing, that is expected for this extension.
    """
    manifest = extension_paths["manifest"]

    assert manifest.get("manifest_version") == 3
    assert manifest.get("name") == extension_paths["extension_name"]
    assert extension_paths["has_popup"] is False, (
        "Dakota currently has no default_popup in manifest.json. "
        "Use content-script checks instead of popup URL tests."
    )


# ---------------------------------------------------------------------------
# 2. Tests that launch Chrome with the extension
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_extension_is_loaded(chrome_driver, extension_paths, installed_ext_id):
    """
    Smoke test: launch Chrome, install the extension, and verify it is active.

    How we verify:
      - Open chrome-extension://<runtime-id>/manifest.json
      - If we get valid JSON back, the extension is loaded
    """
    loaded = is_extension_loaded(chrome_driver, installed_ext_id)
    assert loaded, (
        f"Extension '{extension_paths['extension_name']}' does not appear to be loaded. "
        f"Runtime ID: {installed_ext_id} | "
        f"Chrome Web Store ID: {extension_paths['store_extension_id']}"
    )


@pytest.mark.smoke
def test_open_extension_base_url(chrome_driver, installed_ext_id, extension_paths):
    """
    Open the extension root URL directly (no toolbar click needed).

    Use the RUNTIME extension ID returned by webextension.install(), e.g.:
      chrome-extension://<runtime-id>/

    The Chrome Web Store ID (pkjcjmhoaajnghcgbkkdfgakcbdnpefj) only works when
    the extension is installed from the store with that signed ID.
    """
    base_url = build_extension_url(installed_ext_id)
    wait_for_extension_page(chrome_driver, base_url)

    current = chrome_driver.current_url
    assert current.startswith(f"chrome-extension://{installed_ext_id}"), (
        f"Unexpected URL after navigation: {current}"
    )


@pytest.mark.smoke
def test_content_script_injects_on_web_page(chrome_driver, wait):
    """
    Verify Dakota's content script runs on a normal website.

    Dakota injects a host element #crxjs-app with a Shadow DOM — not a popup.
    After opening any page, we wait for that host element to appear.
    """
    chrome_driver.get("https://example.com")
    assert is_content_script_active(chrome_driver), (
        "Dakota content script did not inject #crxjs-app on the page. "
        "Check that the extension installed correctly."
    )


def test_inspect_extension_ui_on_web_page(chrome_driver, wait):
    """
    Inspect the injected Dakota UI and print useful selectors for more tests.

    Because the UI lives inside a Shadow DOM, we query through #crxjs-app.
    """
    chrome_driver.get("https://example.com")
    wait.until(lambda d: is_content_script_active(d))

    page_info = chrome_driver.execute_script(
        """
        const host = document.getElementById('crxjs-app');
        if (!host || !host.shadowRoot) {
            return { error: 'Shadow host not found' };
        }
        const root = host.shadowRoot;
        const buttons = [...root.querySelectorAll('button')].map((el) => ({
            text: (el.textContent || '').trim(),
            id: el.id,
            className: el.className,
        }));
        const links = [...root.querySelectorAll('a')].map((el) => ({
            text: (el.textContent || '').trim(),
            href: el.getAttribute('href'),
            id: el.id,
        }));
        const inputs = [...root.querySelectorAll('input')].map((el) => ({
            type: el.type,
            id: el.id,
            name: el.name,
            placeholder: el.placeholder,
        }));
        return {
            hostId: host.id,
            buttonCount: buttons.length,
            buttons: buttons.slice(0, 10),
            links: links.slice(0, 10),
            inputs: inputs.slice(0, 10),
            floatingButtonVisible: !!root.querySelector('.dakota-floating-button'),
        };
        """
    )

    print("\n--- DAKOTA UI INSPECTION REPORT (Shadow DOM) ---")
    print(json.dumps(page_info, indent=2))
    print("--- END REPORT ---\n")

    assert page_info.get("hostId") == "crxjs-app"
    assert page_info.get("floatingButtonVisible") is True


def test_open_extension_popup_if_configured(chrome_driver, extension_paths, installed_ext_id, wait):
    """
    Open a popup URL when the manifest defines default_popup.

    Dakota Marketplace does not define a popup today, so this test is skipped.
    Keep this test as a template for extensions that DO have popups.
    """
    popup_path = extension_paths["popup_relative_path"]
    if not popup_path:
        pytest.skip(
            "Dakota Marketplace has no default_popup. "
            "It uses an in-page sidebar instead of a toolbar popup."
        )

    popup_url = build_extension_url(installed_ext_id, popup_path)
    wait_for_extension_page(chrome_driver, popup_url)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    body = chrome_driver.find_element(By.TAG_NAME, "body")
    print(f"\n  Popup URL : {popup_url}")
    print(f"  Page title: {chrome_driver.title}")
    print(f"  Body text : {body.text[:200]!r}")
    assert body is not None


@pytest.mark.visual
def test_see_dakota_sidebar_on_screen(chrome_driver, pause_seconds, keep_open):
    """
    Visual demo: open Dakota sidebar so you can watch it on screen.

    Run with:
        pytest tests/test_dakota.py::test_see_dakota_sidebar_on_screen --pause 45
        pytest tests/test_dakota.py::test_see_dakota_sidebar_on_screen --keep-open
    """
    # chrome_driver fixture already opened example.com and waited for the content script
    clicked = click_dakota_floating_button(chrome_driver)
    assert clicked, "Could not find Dakota floating button on the page."

    # Wait for sidebar container to appear in Shadow DOM
    WebDriverWait(chrome_driver, 20).until(
        lambda d: d.execute_script(
            """
            const host = document.getElementById('crxjs-app');
            return !!host?.shadowRoot?.querySelector('.dakota-sidebar-container');
            """
        )
    )

    if not keep_open and pause_seconds == 0:
        print("\n[VISUAL] Sidebar is open. Waiting 15 seconds so you can see it...")
        time.sleep(15)


def test_manifest_accessible_in_browser(chrome_driver, installed_ext_id, extension_paths, wait):
    """
    Open manifest.json via chrome-extension:// URL and validate the response.
    """
    manifest_url = build_extension_url(installed_ext_id, "manifest.json")
    wait_for_extension_page(chrome_driver, manifest_url)

    body = chrome_driver.find_element(By.TAG_NAME, "body")
    manifest_data = json.loads(body.text)

    assert manifest_data.get("manifest_version") >= 2
    assert manifest_data.get("name") == extension_paths["extension_name"]
    print(f"\n  Extension name (from manifest): {manifest_data.get('name')}")
    print(f"  Manifest version: {manifest_data.get('manifest_version')}")
    print(f"  Popup path: {get_popup_relative_path(manifest_data)}")
    print(f"  Runtime extension ID: {installed_ext_id}")
    print(f"  Chrome Web Store ID: {extension_paths['store_extension_id']}")
