"""Public package imports must not require credentials or make requests."""

from langchain_mrscraper import MrScraperToolkit


def test_package_toolkit_import() -> None:
    assert callable(MrScraperToolkit)
