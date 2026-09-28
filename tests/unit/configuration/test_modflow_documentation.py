"""The configuration examples of the groundwater page are sections the loader accepts."""

import json
import re
import textwrap
from pathlib import Path

from rubem.configuration.modflow_configuration import ModflowSettings

PAGE = Path(__file__).resolve().parents[3] / "doc" / "source" / "groundwater.rst"

_JSON_BLOCK = re.compile(r"^\.\. code-block:: json\n\n((?:(?:   .*)?\n)+)", re.MULTILINE)


def json_examples() -> list[dict]:
    """Every ``code-block:: json`` of the page, parsed."""
    text = PAGE.read_text(encoding="utf-8")
    return [json.loads(textwrap.dedent(block)) for block in _JSON_BLOCK.findall(text)]


def sections() -> list[dict]:
    """The ``modflow`` (format 1.0) or ``MODFLOW`` (legacy) sections of the examples."""
    found = []
    for example in json_examples():
        for key in ("modflow", "MODFLOW"):
            if key in example:
                found.append(example[key])
    return found


def test_the_page_has_json_examples():
    assert json_examples()


def test_the_page_shows_an_enabled_section():
    assert any(section.get("enabled") is True for section in sections())


def test_every_section_of_the_page_is_valid():
    found = sections()
    assert found
    for section in found:
        ModflowSettings.model_validate(section)


def test_the_layer_names_of_the_template_are_top_down():
    """The example lists the layers from the top down: layer 1 is the upper one."""
    template = next(section for section in sections() if section.get("enabled") is True)
    settings = ModflowSettings.model_validate(template)
    assert [layer.name for layer in settings.layers] == ["upper", "middle", "lower"]
    assert settings.pcraster_layer(1) == 3
