import logging

import pytest

from rubem.cli import setup_logging


@pytest.fixture(name="restore_logging")
def restore_logging_fixture():
    """Undo the global changes ``dictConfig`` makes to the logging module."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    manager = root.manager
    saved_disabled = {
        name: existing.disabled
        for name, existing in manager.loggerDict.items()
        if isinstance(existing, logging.Logger)
    }
    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        for name, disabled in saved_disabled.items():
            existing = manager.loggerDict.get(name)
            if isinstance(existing, logging.Logger):
                existing.disabled = disabled


class TestSetupLogging:
    @pytest.mark.unit
    def test_default_config_keeps_existing_loggers_enabled(self, restore_logging):
        """The packaged ``appsettings.json`` has no ``logging`` block, so this path
        configures every installed run. It must not disable the module loggers that
        already exist by the time it runs -- ``rubem.cli``'s own included.
        """
        existing = logging.getLogger("rubem.tests.default_path")

        setup_logging()

        assert not existing.disabled

    @pytest.mark.unit
    def test_custom_config_keeps_existing_loggers_enabled(self, restore_logging):
        """A custom block that omits the flag must not silence pre-existing loggers."""
        existing = logging.getLogger("rubem.tests.custom_path")

        setup_logging({"version": 1, "handlers": {}, "root": {"level": "DEBUG"}})

        assert not existing.disabled

    @pytest.mark.unit
    def test_custom_config_may_opt_into_disabling_loggers(self, restore_logging):
        """An explicit ``disable_existing_loggers`` in the custom block still wins."""
        existing = logging.getLogger("rubem.tests.opt_in_path")

        setup_logging(
            {
                "version": 1,
                "disable_existing_loggers": True,
                "handlers": {},
                "root": {"level": "DEBUG"},
            }
        )

        assert existing.disabled

    @pytest.mark.unit
    def test_invalid_custom_config_falls_back_to_defaults(self, restore_logging):
        """A broken custom block must leave usable logging behind, not a dead one."""
        existing = logging.getLogger("rubem.tests.fallback_path")

        setup_logging({"version": 1, "handlers": {"console": {"class": "not.a.Handler"}}})

        assert not existing.disabled
        assert logging.getLogger().handlers
