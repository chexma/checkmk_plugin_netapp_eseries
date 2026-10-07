from collections import namedtuple

import pytest
from cmk.password_store.v1_unstable import Secret
from cmk.password_store.v1_unstable import _impl as password_store_impl
from cmk_addons.plugins.netapp_eseries.lib import parse_netapp_eseries
from cmk_addons.plugins.netapp_eseries.special_agents import agent_netappeseries as agent

Section = namedtuple("Section", ["name", "uri", "perfdata_uri", "perfdata_identifier"])

HOST = "eseries.example.com"
BASE_URL = f"https://{HOST}:8443/devmgr/v2/storage-systems/1"


# Arguments and password


def test_parse_arguments_defaults():
    args = agent.parse_arguments(["-u", "monitor", "-s", "geheim", HOST])
    assert args.user == "monitor"
    assert args.host == HOST
    assert args.proto == "https"
    assert args.port == 8443
    assert args.system_id == 1
    assert args.verify_ssl is False
    assert "volumes" in args.sections
    # The plaintext password is wrapped, so it doesn't end up in logs
    assert "geheim" not in repr(args)


def test_parse_arguments_sections_are_a_list():
    args = agent.parse_arguments(["-u", "monitor", "-s", "x", "--sections", "system,drives", HOST])
    assert args.sections == ["system", "drives"]
    # was a substring match on the raw string before
    assert "sys" not in args.sections


def test_parse_arguments_password_required(capsys):
    with pytest.raises(SystemExit):
        agent.parse_arguments(["-u", "monitor", HOST])
    assert "--password-id" in capsys.readouterr().err


def test_parse_arguments_password_options_exclusive():
    with pytest.raises(SystemExit):
        agent.parse_arguments(["-u", "monitor", "-s", "x", "--password-id", "a:b", HOST])


def test_session_with_plaintext_password():
    session = agent.get_session(agent.parse_arguments(["-u", "monitor", "-s", "geheim", HOST]))
    assert session.auth == ("monitor", "geheim")


