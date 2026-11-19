"""Schema descriptions use the same standard as the CLI and SDKs."""

import json
from pathlib import Path

import pytest

from langchain_mrscraper.tools import TOOL_CLASSES

REFERENCE = json.loads(
    (Path(__file__).parents[2] / "docs/service-reference.json").read_text()
)
SERVICES = {
    service["name"].replace("-", "_"): service for service in REFERENCE["services"]
}


@pytest.mark.parametrize("cls", TOOL_CLASSES)
def test_standard_descriptions(cls):
    tool = cls()
    service = SERVICES[tool.sdk_method]
    assert tool.description == service["description"]
    for key in service["parameters"]:
        parameter = REFERENCE["parameters"][key]
        name = "".join(
            "_" + char.lower() if char.isupper() else char for char in parameter["name"]
        )
        assert (
            tool.args_schema.model_fields[name].description == parameter["description"]
        )
