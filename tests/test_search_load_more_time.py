"""Dakota search Load More performance — Selenium."""

import pytest

from utils.performance_config import (
    DAKOTA_LOAD_MORE_PERFORMANCE_BENCHMARK_SEC,
    DAKOTA_LOAD_MORE_TEST_TERMS,
    DAKOTA_SEARCH_ITERATIONS,
)

pytestmark = [pytest.mark.performance, pytest.mark.extension]


def test_search_load_more_time(dakota_performance):
    """Search companies that support Load More and measure extra page load time."""
    dakota_performance.run_load_more_benchmark(
        DAKOTA_LOAD_MORE_TEST_TERMS,
        DAKOTA_SEARCH_ITERATIONS,
        DAKOTA_LOAD_MORE_PERFORMANCE_BENCHMARK_SEC,
    )
