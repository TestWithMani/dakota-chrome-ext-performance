"""Dakota company search performance — Selenium + portal login."""

import pytest

from utils.performance_config import (
    DAKOTA_SEARCH_ITERATIONS,
    DAKOTA_SEARCH_PERFORMANCE_BENCHMARK_SEC,
    DAKOTA_SEARCH_TEST_TERMS,
)

pytestmark = [pytest.mark.performance, pytest.mark.extension]


def test_dakota_search_time(dakota_performance):
    """Measure how long each company search takes in the extension."""
    dakota_performance.run_search_benchmark(
        DAKOTA_SEARCH_TEST_TERMS,
        DAKOTA_SEARCH_ITERATIONS,
        DAKOTA_SEARCH_PERFORMANCE_BENCHMARK_SEC,
    )
