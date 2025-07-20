import logging
import shutil
from pathlib import Path

import libtorrent as lt

logger = logging.getLogger(__name__)


def create_torrent_file(payload_file: str, tracker: str, workspace: str) -> str:
    """Create the torrent file for the content of the payload dir in the workspace"""
    payload_path = Path(workspace) / payload_file

    fs = lt.file_storage()
    lt.add_files(fs, str(payload_path))

    t = lt.create_torrent(fs)
    t.add_tracker(tracker)
    t.set_creator("test-setup")

    lt.set_piece_hashes(t, str(payload_path.parent))
    torrent_data = lt.bencode(t.generate())

    torrent_path = payload_path.with_suffix(".torrent")
    with open(torrent_path, "wb") as f:
        f.write(torrent_data)

    logger.debug(f"Torrent file: {str(torrent_path)}")

    return str(torrent_path)


def create_payload(workspace: str, size: int = 1024 * 1024) -> str:
    """Create test payload file in debug workspace"""
    payload_file = Path(workspace) / "payload.dat"
    payload_file.write_bytes(b"A" * size)
    return str(payload_file)


def copy_payload(payload: str, assets_dir: str, workspace: str) -> str:
    """Copy the payload to the temp workspace"""
    output = Path(workspace) / payload
    shutil.copy(Path(assets_dir) / payload, output)
    logger.debug(f"Payload file: {str(output)}")

    return str(output)