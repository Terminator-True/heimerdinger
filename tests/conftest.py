"""Root pytest configuration for the equivalence harness.

Registers the `--snapshot-update` flag used by tests/test_equivalence.py to
regenerate snapshots from current (pre/post extraction) output.
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        help="Regenerate equivalence snapshots from current output.",
    )


@pytest.fixture
def snapshot_update(request):
    return request.config.getoption("--snapshot-update")
