"""Shared fixtures: parsed sections from canned special agent output.

tests/data/simulator_sample.txt holds a few items per section (one per drive media
type and interface type) taken from the SANtricity simulator outputs in temp/.
"""

import copy
from pathlib import Path

import pytest
from cmk_addons.plugins.netapp_eseries.lib import parse_netapp_eseries

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_FILE = DATA_DIR / "simulator_sample.txt"


def load_agent_output(path: Path) -> dict[str, dict]:
    """Agent output file -> {section name: parsed section}"""
    sections = {}
    lines = path.read_text().splitlines()
    for header, payload in zip(lines[::2], lines[1::2]):
        name = header.strip("<>").split(":")[0]
        sections[name] = parse_netapp_eseries([[payload]])
    return sections


_SAMPLE = load_agent_output(SAMPLE_FILE)


@pytest.fixture
def sample_sections() -> dict[str, dict]:
    # Some checks modify the section data (drive temperature), so hand out a copy
    return copy.deepcopy(_SAMPLE)


@pytest.fixture
def value_store(monkeypatch) -> dict:
    """Replace get_value_store() in the plugins that use it (outside of a check context)"""
    store: dict = {}
    from cmk_addons.plugins.netapp_eseries.agent_based import (
        netapp_eseries_drives,
        netapp_eseries_pools,
    )

    for module in (netapp_eseries_drives, netapp_eseries_pools):
        monkeypatch.setattr(module, "get_value_store", lambda: store)
    return store
