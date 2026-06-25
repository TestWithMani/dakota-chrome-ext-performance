"""
Open Chrome with Dakota installed and keep it open so you can SEE the extension.

This is the easiest way to visually confirm the extension works.

Run:
    python demo_extension.py

Optional — pause N seconds before closing (default: 120):
    python demo_extension.py 60

Keep open until you press Enter:
    python demo_extension.py --keep-open

Login on portal then extension SSO:
    python demo_extension.py --login --keep-open

WHERE TO LOOK:
  Dakota does NOT use a toolbar popup. After the browser opens example.com,
  look at the BOTTOM-RIGHT corner of the page for the Dakota floating button.
  Click it to open the sidebar.
"""

import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from conftest import (
    click_dakota_floating_button,
    create_chrome_options,
    install_extension,
    load_dakota_credentials,
    open_demo_page_with_extension,
)
from download_extension import UNPACKED_DIR, download_extension
from pages.dakota_auth import login_to_dakota


def main() -> None:
    keep_open = "--keep-open" in sys.argv
    pause_seconds = 120

    for arg in sys.argv[1:]:
        if arg.isdigit():
            pause_seconds = int(arg)

    if not (UNPACKED_DIR / "manifest.json").exists():
        print("Downloading extension first...")
        download_extension()

    # Stable profile folder so the same extension ID is reused during manual demos
    profile_dir = Path(__file__).resolve().parent / ".chrome-demo-profile"
    profile_dir.mkdir(exist_ok=True)

    options = create_chrome_options(profile_dir)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        print("\nInstalling Dakota Marketplace extension...")
        ext_id = install_extension(driver, UNPACKED_DIR)
        print(f"Extension installed. Runtime ID: {ext_id}")
        time.sleep(2)

        print("\nOpening example.com — wait for the Dakota floating button (bottom-right)...")
        open_demo_page_with_extension(driver)

        if "--login" in sys.argv:
            print("\nLogging in on Dakota portal, then extension SSO...")
            login_to_dakota(driver, load_dakota_credentials())
            print("Login complete — extension opened again with 5 second delay.")
        else:
            clicked = click_dakota_floating_button(driver)
            if clicked:
                print("Clicked the Dakota floating button — sidebar should be open.")
                time.sleep(2)
            else:
                print("Floating button not found yet — look at the bottom-right of the page.")

        print(
            "\n*** TIP: The extension UI is ON THE WEB PAGE, not in the Chrome toolbar. ***\n"
        )

        if keep_open:
            input("Press Enter to close Chrome...")
        else:
            print(f"Keeping browser open for {pause_seconds} seconds...")
            time.sleep(pause_seconds)
    finally:
        driver.quit()
        print("Chrome closed.")


if __name__ == "__main__":
    main()
