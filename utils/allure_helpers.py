"""Allure steps and screenshot attachments for Selenium tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from selenium.webdriver.chrome.webdriver import WebDriver

try:
    import allure
except ImportError:  # pragma: no cover - optional when allure-pytest is not installed
    allure = None


def allure_available() -> bool:
    return allure is not None


def attach_screenshot(driver: "WebDriver", name: str = "Screenshot") -> None:
    """Attach the current browser view to the active Allure step or test."""
    if not allure_available():
        return
    try:
        png = driver.get_screenshot_as_png()
    except Exception:
        return
    if not png:
        return
    allure.attach(
        png,
        name=name,
        attachment_type=allure.attachment_type.PNG,
    )


@contextmanager
def allure_step(driver: "WebDriver | None", title: str, *, screenshot: bool = True):
    """
    Record an Allure step and optionally attach a screenshot when it completes.

    Pass driver=None to record a step without a screenshot.
    """
    if not allure_available():
        yield
        return

    with allure.step(title):
        yield
        if screenshot and driver is not None:
            attach_screenshot(driver, title)


def attach_page_info(driver: "WebDriver", label: str = "Page info") -> None:
    """Attach URL and title for debugging without a full screenshot."""
    if not allure_available():
        return
    try:
        info = f"URL: {driver.current_url}\nTitle: {driver.title}"
    except Exception:
        return
    allure.attach(info, name=label, attachment_type=allure.attachment_type.TEXT)
