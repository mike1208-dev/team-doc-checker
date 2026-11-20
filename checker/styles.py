from dataclasses import dataclass, field
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


@dataclass
class Style:
    """
    One document style (daily report, issue/PR, work plan, ...), loaded from rules/<id>.yaml.
    """

    id: str
    name: str
    rules: list[dict]
    description: str = ""
    detect: list[str] = field(default_factory=list)


def load_styles(rules_dir: Path = RULES_DIR) -> dict[str, Style]:
    """
    Loads every rules/*.yaml file. Adding a new style = adding a new file.
    """
    styles = {}
    for path in sorted(Path(rules_dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        styles[path.stem] = Style(
            id=path.stem,
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            detect=data.get("detect", []),
            rules=data.get("rules", []),
        )
    return styles


def guess_style(text: str, styles: dict[str, Style]) -> Style | None:
    """
    Picks the style whose `detect` keywords appear most often in the text.
    Returns None if no keyword matches, so the user has to choose.
    """
    lowered = text.lower()
    best, best_score = None, 0
    for style in styles.values():
        score = sum(1 for keyword in style.detect if keyword.lower() in lowered)
        if score > best_score:
            best, best_score = style, score
    return best
