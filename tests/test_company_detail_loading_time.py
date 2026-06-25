"""Dakota company detail load performance — Selenium."""

import pytest

from utils.performance_config import (
    DAKOTA_DETAIL_LOAD_PERFORMANCE_BENCHMARK_SEC,
    DAKOTA_DETAIL_LOAD_TEST_TERMS,
    DAKOTA_SEARCH_ITERATIONS,
)

pytestmark = [pytest.mark.performance, pytest.mark.extension]


def test_company_detail_loading_time(dakota_performance):
    """Search a company, open the first result, measure detail view load time."""
    dakota_performance.run_detail_load_benchmark(
        DAKOTA_DETAIL_LOAD_TEST_TERMS,
        DAKOTA_SEARCH_ITERATIONS,
        DAKOTA_DETAIL_LOAD_PERFORMANCE_BENCHMARK_SEC,
    )
