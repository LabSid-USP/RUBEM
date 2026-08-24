import logging

import pytest

from rubem.cli import setup_logging


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


class TestRestoreLoggingFixture:
    """The fixture guards every test that reconfigures logging."""

    @pytest.mark.unit
    def test_configuring_logging_attaches_the_progress_handler(self, restore_logging):
        setup_logging()

        assert logging.getLogger("rubem.progress").handlers

    @pytest.mark.unit
    def test_the_progress_logger_is_left_as_it_was(self):
        """Runs after the test above: its configuration must not have survived."""
        progress = logging.getLogger("rubem.progress")

        assert not progress.handlers
        assert progress.propagate
