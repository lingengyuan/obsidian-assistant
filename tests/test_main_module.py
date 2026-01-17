from __future__ import annotations

import runpy
import sys

import pytest


def test_main_module_invocation() -> None:
    original_argv = sys.argv
    sys.argv = ["oka"]
    try:
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("oka", run_name="__main__")
        assert excinfo.value.code == 0
    finally:
        sys.argv = original_argv
