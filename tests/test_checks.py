import copy
import time

import pytest
from cmk.agent_based.v2 import Metric, Result, State
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_batteries import (
    check_netapp_eseries_batteries,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_controllers import (
    check_netapp_eseries_controllers,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_drawers import (
    check_netapp_eseries_drawers,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_drives import (
    check_netapp_eseries_drives,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_esms import (
    check_netapp_eseries_esms,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_fans import (
    check_netapp_eseries_fans,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_interfaces import (
    check_netapp_eseries_interfaces,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_pools import (
    FILESYSTEM_DEFAULT_PARAMS,
    check_netapp_eseries_pools,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_powersupplies import (
    check_netapp_eseries_powersupplies,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_system import (
    check_netapp_eseries_system,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_thermalsensors import (
    check_netapp_eseries_thermalsensors,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_trays import (
    check_netapp_eseries_trays,
)
from cmk_addons.plugins.netapp_eseries.agent_based.netapp_eseries_volumes import (
    check_netapp_eseries_volumes,
)


def _run(check, item, section, params=None):
    if params is None:
        return list(check(item=item, section=section))
    return list(check(item=item, params=params, section=section))


# section name -> (check function, params or None if the check takes no params)
CHECKS = {
    "netapp_eseries_batteries": (check_netapp_eseries_batteries, None),
    "netapp_eseries_controllers": (check_netapp_eseries_controllers, None),
    "netapp_eseries_drawers": (check_netapp_eseries_drawers, None),
    "netapp_eseries_drives": (check_netapp_eseries_drives, {}),
    "netapp_eseries_esms": (check_netapp_eseries_esms, None),
    "netapp_eseries_fans": (check_netapp_eseries_fans, None),
    "netapp_eseries_interfaces": (check_netapp_eseries_interfaces, None),
    "netapp_eseries_pools": (check_netapp_eseries_pools, FILESYSTEM_DEFAULT_PARAMS),
    "netapp_eseries_powersupplies": (check_netapp_eseries_powersupplies, None),
    "netapp_eseries_system": (check_netapp_eseries_system, None),
    "netapp_eseries_thermalsensors": (check_netapp_eseries_thermalsensors, None),
    "netapp_eseries_trays": (check_netapp_eseries_trays, None),
    "netapp_eseries_volumes": (check_netapp_eseries_volumes, None),
}


def _seed_pool_trend(value_store, section):
    """The size trend needs a previous value (Checkmk initializes it on the first run)"""
    for item, data in section.items():
        used_mb = (int(data["totalRaidedSpace"]) - int(data["freeSpace"])) / 1024**2
        value_store[f"{item}.delta"] = (time.time() - 3600, used_mb)


def _states(results):
    return [r.state for r in results if isinstance(r, Result)]


def _metrics(results):
    return {m.name: m.value for m in results if isinstance(m, Metric)}


def _summary(results):
    return ", ".join(r.summary for r in results if isinstance(r, Result))


@pytest.mark.parametrize("section_name", sorted(CHECKS))
def test_all_sample_items(section_name, sample_sections, value_store):
    """Every item of the simulator sample can be checked and yields a result"""
    check, params = CHECKS[section_name]
    section = sample_sections[section_name]
    if section_name == "netapp_eseries_pools":
        _seed_pool_trend(value_store, section)
    for item in section:
        results = _run(check, item, section, params)
        assert any(isinstance(r, Result) for r in results), item


@pytest.mark.parametrize("section_name", sorted(CHECKS))
def test_vanished_item(section_name, value_store):
    check, params = CHECKS[section_name]
    assert _run(check, "does-not-exist", {}, params) == []


def _item(sample_sections, section_name, item):
    return copy.deepcopy(sample_sections[section_name][item])


# Volumes


def test_volume_optimal_with_metrics(sample_sections):
    section = sample_sections["netapp_eseries_volumes"]
    results = _run(check_netapp_eseries_volumes, "1", section)
    assert State.worst(*_states(results)) == State.OK
    assert "raidlevel: raid6, status: optimal" in _summary(results)
    assert {
        "disk_read_ios",
        "disk_write_ios",
        "disk_read_throughput",
        "disk_write_throughput",
        "read_latency",
        "write_latency",
    } <= set(_metrics(results))


def test_volume_degraded(sample_sections):
    data = _item(sample_sections, "netapp_eseries_volumes", "1")
    data["status"] = "degraded"
    results = _run(check_netapp_eseries_volumes, "1", {"1": data})
    assert _states(results)[0] == State.WARN


def test_volume_offline_no_metrics(sample_sections):
    data = _item(sample_sections, "netapp_eseries_volumes", "1")
    data["offline"] = True
    results = _run(check_netapp_eseries_volumes, "1", {"1": data})
    assert _states(results)[0] == State.CRIT
    assert "OFFLINE" in _summary(results)
    assert _metrics(results) == {}


def test_volume_latency_in_seconds(sample_sections):
    data = _item(sample_sections, "netapp_eseries_volumes", "1")
    data["performance"]["readResponseTime"] = 2.5  # ms
    metrics = _metrics(_run(check_netapp_eseries_volumes, "1", {"1": data}))
    assert metrics["read_latency"] == pytest.approx(0.0025)


# Drives


def test_drive_optimal(sample_sections, value_store):
    section = sample_sections["netapp_eseries_drives"]
    item = next(iter(section))
    results = _run(check_netapp_eseries_drives, item, section, {})
    assert State.worst(*_states(results)) == State.OK
    assert f"Drive {item}, status: optimal" in _summary(results)
    assert "disk_read_ios" in _metrics(results)


def test_drive_offline(sample_sections, value_store):
    data = _item(sample_sections, "netapp_eseries_drives", "0-7")
    data["offline"] = True
    results = _run(check_netapp_eseries_drives, "0-7", {"0-7": data}, {})
    assert _states(results)[0] == State.CRIT
    assert "is OFFLINE" in _summary(results)
    assert "disk_read_ios" not in _metrics(results)


def test_drive_degraded_channel(sample_sections, value_store):
    data = _item(sample_sections, "netapp_eseries_drives", "0-7")
    data["hasDegradedChannel"] = True
    results = _run(check_netapp_eseries_drives, "0-7", {"0-7": data}, {})
    assert State.CRIT in _states(results)
    assert "degraded Channel" in _summary(results)


def test_drive_failed_temperature_255(sample_sections, value_store):
    data = _item(sample_sections, "netapp_eseries_drives", "0-7")
    data["driveTemperature"]["currentTemp"] = 255
    results = _run(check_netapp_eseries_drives, "0-7", {"0-7": data}, {})
    assert _metrics(results)["temp"] == 0


def test_drive_temperature_levels(sample_sections, value_store):
    data = _item(sample_sections, "netapp_eseries_drives", "0-7")
    data["driveTemperature"]["currentTemp"] = 60
    results = _run(check_netapp_eseries_drives, "0-7", {"0-7": data}, {"levels": (50.0, 55.0)})
    assert _metrics(results)["temp"] == 60
    assert State.CRIT in _states(results)


def test_drive_ssd_wear_metrics(sample_sections, value_store):
    section = sample_sections["netapp_eseries_drives"]
    item = next(k for k, v in section.items() if v["driveMediaType"] == "ssd")
    metrics = _metrics(_run(check_netapp_eseries_drives, item, section, {}))
    assert {"endurance", "spareBlocks", "erase"} <= set(metrics)


# Pools


def test_pool_complete(sample_sections, value_store):
    section = sample_sections["netapp_eseries_pools"]
    _seed_pool_trend(value_store, section)
    results = _run(check_netapp_eseries_pools, "test", section, FILESYSTEM_DEFAULT_PARAMS)
    assert _states(results)[0] == State.OK
    assert "fs_used" in _metrics(results)


@pytest.mark.parametrize(
    "changes, state",
    [
        ({"state": "degraded"}, State.WARN),
        ({"raidStatus": "degraded"}, State.WARN),
        ({"offline": True}, State.CRIT),
    ],
)
def test_pool_status(sample_sections, value_store, changes, state):
    data = _item(sample_sections, "netapp_eseries_pools", "test")
    data.update(changes)
    _seed_pool_trend(value_store, {"test": data})
    results = _run(check_netapp_eseries_pools, "test", {"test": data}, FILESYSTEM_DEFAULT_PARAMS)
    assert _states(results)[0] == state


def test_pool_usage_levels(sample_sections, value_store):
    data = _item(sample_sections, "netapp_eseries_pools", "test")
    data["freeSpace"] = str(int(data["totalRaidedSpace"]) // 100)  # 99 % used
    _seed_pool_trend(value_store, {"test": data})
    results = _run(check_netapp_eseries_pools, "test", {"test": data}, FILESYSTEM_DEFAULT_PARAMS)
    assert State.CRIT in _states(results)


# Batteries


@pytest.mark.parametrize(
    "status, state",
    [
        ("optimal", State.OK),
        ("learning", State.OK),
        ("maintenanceCharging", State.OK),
        ("removed", State.WARN),
        ("failed", State.WARN),
    ],
)
def test_battery_status(sample_sections, status, state):
    data = _item(sample_sections, "netapp_eseries_batteries", "Tray 0-2")
    data["status"] = status
    results = _run(check_netapp_eseries_batteries, "Tray 0-2", {"Tray 0-2": data})
    assert _states(results)[0] == state


# Interfaces


def test_interface_sas_driveside(sample_sections):
    section = sample_sections["netapp_eseries_interfaces"]
    results = _run(check_netapp_eseries_interfaces, "SAS A-1", section)
    assert _states(results)[0] == State.OK
    assert "Port status: optimal" in _summary(results)


def test_interface_sas_degraded(sample_sections):
    data = _item(sample_sections, "netapp_eseries_interfaces", "SAS A-1")
    data["ioInterfaceTypeData"]["sas"]["isDegraded"] = True
    results = _run(check_netapp_eseries_interfaces, "SAS A-1", {"SAS A-1": data})
    assert _states(results)[0] == State.WARN


def test_interface_sas_not_optimal(sample_sections):
    data = _item(sample_sections, "netapp_eseries_interfaces", "SAS A-1")
    data["ioInterfaceTypeData"]["sas"]["iocPort"]["state"] = "failed"
    results = _run(check_netapp_eseries_interfaces, "SAS A-1", {"SAS A-1": data})
    assert _states(results)[0] == State.WARN
    assert "Port status: failed" in _summary(results)


def test_interface_fc_down_no_metrics(sample_sections):
    section = sample_sections["netapp_eseries_interfaces"]
    results = _run(check_netapp_eseries_interfaces, "FC B-1", section)
    assert _states(results)[0] == State.WARN
    assert "Port status: down" in _summary(results)
    assert _metrics(results) == {}


def test_interface_fc_up(sample_sections):
    data = _item(sample_sections, "netapp_eseries_interfaces", "FC B-1")
    data["ioInterfaceTypeData"]["fibre"]["linkStatus"] = "up"
    results = _run(check_netapp_eseries_interfaces, "FC B-1", {"FC B-1": data})
    assert State.worst(*_states(results)) == State.OK
    assert "disk_read_throughput" in _metrics(results)


@pytest.mark.parametrize("item", ["IB A-1", "PCIE A-1"])
def test_interface_other_types_ok(sample_sections, item):
    results = _run(
        check_netapp_eseries_interfaces, item, sample_sections["netapp_eseries_interfaces"]
    )
    assert _states(results)[0] == State.OK


# Controllers and system


def test_controller_metrics(sample_sections):
    section = sample_sections["netapp_eseries_controllers"]
    results = _run(check_netapp_eseries_controllers, "A", section)
    assert _states(results) == [State.OK]
    assert {"util", "fullStripeWrites", "read_latency"} <= set(_metrics(results))


def test_controller_not_optimal(sample_sections):
    data = _item(sample_sections, "netapp_eseries_controllers", "A")
    data["status"] = "offline"
    assert _states(_run(check_netapp_eseries_controllers, "A", {"A": data})) == [State.WARN]


def test_system(sample_sections):
    section = sample_sections["netapp_eseries_system"]
    results = _run(check_netapp_eseries_system, "2800", section)
    assert State.worst(*_states(results)) == State.OK
    assert "status: optimal" in _summary(results)
    assert "disk_read_ios" in _metrics(results)


def test_system_needs_attention(sample_sections):
    data = _item(sample_sections, "netapp_eseries_system", "2800")
    data["status"] = "needsAttn"
    assert _states(_run(check_netapp_eseries_system, "2800", {"2800": data}))[0] == State.WARN


# Simple hardware components: WARN unless optimal


@pytest.mark.parametrize(
    "section_name, check",
    [
        ("netapp_eseries_esms", check_netapp_eseries_esms),
        ("netapp_eseries_fans", check_netapp_eseries_fans),
        ("netapp_eseries_powersupplies", check_netapp_eseries_powersupplies),
        ("netapp_eseries_thermalsensors", check_netapp_eseries_thermalsensors),
        ("netapp_eseries_drawers", check_netapp_eseries_drawers),
    ],
)
def test_hardware_status(sample_sections, section_name, check):
    section = sample_sections[section_name]
    item = next(iter(section))
    assert _states(_run(check, item, section)) == [State.OK]

    data = copy.deepcopy(section[item])
    data["status"] = "failed"
    assert _states(_run(check, item, {item: data}))[0] == State.WARN


def test_drawer_open(sample_sections):
    data = _item(sample_sections, "netapp_eseries_drawers", "3")
    data["isOpen"] = True
    results = _run(check_netapp_eseries_drawers, "3", {"3": data})
    assert _states(results) == [State.OK, State.WARN]
    assert "Drawer is open" in _summary(results)


# Trays


def test_tray_ok(sample_sections):
    results = _run(check_netapp_eseries_trays, "0", sample_sections["netapp_eseries_trays"])
    assert _states(results) == [State.OK]
    assert "Tray ID 0, type: de5600 with 24 slots" in _summary(results)


def test_tray_error_flag(sample_sections):
    data = _item(sample_sections, "netapp_eseries_trays", "0")
    data["esmMiswire"] = True
    results = _run(check_netapp_eseries_trays, "0", {"0": data})
    assert State.WARN in _states(results)
    assert "esmMiswire" in _summary(results)
