from cmk.agent_based.v2 import Service
from cmk_addons.plugins.netapp_eseries.lib import (
    discovery_netapp_eseries_multiple,
    parse_netapp_eseries,
)


def test_parse_python_dict_literal():
    string_table = [["{'A': {'status': 'optimal', 'offline': False, 'size': None}}"]]
    assert parse_netapp_eseries(string_table) == {
        "A": {"status": "optimal", "offline": False, "size": None}
    }


def test_parse_empty_section():
    assert parse_netapp_eseries([["{}"]]) == {}


def test_discovery_one_service_per_item():
    section = {"0-1": {}, "0-2": {}}
    assert list(discovery_netapp_eseries_multiple(section)) == [
        Service(item="0-1"),
        Service(item="0-2"),
    ]


def test_sample_contains_all_sections(sample_sections):
    assert set(sample_sections) == {
        f"netapp_eseries_{name}"
        for name in (
            "batteries",
            "controllers",
            "drawers",
            "drives",
            "esms",
            "fans",
            "interfaces",
            "pools",
            "powersupplies",
            "system",
            "thermalsensors",
            "trays",
            "volumes",
        )
    }
