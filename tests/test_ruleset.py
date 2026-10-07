"""Rules saved by older versions must still load (cmk-update-config aborts otherwise)"""

import pytest
from cmk.rulesets.v1.form_specs import Dictionary
from cmk_addons.plugins.netapp_eseries.rulesets.netappeseries import (
    _migrate_proto,
    rule_spec_netapp_eseries_datasource_programs,
)


def _elements():
    form = rule_spec_netapp_eseries_datasource_programs.parameter_form()
    assert isinstance(form, Dictionary)
    return form.elements


def _migrate(key, value):
    migrate = _elements()[key].parameter_form.migrate
    return value if migrate is None else migrate(value)


def test_rule_spec_name_matches_server_side_calls():
    assert rule_spec_netapp_eseries_datasource_programs.name == "netappeseries"


@pytest.mark.parametrize(
    "stored, expected",
    [
        ("https", ("https", None)),
        ("http", ("http", None)),
        (("https", None), ("https", None)),
    ],
)
def test_migrate_proto(stored, expected):
    assert _migrate("proto", stored) == expected


def test_migrate_proto_rejects_garbage():
    with pytest.raises(TypeError):
        _migrate_proto(443)


def test_migrate_legacy_explicit_password():
    # Checkmk 2.2 valuespec format, see temp/password_rule
    kind, how, (pw_id, secret) = _migrate("password", ("password", "Passw0rd"))
    assert (kind, how, secret) == ("cmk_postprocessed", "explicit_password", "Passw0rd")
    assert pw_id


def test_migrate_legacy_stored_password():
    assert _migrate("password", ("store", "eseries")) == (
        "cmk_postprocessed",
        "stored_password",
        ("eseries", ""),
    )


def test_current_password_format_unchanged():
    value = ("cmk_postprocessed", "explicit_password", ("uuid-1", "secret"))
    assert _migrate("password", value) == value


def test_sections_match_agent():
    """Every section the rule offers is known to the agent"""
    from cmk_addons.plugins.netapp_eseries.special_agents.agent_netappeseries import (
        parse_arguments,
    )

    offered = {e.name for e in _elements()["sections"].parameter_form.elements}
    defaults = parse_arguments(["-u", "x", "-s", "y", "host"]).sections
    assert offered == set(defaults)
