"""
Selenium performance helpers for Dakota extension.

Flow (same as login tests):
  1. Open portal URL and log in on the website
  2. Open extension + SSO
  3. Search companies and measure how long each action takes
"""

import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from pages.dakota_auth import (
    DAKOTA_PORTAL_URL,
    login_to_dakota,
    open_dakota_sidebar,
    wait_for_extension_logged_in,
)
from utils.performance_config import profile_tab_for_company_type
from utils.search_report import (
    PERFORMANCE_TEST_CASE_LABELS,
    SearchSummary,
    append_test_case_result,
    build_test_case_summary_row,
    get_performance_report_path,
    get_search_report_metadata,
)

DEFAULT_TIMEOUT = 60
SEARCH_DEBOUNCE_SEC = 1.5
VISIBILITY_PAUSE_SEC = 3


@dataclass
class SearchTiming:
    elapsed_s: float
    result_count: int
    has_load_more: bool


@dataclass
class ActionTiming:
    elapsed_s: float
    company_name: str
    company_type: str
    tab_name: str = ""


class DakotaPerformance:
    """Company search and load-time measurements via Selenium + Shadow DOM."""

    def __init__(self, driver: webdriver.Chrome) -> None:
        self.driver = driver

    # ------------------------------------------------------------------
    # Shadow DOM helpers
    # ------------------------------------------------------------------

    def _js(self, script: str, *args):
        return self.driver.execute_script(script, *args)

    def _shadow_ready(self) -> bool:
        return bool(
            self._js(
                "return !!(document.getElementById('crxjs-app')?.shadowRoot);"
            )
        )

    def _wait_shadow(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        WebDriverWait(self.driver, timeout).until(lambda d: self._shadow_ready())

    def _search_input_ready(self) -> bool:
        return bool(
            self._js(
                """
                const root = document.getElementById('crxjs-app')?.shadowRoot;
                if (!root) return false;
                const signin = root.querySelector('.dakota-salesforce-signin-button');
                const search = root.querySelector('#company-search');
                const loading = root.querySelector(
                    '.dakota-loading, .dakota-signin-loading, .dakota-loading-text'
                );
                if (loading && loading.offsetParent !== null) return false;
                if (signin && signin.offsetParent !== null) return false;
                if (!search || search.disabled) return false;
                const style = window.getComputedStyle(search);
                return style.display !== 'none' && style.visibility !== 'hidden';
                """
            )
        )

    def ensure_logged_in_on_portal(self, credentials) -> None:
        """Portal login + extension SSO (reuses pages.dakota_auth)."""
        if not self._search_input_ready():
            login_to_dakota(self.driver, credentials, final_extension_delay=False)
            wait_for_extension_logged_in(self.driver)
        else:
            open_dakota_sidebar(self.driver)
            wait_for_extension_logged_in(self.driver)

    def clear_search(self) -> None:
        self._js(
            """
            const root = document.getElementById('crxjs-app')?.shadowRoot;
            const close = root?.querySelector('.dakota-search-close-button');
            if (close) { close.click(); return; }
            const input = root?.querySelector('#company-search');
            if (input) {
                input.value = '';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            """
        )
        time.sleep(SEARCH_DEBOUNCE_SEC)

    def type_search_term(self, term: str) -> None:
        open_dakota_sidebar(self.driver)
        self.clear_search()
        self._js(
            """
            const input = document.getElementById('crxjs-app')?.shadowRoot
                ?.querySelector('#company-search');
            if (!input) return false;
            input.focus();
            input.value = arguments[0];
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
            """,
            term,
        )
        time.sleep(SEARCH_DEBOUNCE_SEC)

    def wait_for_search_finished(self, timeout: int = DEFAULT_TIMEOUT) -> SearchTiming:
        start = time.perf_counter()

        def _done(_driver):
            state = self._js(
                """
                const root = document.getElementById('crxjs-app')?.shadowRoot;
                if (!root) return null;
                const loading = root.querySelector('.dakota-loading');
                if (loading && loading.offsetParent !== null) return null;
                const rows = root.querySelectorAll('.dakota-record-item');
                const noResults = root.querySelector('.dakota-no-results');
                const error = root.querySelector('.dakota-error');
                if (rows.length || (noResults && noResults.offsetParent !== null)
                    || (error && error.offsetParent !== null)) {
                    return {
                        count: rows.length,
                        hasLoadMore: !!root.querySelector('.dakota-load-more-button'),
                    };
                }
                return null;
                """
            )
            return state

        try:
            state = WebDriverWait(self.driver, timeout).until(_done)
        except TimeoutException as exc:
            raise TimeoutException("Timed out waiting for search results.") from exc

        return SearchTiming(
            elapsed_s=time.perf_counter() - start,
            result_count=int(state["count"]),
            has_load_more=bool(state["hasLoadMore"]),
        )

    def search_company(self, term: str, sample_number: int = 1) -> SearchTiming:
        if sample_number > 1:
            self.driver.get(DAKOTA_PORTAL_URL)
            self._wait_shadow()
            open_dakota_sidebar(self.driver)

        started = time.perf_counter()
        self.type_search_term(term)
        timing = self.wait_for_search_finished()
        return SearchTiming(
            elapsed_s=time.perf_counter() - started,
            result_count=timing.result_count,
            has_load_more=timing.has_load_more,
        )

    def get_first_result_info(self) -> tuple[str, str]:
        info = self._js(
            """
            const row = document.getElementById('crxjs-app')?.shadowRoot
                ?.querySelector('.dakota-record-item');
            if (!row) return null;
            const name = row.querySelector('.dakota-record-name, .dakota-record-title');
            const ctype = row.querySelector('.dakota-record-type');
            return {
                name: (name?.textContent || '').trim(),
                type: (ctype?.textContent || '').trim(),
            };
            """
        )
        if not info:
            pytest.fail("No search result row found to open.")
        return info["name"], info["type"]

    def click_first_search_result(self) -> tuple[str, str]:
        name, ctype = self.get_first_result_info()
        self._js(
            """
            const row = document.getElementById('crxjs-app')?.shadowRoot
                ?.querySelector('.dakota-record-item');
            if (row) row.click();
            """
        )
        return name, ctype

    def wait_for_company_detail(self, timeout: int = DEFAULT_TIMEOUT) -> float:
        start = time.perf_counter()
        WebDriverWait(self.driver, timeout).until(
            lambda d: self._js(
                """
                const root = document.getElementById('crxjs-app')?.shadowRoot;
                const header = root?.querySelector('.dakota-company-header');
                return !!(header && header.offsetParent !== null);
                """
            )
        )
        return time.perf_counter() - start

    def click_tab_by_name(self, tab_name: str) -> None:
        clicked = self._js(
            """
            const root = document.getElementById('crxjs-app')?.shadowRoot;
            const links = root?.querySelectorAll('.dakota-tab-button-container a') || [];
            for (const link of links) {
                if ((link.textContent || '').trim().includes(arguments[0])) {
                    link.click();
                    return true;
                }
            }
            return false;
            """,
            tab_name,
        )
        if not clicked:
            pytest.fail(f"Tab '{tab_name}' not found in extension.")

    def wait_for_contacts_loaded(self, timeout: int = DEFAULT_TIMEOUT) -> float:
        start = time.perf_counter()
        WebDriverWait(self.driver, timeout).until(
            lambda d: self._js(
                """
                const root = document.getElementById('crxjs-app')?.shadowRoot;
                const ready = root?.querySelector(
                    '.contacts-dakota-record-item, .contacts-dakota-no-results, '
                    + '.contacts-dakota-error, .dakota-contact-name'
                );
                const loading = root?.querySelector(
                    '.contacts-dakota-loading, .dakota-loading-contacts-text'
                );
                return !!(ready && ready.offsetParent !== null
                    && !(loading && loading.offsetParent !== null));
                """
            )
        )
        return time.perf_counter() - start

    def wait_for_tab_content(self, content_selector: str, timeout: int = DEFAULT_TIMEOUT) -> float:
        start = time.perf_counter()
        WebDriverWait(self.driver, timeout).until(
            lambda d: self._js(
                """
                const root = document.getElementById('crxjs-app')?.shadowRoot;
                const el = root?.querySelector(arguments[0]);
                const loading = root?.querySelector('.dakota-loading');
                return !!(el && el.offsetParent !== null
                    && !(loading && loading.offsetParent !== null));
                """,
                content_selector,
            )
        )
        return time.perf_counter() - start

    def scroll_and_click_load_more(self) -> float:
        revealed = self._js(
            """
            const root = document.getElementById('crxjs-app')?.shadowRoot;
            const body = root?.querySelector('.dakota-sidebar-body, .dakota-loggedin-body');
            const btn = root?.querySelector('.dakota-load-more-button');
            if (!btn || !body) return false;
            body.scrollTop = body.scrollHeight;
            btn.scrollIntoView({ block: 'center' });
            btn.click();
            return true;
            """
        )
        if not revealed:
            pytest.fail("Load More button not found.")

        start = time.perf_counter()
        WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
            lambda d: self._js(
                """
                const root = document.getElementById('crxjs-app')?.shadowRoot;
                const loading = root?.querySelector('.dakota-loading-more-text');
                if (loading && loading.offsetParent !== null) return false;
                const rows = root?.querySelectorAll('.dakota-record-item') || [];
                return rows.length > 10;
                """
            )
        )
        return time.perf_counter() - start

    def reset_to_search_home(self) -> None:
        self._js(
            """
            const root = document.getElementById('crxjs-app')?.shadowRoot;
            const close = root?.querySelector('.dakota-search-close-button');
            if (close) close.click();
            """
        )
        time.sleep(1)
        if not self._search_input_ready():
            self.driver.get(DAKOTA_PORTAL_URL)
            self._wait_shadow()
            open_dakota_sidebar(self.driver)

    # ------------------------------------------------------------------
    # Benchmark runners (one Excel row per test case)
    # ------------------------------------------------------------------

    def _write_test_case_result(
        self,
        test_case_key: str,
        companies: tuple[str, ...] | list[str],
        timings: list[float],
        benchmark_s: float,
    ) -> Path:
        metadata = get_search_report_metadata(self.driver)
        test_case = PERFORMANCE_TEST_CASE_LABELS[test_case_key]
        row, summary = build_test_case_summary_row(
            test_case, companies, timings, benchmark_s, metadata
        )
        report = append_test_case_result(get_performance_report_path(), row)
        self._assert_summary(summary, report)
        return report

    def run_search_benchmark(self, terms, iterations: int, benchmark_s: float) -> Path:
        all_timings: list[float] = []

        for term in terms:
            for sample in range(1, iterations + 1):
                timing = self.search_company(term, sample_number=sample)
                all_timings.append(timing.elapsed_s)
                print(
                    f"[Search] {term} sample {sample}: {timing.elapsed_s:.3f}s "
                    f"({timing.result_count} results)"
                )

        return self._write_test_case_result("company_search", terms, all_timings, benchmark_s)

    def run_detail_load_benchmark(self, terms, iterations: int, benchmark_s: float) -> Path:
        all_timings: list[float] = []

        for term in terms:
            for sample in range(1, iterations + 1):
                if sample == 1:
                    self.reset_to_search_home()
                self.search_company(term, sample_number=sample)
                started = time.perf_counter()
                name, ctype = self.click_first_search_result()
                elapsed = self.wait_for_company_detail()
                total = time.perf_counter() - started
                all_timings.append(total)
                print(f"[Detail] {term} sample {sample}: {name} in {total:.3f}s")
                time.sleep(VISIBILITY_PAUSE_SEC)
                self.reset_to_search_home()

        return self._write_test_case_result("company_detail", terms, all_timings, benchmark_s)

    def run_contacts_load_benchmark(self, terms, iterations: int, benchmark_s: float) -> Path:
        all_timings: list[float] = []

        for term in terms:
            for sample in range(1, iterations + 1):
                if sample == 1:
                    self.reset_to_search_home()
                self.search_company(term, sample_number=sample)
                name, ctype = self.click_first_search_result()
                self.wait_for_company_detail()
                time.sleep(VISIBILITY_PAUSE_SEC)
                started = time.perf_counter()
                self.click_tab_by_name("Contacts")
                elapsed = self.wait_for_contacts_loaded()
                total = time.perf_counter() - started
                all_timings.append(total)
                print(f"[Contacts] {term} sample {sample}: {name} in {total:.3f}s")
                time.sleep(VISIBILITY_PAUSE_SEC)
                self.reset_to_search_home()

        return self._write_test_case_result("company_contacts", terms, all_timings, benchmark_s)

    def run_tab_load_benchmark(self, terms, iterations: int, benchmark_s: float) -> Path:
        tab_content_selectors = {
            "Platform Details": ".dakota-platform-info-item",
            "Investment Details": ".dakota-investment-details-item",
            "Investors": ".dakota-investor-item",
            "Earnings Events": ".dakota-earning-event-item",
        }
        all_timings: list[float] = []

        for term in terms:
            for sample in range(1, iterations + 1):
                if sample == 1:
                    self.reset_to_search_home()
                self.search_company(term, sample_number=sample)
                name, ctype = self.click_first_search_result()
                self.wait_for_company_detail()
                tab = profile_tab_for_company_type(ctype)
                if not tab:
                    pytest.fail(f"Unknown company type '{ctype}' for term '{term}'.")
                time.sleep(VISIBILITY_PAUSE_SEC)
                started = time.perf_counter()
                self.click_tab_by_name(tab)
                elapsed = self.wait_for_tab_content(tab_content_selectors[tab])
                total = time.perf_counter() - started
                all_timings.append(total)
                print(f"[Tab] {term} sample {sample}: {name}->{tab} in {total:.3f}s")
                time.sleep(VISIBILITY_PAUSE_SEC)
                self.reset_to_search_home()

        return self._write_test_case_result("company_type_tab", terms, all_timings, benchmark_s)

    def run_load_more_benchmark(self, terms, iterations: int, benchmark_s: float) -> Path:
        all_timings: list[float] = []

        for term in terms:
            for sample in range(1, iterations + 1):
                if sample == 1:
                    self.reset_to_search_home()
                search = self.search_company(term, sample_number=sample)
                if not search.has_load_more or search.result_count < 10:
                    print(f"[Load more] {term} sample {sample}: skipped (no more pages)")
                    continue
                elapsed = self.scroll_and_click_load_more()
                all_timings.append(elapsed)
                print(f"[Load more] {term} sample {sample}: {elapsed:.3f}s")
                self.reset_to_search_home()

        return self._write_test_case_result("search_load_more", terms, all_timings, benchmark_s)

    @staticmethod
    def _assert_summary(summary: SearchSummary, report: Path) -> None:
        if summary.result == "FAIL":
            pytest.fail(
                f"Performance benchmark exceeded for '{summary.test_case}' "
                f"(avg {summary.average_time_s:.3f}s > {summary.benchmark_s:.3f}s). "
                f"Report: {report}"
            )