def test_session_with_password_store(tmp_path, monkeypatch):
    """--password-id is what the server side calls pass: <id>:<password store file>"""
    store_key = Secret(b"0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(password_store_impl, "_read_store_secret", lambda: store_key)
    store_file = tmp_path / "passwords_merged"
    store_file.write_bytes(
        password_store_impl.PasswordStore(store_key).dump_bytes({"eseries": Secret("geheim")})
    )

    args = agent.parse_arguments(["-u", "monitor", "--password-id", f"eseries:{store_file}", HOST])
    assert agent.get_session(args).auth == ("monitor", "geheim")


# Data processing


def test_add_perfdata_to_section_data():
    section = Section("volumes", "/volumes", "/analysed-volume-statistics", "volumeId")
    data = [{"id": "v1"}, {"id": "v2"}]
    perfdata = [{"volumeId": "v1", "readIOps": 1.5}, {"volumeId": "other"}]
    result = agent.add_perfdata_to_section_data(section, data, perfdata)
    assert result[0]["performance"] == {"volumeId": "v1", "readIOps": 1.5}
    assert "performance" not in result[1]


def test_add_perfdata_interfaces_use_interface_ref():
    section = Section("interfaces", "/interfaces", "/x", "interfaceId")
    data = [{"interfaceRef": "if1"}]
    result = agent.add_perfdata_to_section_data(section, data, [{"interfaceId": "if1"}])
    assert result[0]["performance"] == {"interfaceId": "if1"}


IDS = {"ctrlA": "A", "ctrlB": "B", "tray0": 0, "drawer1": 1}


@pytest.mark.parametrize(
    "name, item, expected",
    [
        ("volumes", {"label": "vol1"}, "vol1"),
        ("pools", {"label": "pool1"}, "pool1"),
        ("system", {"name": "2800"}, "2800"),
        ("controllers", {"physicalLocation": {"label": "A"}}, "A"),
        ("trays", {"trayId": 99}, "99"),
        (
            "drives",
            {"physicalLocation": {"trayRef": "tray0", "drawerRef": None, "slot": 7}},
            "0-7",
        ),
        (
            "fans",
            {"physicalLocation": {"trayRef": "tray0", "slot": 2}},
            "Tray 0-2",
        ),
        (
            "batteries",
            {"physicalLocation": {"trayRef": None, "drawerRef": "drawer1", "slot": 1}},
            "Drawer 1-1",
        ),
        (
            "interfaces",
            {
                "controllerRef": "ctrlB",
                "ioInterfaceTypeData": {"interfaceType": "fc", "fibre": {"channel": 3}},
            },
            "FC B-3",
        ),
        (
            "interfaces",
            {
                "controllerRef": "ctrlA",
                "ioInterfaceTypeData": {"interfaceType": "iscsi", "iscsi": {"channel": 1}},
            },
            "ISCSI A-1",
        ),
    ],
)
def test_checkmk_item_identifier(name, item, expected):
    section = Section(name, None, None, None)
    result = agent.add_checkmk_item_identifier(section, IDS, [item])
    assert result[0]["checkmk_item_identifier"] == expected


def test_handle_output_keeps_first_duplicate(capsys):
    agent.handle_output(
        [
            {"checkmk_item_identifier": "A ", "n": 1},
            {"checkmk_item_identifier": "A", "n": 2},
        ]
    )
    parsed = parse_netapp_eseries([[capsys.readouterr().out.strip()]])
    assert list(parsed) == ["A"]
    assert parsed["A"]["n"] == 1


# Complete agent run against a fake REST API


def _location(label, slot=1, tray="tray0"):
    return {"label": label, "slot": slot, "trayRef": tray, "drawerRef": None}


CONTROLLERS = [
    {
        "id": "c1",
        "controllerRef": "ctrlA",
        "status": "optimal",
        "physicalLocation": _location("A"),
    },
    {
        "id": "c2",
        "controllerRef": "ctrlB",
        "status": "optimal",
        "physicalLocation": _location("B", 2),
    },
]
INVENTORY = {
    "drawers": [],
    "trays": [{"trayRef": "tray0", "trayId": 0}],
    "esms": [],
    "batteries": [],
    "fans": [
        {"fanRef": "fan1", "status": "optimal", "physicalLocation": _location("", 1)},
        {"fanRef": "fan2", "status": "failed", "physicalLocation": _location("", 2)},
    ],
    "powerSupplies": [],
    "thermalSensors": [],
}
SYSTEM = {"id": "1", "name": "2800", "status": "optimal"}
VOLUMES = [{"id": "v1", "label": "vol1"}, {"id": "v2", "label": "vol2"}]


@pytest.fixture
def api(requests_mock):
    requests_mock.get(BASE_URL, json=SYSTEM)
    requests_mock.get(BASE_URL + "/", json=SYSTEM)
    requests_mock.get(BASE_URL + "/controllers", json=CONTROLLERS)
    requests_mock.get(BASE_URL + "/hardware-inventory", json=INVENTORY)
    requests_mock.get(BASE_URL + "/volumes", json=VOLUMES)
    # New statistics endpoint for volumes ...
    requests_mock.get(
        BASE_URL + "/analyzed/volume-statistics",
        json={"statistics": [{"volumeId": "v1", "readIOps": 10.0}]},
    )
    # ... old one for the system (new one missing on older firmware)
    requests_mock.get(BASE_URL + "/analyzed/system-statistics", status_code=404)
    requests_mock.get(
        BASE_URL + "/analysed-system-statistics",
        json={"storageSystemId": "1", "readIOps": 5.0},
    )
    # Not enough samples yet
    requests_mock.get(BASE_URL + "/analyzed/controller-statistics", status_code=422)
    return requests_mock


def _sections(output: str) -> dict[str, dict]:
    lines = output.splitlines()
    return {
        header.strip("<>").split(":")[0]: parse_netapp_eseries([[payload]])
        for header, payload in zip(lines[::2], lines[1::2])
    }


def test_agent_run(api, capsys):
    argv = ["-u", "monitor", "-s", "geheim", "--sections", "system,volumes,controllers,fans", HOST]
    assert agent.main(argv) == 0

    sections = _sections(capsys.readouterr().out)
    assert list(sections) == [
        "netapp_eseries_controllers",
        "netapp_eseries_fans",
        "netapp_eseries_system",
        "netapp_eseries_volumes",
    ]
    assert sections["netapp_eseries_volumes"]["vol1"]["performance"]["readIOps"] == 10.0
    assert "performance" not in sections["netapp_eseries_volumes"]["vol2"]
    assert sections["netapp_eseries_system"]["2800"]["performance"]["readIOps"] == 5.0
    assert set(sections["netapp_eseries_controllers"]) == {"A", "B"}
    assert "performance" not in sections["netapp_eseries_controllers"]["A"]
    assert set(sections["netapp_eseries_fans"]) == {"Tray 0-1", "Tray 0-2"}

    assert api.last_request.headers["Authorization"].startswith("Basic ")


def test_agent_connection_error(requests_mock, capsys):
    requests_mock.get(BASE_URL, status_code=401)
    with pytest.raises(SystemExit) as exc:
        agent.main(["-u", "monitor", "-s", "falsch", HOST])
    assert exc.value.code == 1
    assert "401" in capsys.readouterr().err
