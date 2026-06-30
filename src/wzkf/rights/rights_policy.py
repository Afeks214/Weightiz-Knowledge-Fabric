from pathlib import Path

import yaml


def load_rights_policies(path: Path) -> dict[str, object]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
