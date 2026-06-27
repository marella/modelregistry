import json
from dataclasses import asdict, dataclass
from pathlib import Path

from huggingface_hub import model_info

root = Path(__file__).parent.parent.resolve()
model_dir = root / "models"


@dataclass
class Model:
    id: str
    size: str
    parameters: str
    license: str
    torrent: str


def main():
    paths = [p for p in model_dir.glob("*/*/*.torrent") if p.is_file()]
    models = [get_model(p) for p in paths]
    models = sorted(models, key=lambda v: v[0], reverse=True)
    models = [asdict(m) for _, m in models]

    file = root / "_data" / "models.json"
    file.write_text(json.dumps(models, indent=2) + "\n")


def get_model(path: Path) -> tuple[int, Model]:
    repo_id = str(path.parent.relative_to(model_dir))
    model = model_info(repo_id=repo_id, files_metadata=True)
    extra = model_info(repo_id=model.id, expand=["trendingScore"])

    size = sum(s.size or 0 for s in model.siblings or [])
    parameters = model.safetensors.total if model.safetensors else 0
    license = model.card_data.license if model.card_data else None
    sort = extra.trending_score or 0

    return sort, Model(
        id=model.id,
        size=format_size(size),
        parameters=format_parameters(parameters),
        license=license or "",
        torrent=str(path.relative_to(root)),
    )


def format_size(n: float) -> str:
    units = ["KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        n /= 1000
        if n < 1000 or unit == units[-1]:
            return f"{format_num(n)} {unit}"
    return ""


def format_parameters(n: float) -> str:
    if n == 0:
        return ""
    units = ["", "K", "M", "B", "T"]
    for unit in units:
        if n < 1000 or unit == units[-1]:
            return f"{format_num(n)}{unit}"
        n /= 1000
    return ""


def format_num(n: float) -> str:
    return f"{n:.1f}".rstrip("0").rstrip(".")


main()
