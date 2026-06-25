"""Dakota company-type profile tab load performance — Selenium."""

import pytest

from utils.performance_config import (
    DAKOTA_CRITERIA_TAB_LOAD_PERFORMANCE_BENCHMARK_SEC,
    DAKOTA_SEARCH_ITERATIONS,
    DAKOTA_TAB_LOAD_TEST_TERMS,
)

pytestmark = [pytest.mark.performance, pytest.mark.extension]


def test_company_type_specific_tab_loading_time(dakota_performance):
    """Open first result and measure the tab that matches the company type."""
    dakota_performance.run_tab_load_benchmark(
        DAKOTA_TAB_LOAD_TEST_TERMS,
        DAKOTA_SEARCH_ITERATIONS,
        DAKOTA_CRITERIA_TAB_LOAD_PERFORMANCE_BENCHMARK_SEC,
    )
