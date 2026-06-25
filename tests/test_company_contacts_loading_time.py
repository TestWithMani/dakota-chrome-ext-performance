"""Dakota company contacts tab load performance — Selenium."""

import pytest

from utils.performance_config import (
    DAKOTA_CONTACTS_LOAD_PERFORMANCE_BENCHMARK_SEC,
    DAKOTA_CONTACTS_LOAD_TEST_TERMS,
    DAKOTA_SEARCH_ITERATIONS,
)

pytestmark = [pytest.mark.performance, pytest.mark.extension]


def test_company_contacts_loading_time(dakota_performance):
    """Open first search result, click Contacts tab, measure load time."""
    dakota_performance.run_contacts_load_benchmark(
        DAKOTA_CONTACTS_LOAD_TEST_TERMS,
        DAKOTA_SEARCH_ITERATIONS,
        DAKOTA_CONTACTS_LOAD_PERFORMANCE_BENCHMARK_SEC,
    )
