"""
Download the Dakota Marketplace Chrome extension (.crx) from the Chrome Web Store.

Run this script BEFORE your tests if the extension file is missing:
    python download_extension.py

What it does:
  1. Creates an "extensions" folder in the project root (if it does not exist).
  2. Downloads the .crx file using Google's update service.
  3. Saves it as extensions/dakota.crx.
  4. Unpacks the .crx into extensions/dakota/ so Chrome can load it reliably.
"""

import io
import zipfile
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Extension settings — change these if you test a different extension
# ---------------------------------------------------------------------------
EXTENSION_ID = "pkjcjmhoaajnghcgbkkdfgakcbdnpefj"
EXTENSION_NAME = "Dakota Marketplace"

# Folder paths (relative to this script's location)
PROJECT_ROOT = Path(__file__).resolve().parent
EXTENSIONS_DIR = PROJECT_ROOT / "extensions"
CRX_FILE = EXTENSIONS_DIR / "dakota.crx"
UNPACKED_DIR = EXTENSIONS_DIR / "dakota"

# Google Chrome update URL used to download extensions as .crx files
DOWNLOAD_URL = (
    "https://clients2.google.com/service/update2/crx?"
    "response=redirect&prodversion=149.0"
    "&acceptformat=crx2,crx3"
    f"&x=id%3D{EXTENSION_ID}%26installsource%3Dondemand%26uc"
)


def _find_zip_start(crx_bytes: bytes) -> int:
    """
    A .crx file is a ZIP archive with a small header in front.
    This function finds where the ZIP data starts (the 'PK' signature).
    """
    zip_start = crx_bytes.find(b"PK\x03\x04")
    if zip_start == -1:
        raise ValueError("Downloaded file does not look like a valid .crx (no ZIP data found).")
    return zip_start


def unpack_crx(crx_path: Path, destination: Path) -> None:
    """
    Extract the contents of a .crx file into a folder.
    Chrome's --load-extension flag needs an unpacked folder, not a .crx file.
    """
    crx_bytes = crx_path.read_bytes()
    zip_start = _find_zip_start(crx_bytes)

    # Clean up any previous unpack so we always have a fresh copy
    if destination.exists():
        import shutil

        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(crx_bytes[zip_start:])) as archive:
        archive.extractall(destination)


def download_extension() -> Path:
    """
    Download the extension and unpack it. Returns the path to the unpacked folder.
    """
    EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading '{EXTENSION_NAME}' (ID: {EXTENSION_ID})...")
    response = requests.get(DOWNLOAD_URL, timeout=60)
    response.raise_for_status()

    if len(response.content) < 100:
        raise RuntimeError(
            "Download failed — file is too small. "
            "Check your network or try updating prodversion in the URL."
        )

    CRX_FILE.write_bytes(response.content)
    print(f"Saved .crx file to: {CRX_FILE}")

    unpack_crx(CRX_FILE, UNPACKED_DIR)
    print(f"Unpacked extension to: {UNPACKED_DIR}")

    return UNPACKED_DIR


if __name__ == "__main__":
    download_extension()
    print("Extension downloaded and unpacked successfully.")
