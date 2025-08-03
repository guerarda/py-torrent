import asyncio
import logging
import shutil
import tempfile
import time
from pathlib import Path

import libtorrent as lt
import pytest

from src.client import SimpleClient
from .utils import create_payload, create_torrent_file, copy_payload, calculate_sha256

logging.basicConfig(format="%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger()

TRACKER_URL = "http://localhost:8080/announce"
ASSETS_DIR = str(Path(__file__).parent / "assets")
PEER_DIR_FMT = "peer_{}"


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
        peer_dir = Path(workspace_dir) / PEER_DIR_FMT.format(port)
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


@pytest.mark.asyncio
async def test_simple_download(workspace, create_mock_peer):
    """Test downloading first piece from a single seeder using our Client"""
    # Create a small payload (smaller than default piece size)
    payload_file = create_payload(workspace, 16 * 2**10)
    torrent_file = create_torrent_file(payload_file, TRACKER_URL, workspace)

    # Create a seeding peer
    create_mock_peer(6881, payload_file, torrent_file, workspace)

    # Give the seeder time to start up and connect to tracker
    await asyncio.sleep(2)

    # Create download directory
    download_dir = Path(workspace) / "download"
    download_dir.mkdir(exist_ok=True)

    # Attempt to fetch the first piece
    logger.info("Attempting to fetch first piece with our client")
    client = SimpleClient()
    result = await client.fetch_first_piece(torrent_file, str(download_dir))

    # Verify we successfully connected and fetched without errors
    assert result, "Client should have successfully fetched the first piece"
    logger.info("Successfully fetched first piece!")

    # Verify the downloaded file exists
    downloaded_file = download_dir / Path(payload_file).name

    assert downloaded_file.exists(), (
        f"Downloaded file should exist at {downloaded_file}"
    )

    # Calculate checksums for comparison
    original_checksum = calculate_sha256(payload_file)
    downloaded_checksum = calculate_sha256(str(downloaded_file))

    logger.info(f"Original checksum: {original_checksum}")
    logger.info(f"Downloaded checksum: {downloaded_checksum}")

    assert original_checksum == downloaded_checksum, (
        "Downloaded file checksum should match original"
    )

    # Verify file size matches
    original_size = Path(payload_file).stat().st_size
    downloaded_size = downloaded_file.stat().st_size
    assert original_size == downloaded_size, (
        f"File sizes should match: {original_size} != {downloaded_size}"
    )


def test_mult_peers_download_copy(workspace, create_mock_peer):
    """Test multiple peers downloading a file"""
    payload_file = copy_payload("image.png", ASSETS_DIR, workspace)
    torrent_file = create_torrent_file(payload_file, TRACKER_URL, workspace)

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
    payload_file = copy_payload("image.png", ASSETS_DIR, workspace)
    torrent_file = create_torrent_file(payload_file, TRACKER_URL, workspace)

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
