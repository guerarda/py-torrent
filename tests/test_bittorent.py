import logging
import shutil
import tempfile
import time
from pathlib import Path

import libtorrent as lt
import pytest

logging.basicConfig(format="%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger()

TRACKER_URL = "http://localhost:8080/announce"
ASSETS_DIR = str(Path(__file__).parent / "assets")
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

    logger.debug(f"Torrent file: {str(torrent_path)}")

    return str(torrent_path)


def _create_payload(workspace: str):
    """Create test payload file in debug workspace"""
    payload_file = Path(workspace) / "payload.dat"
    payload_file.write_bytes(b"A" * (1024 * 1024))
    return str(payload_file)


def _copy_payload(payload: str, workspace: str):
    """Copy the payload to the temp workspace"""
    output = Path(workspace) / payload
    shutil.copy(Path(ASSETS_DIR) / payload, output)
    logger.debug(f"Payload file: {str(output)}")

    return str(output)


@pytest.fixture
def workspace():
    """Create a temporary workspace to write files to"""

    tmp_dir = tempfile.mkdtemp(prefix=Path(__file__).stem)
    tmp_path = Path(tmp_dir)

    logger.debug(f"Test Workspace: {tmp_path}")

    return str(tmp_path)


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

        if payload:
            shutil.copy(payload, peer_dir)

        lt_params = {
            "ti": info,
            "save_path": str(peer_dir),
        }

        handle = session.add_torrent(lt_params)
        sessions.append(session)

        return {
            "port": port,
            "dir": str(peer_dir),
            "session": session,
            "handle": handle,
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
    torrent_file = _create_torrent_file(payload_file, TRACKER_URL, workspace)

    create_mock_peer(6881, payload_file, torrent_file, workspace)

    time.sleep(2)
    assert Path(torrent_file).exists()


def test_mult_peers_download_copy(workspace, create_mock_peer):
    """Test multiple peers downloading a file"""
    payload_file = _copy_payload("image.png", workspace)
    torrent_file = _create_torrent_file(payload_file, TRACKER_URL, workspace)

    peers = [
        create_mock_peer(port, payload_file, torrent_file, workspace)
        for port in [6100, 6101, 6102]
    ]
    logger.debug(f"{peers=}")

    time.sleep(2)
    assert Path(torrent_file).exists()


@pytest.mark.manual
def test_setup(workspace, create_mock_peer):
    """Test the testing setup by creating a peer and make it download the torrent"""
    payload_file = _copy_payload("image.png", workspace)
    torrent_file = _create_torrent_file(payload_file, TRACKER_URL, workspace)

    seeding_peers = [
        create_mock_peer(port, payload_file, torrent_file, workspace)
        for port in [6100, 6101, 6102]
    ]
    logger.debug(f"{seeding_peers=}")

    time.sleep(2)
    assert Path(torrent_file).exists()

    leech = create_mock_peer(6881, None, torrent_file, workspace)
    logger.debug("Downloading...")

    # Download until complete
    h = leech["handle"]

    while not h.status().is_seeding:
        s = h.status()
        logger.debug(
            f"Progress: {s.progress * 100:.1f}% "
            f"Down: {s.download_rate / 1000:.1f} kB/s "
            f"Peers: {s.num_peers}"
        )
        time.sleep(1)

    logger.debug("Download complete!")
    assert True
