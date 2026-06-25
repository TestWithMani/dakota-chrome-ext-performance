"""Performance test settings — companies, benchmarks, and iteration counts."""

import os
from pathlib import Path

# How many times each company/term is measured per test
DAKOTA_SEARCH_ITERATIONS = 3

# Company names per benchmark (same as your previous project)
DAKOTA_SEARCH_TEST_TERMS = ("Microsoft", "KPMG")
DAKOTA_DETAIL_LOAD_TEST_TERMS = ("Microsoft", "KPMG")
DAKOTA_CONTACTS_LOAD_TEST_TERMS = ("Cloudera", "Thoma Bravo")
DAKOTA_TAB_LOAD_TEST_TERMS = ("Databricks", "Plaid")
DAKOTA_LOAD_MORE_TEST_TERMS = ("Microsoft", "KPMG")

# Max allowed average time (seconds) — test fails if exceeded
DAKOTA_SEARCH_PERFORMANCE_BENCHMARK_SEC = 10
DAKOTA_LOAD_MORE_PERFORMANCE_BENCHMARK_SEC = 10
DAKOTA_DETAIL_LOAD_PERFORMANCE_BENCHMARK_SEC = 5
DAKOTA_CONTACTS_LOAD_PERFORMANCE_BENCHMARK_SEC = 5
DAKOTA_CRITERIA_TAB_LOAD_PERFORMANCE_BENCHMARK_SEC = 5

# Company type on search result -> profile tab to open
ACCOUNT_CRITERIA_TO_PROFILE_TAB = {
    "allocator": "Platform Details",
    "firm": "Investment Details",
    "private": "Investors",
    "public": "Earnings Events",
}


def profile_tab_for_company_type(company_type: str) -> str | None:
    return ACCOUNT_CRITERIA_TO_PROFILE_TAB.get(company_type.strip().casefold())


PERFORMANCE_REPORT_TEST_NAMES = frozenset({
    "test_dakota_search_time",
    "test_company_detail_loading_time",
    "test_company_contacts_loading_time",
    "test_company_type_specific_tab_loading_time",
    "test_search_load_more_time",
})
