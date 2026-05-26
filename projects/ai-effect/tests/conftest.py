import pathlib

import pytest


@pytest.fixture
def stub_include_args():
    stubs = pathlib.Path(__file__).resolve().parents[1] / "stubs"
    return ["-I", str(stubs)]
