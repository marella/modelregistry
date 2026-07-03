import os
import sys
import tempfile
from pathlib import Path
from shutil import disk_usage, rmtree

import libtorrent as lt
from huggingface_hub import list_models, model_info, snapshot_download

licenses = [
    "apache-2.0",
    "mit",
]

LICENSES = frozenset(licenses)
GB = 1000**3
root = Path(__file__).parent.parent.resolve()
models_dir = root / "models"


def main() -> None:
    repo_id = get_repo_id()
    if not repo_id:
        return
    repo_id, revision = get_model_info(repo_id)
    download_model_and_create_torrent(repo_id, revision)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            print(f"repo_id={repo_id}", file=f)


def download_model_and_create_torrent(repo_id: str, revision: str) -> None:
    url_seed = get_url_seed(repo_id, revision)
    torrent_file = get_torrent_file(repo_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir, repo_id)
        print(
            {
                "repo_id": repo_id,
                "revision": revision,
                "url_seed": url_seed,
                "model_dir": str(model_dir),
                "torrent_file": str(torrent_file),
            }
        )

        snapshot_download(repo_id=repo_id, revision=revision, local_dir=model_dir)
        try:
            # snapshot_download adds .cache directory which won't be available in web seed.
            rmtree(model_dir / ".cache")
        except FileNotFoundError:
            pass

        create_torrent(model_dir, url_seed, torrent_file)


def get_repo_id() -> str | None:
    try:
        repo_id = sys.argv[1].strip()
    except IndexError:
        repo_id = None

    repo_id = repo_id or find_repo_id()
    if not repo_id:
        return

    if repo_id.count("/") != 1:
        raise ValueError(
            f"Repo id '{repo_id}' must be in the form 'namespace/repo_name'."
        )
    return repo_id


def find_repo_id() -> str | None:
    existing = set(
        str(p.parent.relative_to(models_dir)).lower()
        for p in models_dir.glob("*/*/*.torrent")
        if p.is_file()
    )
    free = disk_usage("/").free - 5 * GB
    print(f"Finding repo with size < {free}.")
    models = list_models(gated=False, expand=["cardData"], limit=30)
    for model in models:
        repo_id = model.id
        if repo_id.lower() in existing:
            print(f"Repo '{repo_id}' already exists.")
            continue
        license = model.card_data.license if model.card_data else None
        if license not in LICENSES:
            print(f"Repo '{repo_id}' license '{license}' is not allowed.")
            continue
        repo_size = get_repo_size(repo_id)
        if repo_size > free:
            print(f"Repo '{repo_id}' size ({repo_size}) > free space ({free}).")
            continue
        print(f"Found repo '{repo_id}' with size {repo_size}.")
        return repo_id
    print("No repo found.")


def get_repo_size(repo_id: str) -> int:
    model = model_info(repo_id=repo_id, files_metadata=True)
    return sum(s.size or 0 for s in model.siblings or [])


def get_model_info(repo_id: str) -> tuple[str, str]:
    model = model_info(repo_id=repo_id, expand=["sha"])
    if not model.sha:
        raise ValueError(f"Unknown revision for repo id '{model.id}'.")
    return model.id, model.sha


def get_torrent_file(repo_id: str) -> Path:
    root = Path(__file__).parent.parent.resolve()
    filename = Path(repo_id).name + ".torrent"
    return root / "models" / repo_id.lower() / filename


def get_url_seed(repo_id: str, revision: str) -> str:
    return f"https://seed.modelregistry.io/v1/{repo_id}/{revision}/"


def create_torrent(model_dir: Path, url_seed: str, torrent_file: Path) -> None:
    fs = lt.file_storage()
    lt.add_files(fs, str(model_dir))

    torrent = lt.create_torrent(fs)
    torrent.add_url_seed(url_seed)
    lt.set_piece_hashes(torrent, str(model_dir.parent))

    data = torrent.generate()
    # Remove creation date to generate the exact same file every time.
    data.pop(b"creation date", None)

    torrent_file.parent.mkdir(parents=True, exist_ok=True)
    torrent_file.write_bytes(lt.bencode(data))


main()
