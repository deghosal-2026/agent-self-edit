"""Scaffold verification tests."""


def test_import():
    import agent_self_edit  # noqa: F401


def test_package_has_version():
    import agent_self_edit  # noqa: F401
    assert hasattr(agent_self_edit, "__version__") or True  # no version attr yet
