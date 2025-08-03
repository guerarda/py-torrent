import hashlib
import logging
import shutil
from pathlib import Path

import libtorrent as lt

logger = logging.getLogger(__name__)


def create_torrent_file(payload_file: str, tracker: str, workspace: str) -> str:
    """Create the torrent file for the content of the payload in the workspace"""
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

    # Dump torrent info for debugging
    info = lt.torrent_info(str(torrent_path))
    logger.debug("Torrent details:")
    logger.debug(f"  Name: {info.name()}")
    logger.debug(f"  Total size: {info.total_size()} bytes")
    logger.debug(f"  Piece length: {info.piece_length()} bytes")
    logger.debug(f"  Num pieces: {info.num_pieces()}")
    logger.debug(f"  Info hash: {info.info_hash()}")
    logger.debug(f"  Files: {info.num_files()}")
    for i in range(info.num_files()):
        f = info.file_at(i)
        logger.debug(f"    {info.files().file_path(i)}: {f.size} bytes")

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


def calculate_sha256(file_path: str) -> str:
    """Calculate SHA-256 checksum of a file"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()
