import sys
import tempfile
from pathlib import Path
from shutil import rmtree

import libtorrent as lt
from huggingface_hub import model_info, snapshot_download


def main() -> None:
    repo_id = get_repo_id()
    repo_id, revision = get_model_info(repo_id)
    download_model_and_create_torrent(repo_id, revision)


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


def get_repo_id() -> str:
    try:
        repo_id = sys.argv[1].strip()
    except IndexError:
        raise ValueError("Repo id must be passed as a command-line argument.")

    if repo_id.count("/") != 1:
        raise ValueError(
            f"Repo id '{repo_id}' must be in the form 'namespace/repo_name'."
        )
    return repo_id


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
