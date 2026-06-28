import json
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import libtorrent as lt

root = Path(__file__).parent.parent.resolve()
model_dir = root / "models"


@dataclass
class Status:
    seeds: int
    peers: int


def main() -> None:
    paths = [p for p in model_dir.glob("*/*/*.torrent") if p.is_file()]

    data = {}
    with tempfile.TemporaryDirectory() as save_path:
        for path in paths:
            name = str(path.relative_to(root))
            print(f"Checking status of '{name}'", end=" ")
            status = get_status(path, save_path)
            print(status)
            data[name] = asdict(status)

    file = root / "_data" / "torrents.json"
    file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def get_status(path: Path, save_path: str) -> Status:
    ses = lt.session()
    ses.listen_on(6881, 6891)
    handle = ses.add_torrent({"ti": lt.torrent_info(str(path)), "save_path": save_path})
    handle.pause()

    time.sleep(10)

    status = handle.status()
    return Status(seeds=status.list_seeds, peers=status.list_peers)


main()
