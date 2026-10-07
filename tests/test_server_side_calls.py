from cmk.server_side_calls.v1 import HostConfig, IPv4Config, Secret
from cmk_addons.plugins.netapp_eseries.server_side_calls.special_agent import (
    special_agent_netapp_eseries,
)

HOST_CONFIG = HostConfig(name="eseries", ipv4_config=IPv4Config(address="192.0.2.10"))
PASSWORD = Secret(23)


def _arguments(params, host_config=HOST_CONFIG):
    (command,) = special_agent_netapp_eseries(params, host_config)
    return command.command_arguments


def test_name_matches_ruleset_and_executable():
    # rule spec SpecialAgent(name="netappeseries"), libexec/agent_netappeseries
    assert special_agent_netapp_eseries.name == "netappeseries"


def test_minimal_rule():
    assert _arguments({"user": "monitor", "password": PASSWORD}) == [
        "-u",
        "monitor",
        "--password-id",
        PASSWORD,
        "192.0.2.10",
    ]


def test_all_options():
    params = {
        "user": "monitor",
        "password": PASSWORD,
        "port": 8080,
        "proto": ("http", None),
        "system_id": 3,
        "sections": ["system", "drives"],
    }
    assert _arguments(params) == [
        "-u",
        "monitor",
        "--password-id",
        PASSWORD,
        "--port",
        "8080",
        "--proto",
        "http",
        "--system-id",
        "3",
        "--sections",
        "system,drives",
        "192.0.2.10",
    ]


def test_arguments_accepted_by_agent():
    """The command line the server side calls build is valid for the agent"""
    from cmk_addons.plugins.netapp_eseries.special_agents.agent_netappeseries import (
        parse_arguments,
    )

    params = {
        "user": "monitor",
        "password": PASSWORD,
        "port": 8080,
        "proto": ("http", None),
        "system_id": 3,
        "sections": ["system", "drives"],
    }
    argv = [
        "eseries:/omd/sites/cmk/var/check_mk/core/passwords_merged" if a is PASSWORD else a
        for a in _arguments(params)
    ]
    args = parse_arguments(argv)
    assert args.password_id.startswith("eseries:")
    assert (args.port, args.proto, args.system_id) == (8080, "http", "3")
    assert args.sections == ["system", "drives"]
    assert args.host == "192.0.2.10"
