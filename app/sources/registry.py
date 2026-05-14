from pathlib import Path

import yaml

from app.sources.base import SourceConfig


def load_sources(config_path: Path | None = None) -> dict[str, SourceConfig]:
    path = config_path or Path(__file__).resolve().parents[1] / "config" / "sources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        name: SourceConfig(**config)
        for name, config in data.get("sources", {}).items()
        if config.get("enabled", True)
    }

