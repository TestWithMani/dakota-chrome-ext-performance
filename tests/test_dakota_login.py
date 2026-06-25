"""
Dakota login tests.

Flow:
  1. Log in on https://dakotanetworks.my.site.com/dakotaMarketplace/s/
  2. Open extension → click "Log in with Salesforce"
  3. Extension auto-authenticates via existing website session

Run:
    pytest tests/test_dakota_login.py -v
    pytest tests/test_dakota_login.py -v --keep-open
    pytest tests/test_dakota_login.py -v --pause 30

Credentials: credentials.env or DAKOTA_USERNAME / DAKOTA_PASSWORD env vars.
"""

import pytest

from pages.dakota_auth import (
    DAKOTA_PORTAL_URL,
    authenticate_extension_via_sso,
    click_extension_again_with_delay,
    login_to_dakota,
    login_to_dakota_portal,
)

pytestmark = [pytest.mark.extension, pytest.mark.auth]


@pytest.mark.smoke
def test_dakota_portal_and_extension_login(chrome_driver, dakota_credentials):
    """
    End-to-end:
      1. Login on Dakota website (username + password)
      2. Open extension sidebar
      3. Click .dakota-salesforce-signin-button
      4. Extension auto-authenticates — verify #company-search appears
    """
    login_to_dakota(chrome_driver, dakota_credentials)

    assert DAKOTA_PORTAL_URL.rstrip("/") in chrome_driver.current_url.rstrip("/") or (
        "/dakotaMarketplace/s/" in chrome_driver.current_url
    )

    search_placeholder = chrome_driver.execute_script(
        """
        const host = document.getElementById('crxjs-app');
        const input = host?.shadowRoot?.querySelector('#company-search');
        return input ? input.placeholder : null;
        """
    )
    assert search_placeholder, "Company search should be visible after extension SSO login."
    print(f"\n  Portal URL : {chrome_driver.current_url}")
    print(f"  Search box : {search_placeholder!r}")


@pytest.mark.visual
def test_dakota_login_step_by_step(chrome_driver, dakota_credentials, keep_open):
    """
    Same flow in two visible steps — run with --keep-open to watch.

        pytest tests/test_dakota_login.py::test_dakota_login_step_by_step --keep-open
    """
    login_to_dakota_portal(chrome_driver, dakota_credentials)
    authenticate_extension_via_sso(chrome_driver)
    click_extension_again_with_delay(chrome_driver)
