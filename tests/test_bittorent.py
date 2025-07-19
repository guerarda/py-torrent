import shutil
import tempfile
import pytest
from pathlib import Path
import libtorrent as lt
import time

import logging

logger = logging.getLogger(__name__)


def create_torrent_file(tracker: str, payload: str):
    fs = lt.file_storage()
    lt.add_files(fs, payload)

    t = lt.create_torrent(fs)
    t.add_tracker(tracker)
    t.set_creator("test-setup")

    lt.set_piece_hashes(t, str(Path(payload).parent))
    torrent_data = lt.bencode(t.generate())

    torrent_path = Path(payload).with_suffix(".torrent")
    with open(torrent_path, "wb") as f:
        f.write(torrent_data)

    return str(torrent_path)


@pytest.fixture
def workspace():
    """Create a temporary workspace to write files to"""

    tmp_dir = tempfile.mkdtemp(prefix=Path(__file__).stem)
    tmp_path = Path(tmp_dir)

    logger.info(f"Test Workspace: {tmp_path}")

    return str(tmp_path)


@pytest.fixture
def tracker():
    return f"http://localhost:8080/announce"


@pytest.fixture
def create_payload(workspace):
    """Create test payload file in debug workspace"""
    payload_file = Path(workspace) / "payload.dat"
    payload_file.write_bytes(b"A" * (1024 * 1024))
    return str(payload_file)


def create_mock_peer(port, torrent_file, config, workspace_dir):
    """Create mock peer with explicit workspace directory"""
    settings = {
        "listen_interfaces": f"0.0.0.0:{port}",
        "enable_dht": False,
        "enable_lsd": False,
        "upload_rate_limit": config.get("upload_kb_s", 50) * 1024,
    }

    ses = lt.session(settings)
    info = lt.torrent_info(torrent_file)

    # Use the provided workspace directory
    peer_dir = Path(workspace_dir) / f"peer_{port}"
    peer_dir.mkdir(exist_ok=True)

    params = {
        "ti": info,
        "save_path": str(peer_dir),
    }
    handle = ses.add_torrent(params)

    return {
        "session": ses,
        "handle": handle,
        "port": port,
        "config": config,
        "peer_dir": peer_dir,
    }


def test_simple_download(tracker, workspace, create_payload):
    """Test downloading from a single seeder"""
    print(f"Payload file: {create_payload}")

    # Create torrent
    torrent_file = create_torrent_file(tracker, create_payload)
    print(f"Torrent file: {torrent_file}")

    # Create peer
    peer_config = {"port": 6881, "piece_availability": 100, "upload_kb_s": 50}
    peer = create_mock_peer(6881, torrent_file, peer_config, workspace)

    print(f"Peer directory: {peer['peer_dir']}")

    time.sleep(2)
    assert Path(torrent_file).exists()


# @pytest.fixture
# def create_mock_peer():
#     sessions = []

#     def _create_peer(port: int, torrent: str, workspace_dir: str, payload: str):
#         """Create a single peer bound to port, seeding"""
#         settings = {
#             "listen_interfaces": f"0.0.0.0:{port}",
#             "enable_dht": False,
#             "enable_lsd": False,
#         }

#         session = lt.session(settings)
#         info = lt.torrent_info(torrent)

#         # Create the temp directory, and copy the asset to it
#         peer_dir = Path(workspace_dir) / f"peer_{port}"
#         peer_dir.mkdir(exist_ok=True)
#         shutil.copy(payload, peer_dir)

#         lt_params = {
#             "ti": info,
#             "save_path": str(peer_dir),
#         }

#         session.add_torrent(lt_params)
#         sessions.append(session)

#     yield _create_peer

#     # Cleanup
#     for s in sessions:
#         s.pause()
#         s.abort()
