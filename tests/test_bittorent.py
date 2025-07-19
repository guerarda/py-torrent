import logging
import shutil
import tempfile
import time
from pathlib import Path

import libtorrent as lt
import pytest

logger = logging.getLogger(__name__)

TRACKER_URL = "http://localhost:8080/announce"
PEER_DIR_FMT = "peer_{}"


def _create_torrent_file(payload_file: str, tracker: str, workspace: str):
    """Create the torrent file for the content of the payload dir in the  workspace"""

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

    return str(torrent_path)


def _create_payload(workspace: str):
    """Create test payload file in debug workspace"""
    payload_file = Path(workspace) / "payload.dat"
    payload_file.write_bytes(b"A" * (1024 * 1024))
    return str(payload_file)


def _copy_payload(payload: str, workspace: str):
    """Copy the payload to the temp workspace"""
    shutil.copy(payload, workspace)
    return str(Path(workspace) / Path(payload).name)


@pytest.fixture
def workspace():
    """Create a temporary workspace to write files to"""

    tmp_dir = tempfile.mkdtemp(prefix=Path(__file__).stem)
    tmp_path = Path(tmp_dir)

    logger.info(f"Test Workspace: {tmp_path}")

    return str(tmp_path)


@pytest.fixture
def assets_dir():
    return str(Path(__file__).parent / "assets")


@pytest.fixture
def create_mock_peer():
    sessions = []

    def _create_peer(port: int, payload: str, torrent: str, workspace_dir: str):
        """Create a single peer bound to port, seeding"""
        settings = {
            "listen_interfaces": f"0.0.0.0:{port}",
            "enable_dht": False,
            "enable_lsd": False,
        }

        session = lt.session(settings)
        info = lt.torrent_info(torrent)

        # Create the temp directory, and copy the asset to it
        peer_dir = Path(workspace_dir) / f"peer_{port}"
        peer_dir.mkdir(exist_ok=True)
        shutil.copy(payload, peer_dir)

        lt_params = {
            "ti": info,
            "save_path": str(peer_dir),
        }

        session.add_torrent(lt_params)
        sessions.append(session)

        return {
            "port": port,
            "dir": str(peer_dir),
        }

    yield _create_peer

    # Cleanup
    for s in sessions:
        s.pause()
        for handle in s.get_torrents():
            s.remove_torrent(handle)


def test_simple_download(workspace, create_mock_peer):
    """Test downloading from a single seeder"""
    payload_file = _create_payload(workspace)
    print(f"Payload file: {payload_file}")

    # Create torrent
    torrent_file = _create_torrent_file(payload_file, TRACKER_URL, workspace)
    print(f"Torrent file: {torrent_file}")

    # Create peer
    create_mock_peer(6881, payload_file, torrent_file, workspace)

    time.sleep(2)
    assert Path(torrent_file).exists()


def test_mult_peers_download_copy(workspace, assets_dir, create_mock_peer):
    """Test downloading from a single seeder"""
    payload_file = _copy_payload(str(Path(assets_dir) / "image.png"), workspace)
    print(f"Payload file: {payload_file}")

    # Create torrent
    torrent_file = _create_torrent_file(payload_file, TRACKER_URL, workspace)
    print(f"Torrent file: {torrent_file}")

    # Create peer
    peers = [
        create_mock_peer(port, payload_file, torrent_file, workspace)
        for port in [6100, 6101, 6102]
    ]
    print(f"Peers: {peers}")

    time.sleep(2)
    assert Path(torrent_file).exists()
