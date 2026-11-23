import json
import re
from pathlib import Path

from layoutlingua._version import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_package_metadata_matches_version():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1) == __version__
    assert package["version"] == __version__


def test_readme_states_released_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    title = re.search(r"^# .*?\bv(\d+\.\d+\.\d+)\b", readme, re.MULTILINE)
    badge = re.search(r"badge/Version-(\d+\.\d+\.\d+)-", readme)
    assert title and title.group(1) == __version__
    assert badge and badge.group(1) == __version__
    assert f'alt="Version {__version__}"' in readme
