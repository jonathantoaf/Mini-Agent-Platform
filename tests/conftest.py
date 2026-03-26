from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture(scope="session")
def test_data_folder() -> Path:
    return Path.cwd().parent / "tests/test_data"


@pytest.fixture(scope="session")
def config(test_data_folder: Path) -> dict[str, Any]:
    with open(test_data_folder / "config.yaml") as file:
        return dict(yaml.safe_load(file))
