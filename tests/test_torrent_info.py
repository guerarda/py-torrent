import hashlib
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.bencode import Encoder
from src.torrent_info import TorrentInfo
from .utils import create_torrent_file, create_payload


class TestTorrentInfo:
    """Test suite for the TorrentInfo class."""

    @pytest.fixture
    def sample_metainfo(self):
        """Create a sample torrent metainfo dict."""
        return {
            b"announce": b"http://tracker.example.com:8080/announce",
            b"info": {
                b"name": b"test.txt",
                b"length": 1024,
                b"piece length": 16384,
                b"pieces": b"12345678901234567890" * 3,  # 3 pieces, 20 bytes each
            }
        }

    @pytest.fixture
    def multi_file_metainfo(self):
        """Create a sample multi-file torrent metainfo dict."""
        return {
            b"announce": b"http://tracker.example.com:8080/announce",
            b"info": {
                b"name": b"test_dir",
                b"piece length": 16384,
                b"pieces": b"12345678901234567890" * 2,
                b"files": [
                    {b"length": 512, b"path": [b"file1.txt"]},
                    {b"length": 256, b"path": [b"subdir", b"file2.txt"]}
                ]
            }
        }

    @pytest.fixture
    def torrent_info(self, sample_metainfo):
        """Create a TorrentInfo instance with sample data."""
        return TorrentInfo(sample_metainfo)

    def test_init(self, sample_metainfo):
        """Test TorrentInfo initialization."""
        ti = TorrentInfo(sample_metainfo)
        assert ti.metainfo == sample_metainfo

    def test_info_property(self, torrent_info, sample_metainfo):
        """Test the info property returns the info dict."""
        assert torrent_info.info == sample_metainfo[b"info"]

    def test_url_property(self, torrent_info):
        """Test the URL property returns decoded announce URL."""
        assert torrent_info.url == "http://tracker.example.com:8080/announce"

    def test_length_property(self, torrent_info):
        """Test the length property returns file size."""
        assert torrent_info.length == 1024

    def test_length_property_multi_file(self, multi_file_metainfo):
        """Test that accessing length on multi-file torrent raises KeyError."""
        ti = TorrentInfo(multi_file_metainfo)
        with pytest.raises(KeyError):
            _ = ti.length

    def test_piece_length_property(self, torrent_info):
        """Test the piece_length property."""
        assert torrent_info.piece_length == 16384

    def test_pieces_property(self, torrent_info):
        """Test the pieces property splits pieces correctly."""
        pieces = torrent_info.pieces
        assert len(pieces) == 3
        assert all(len(piece) == 20 for piece in pieces)
        assert pieces[0] == b"12345678901234567890"

    def test_info_hash_property(self, torrent_info, sample_metainfo):
        """Test the info_hash property returns correct hash."""
        # Manually calculate expected hash
        encoder = Encoder()
        info_bencoded = encoder.encode(sample_metainfo[b"info"])
        expected_hash = hashlib.sha1(info_bencoded).digest()
        expected_hex = hashlib.sha1(info_bencoded).hexdigest()
        
        hash_digest, hash_hex = torrent_info.info_hash
        assert hash_digest == expected_hash
        assert hash_hex == expected_hex

    def test_str_representation(self, torrent_info):
        """Test string representation of TorrentInfo."""
        str_repr = str(torrent_info)
        assert "Tracker URL: http://tracker.example.com:8080/announce" in str_repr
        assert "Length: 1024" in str_repr
        assert "Piece Length: 16384" in str_repr
        assert "Info Hash:" in str_repr

    @patch('requests.get')
    def test_get_peers_success(self, mock_get, torrent_info):
        """Test successful peer retrieval from tracker."""
        # Mock successful tracker response
        # Compact peer format: 4 bytes IP + 2 bytes port
        peer1 = b'\x7f\x00\x00\x01\x1a\xe1'  # 127.0.0.1:6881
        peer2 = b'\xc0\xa8\x01\x02\x1a\xe2'  # 192.168.1.2:6882
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = Encoder().encode({
            b"interval": 1800,
            b"peers": peer1 + peer2
        })
        mock_get.return_value = mock_response
        
        peers = torrent_info.get_peers()
        
        assert len(peers) == 2
        assert peers[0] == ("127.0.0.1", 6881)
        assert peers[1] == ("192.168.1.2", 6882)
        
        # Verify request parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == torrent_info.url
        params = call_args[1]['params']
        assert params['info_hash'] == torrent_info.info_hash[0]
        assert params['peer_id'] == "Hj5kP9xZ2qLmNb7vYc3w"
        assert params['port'] == 6881
        assert params['uploaded'] == 0
        assert params['downloaded'] == 0
        assert params['left'] == torrent_info.length
        assert params['compact'] == 1

    @patch('requests.get')
    def test_get_peers_failure(self, mock_get, torrent_info):
        """Test failed peer retrieval from tracker."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            torrent_info.get_peers()
        assert "404" in str(exc_info.value)

    @patch('requests.get')
    def test_get_peers_empty_list(self, mock_get, torrent_info):
        """Test peer retrieval with empty peer list."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = Encoder().encode({
            b"interval": 1800,
            b"peers": b""  # Empty peer list
        })
        mock_get.return_value = mock_response
        
        peers = torrent_info.get_peers()
        assert peers == []

    def test_from_file(self, tmp_path):
        """Test creating TorrentInfo from file."""
        # Create a test torrent file
        metainfo = {
            b"announce": b"http://test.com/announce",
            b"info": {
                b"name": b"test.txt",
                b"length": 100,
                b"piece length": 16384,
                b"pieces": b"12345678901234567890"
            }
        }
        
        torrent_file = tmp_path / "test.torrent"
        encoder = Encoder()
        torrent_file.write_bytes(encoder.encode(metainfo))
        
        ti = TorrentInfo.from_file(str(torrent_file))
        assert ti is not None
        assert ti.url == "http://test.com/announce"
        assert ti.length == 100

    def test_from_file_not_found(self):
        """Test from_file with non-existent file."""
        with pytest.raises(FileNotFoundError):
            TorrentInfo.from_file("/non/existent/file.torrent")

    def test_from_file_invalid_content(self, tmp_path):
        """Test from_file with invalid torrent data."""
        invalid_file = tmp_path / "invalid.torrent"
        invalid_file.write_bytes(b"not a valid torrent file")
        
        with pytest.raises(ValueError):
            TorrentInfo.from_file(str(invalid_file))


class TestTorrentInfoIntegration:
    """Integration tests using real torrent files."""

    @pytest.fixture
    def workspace(self):
        """Create a temporary workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_real_torrent_file(self, workspace):
        """Test with a real torrent file created by libtorrent."""
        # Create a test payload
        payload_file = create_payload(workspace, size=1024)
        
        # Create torrent file
        torrent_file = create_torrent_file(
            Path(payload_file).name,
            "http://localhost:8080/announce",
            workspace
        )
        
        # Load and verify torrent
        ti = TorrentInfo.from_file(torrent_file)
        assert ti is not None
        assert ti.url == "http://localhost:8080/announce"
        assert ti.length == 1024
        assert ti.piece_length > 0
        assert len(ti.pieces) > 0
        
        # Verify info hash format
        hash_digest, hash_hex = ti.info_hash
        assert isinstance(hash_digest, bytes)
        assert len(hash_digest) == 20  # SHA1 produces 20 bytes
        assert isinstance(hash_hex, str)
        assert len(hash_hex) == 40  # 40 hex characters

    def test_string_representation_real_torrent(self, workspace):
        """Test string representation with real torrent."""
        payload_file = create_payload(workspace, size=2048)
        torrent_file = create_torrent_file(
            Path(payload_file).name,
            "http://example.com/announce",
            workspace
        )
        
        ti = TorrentInfo.from_file(torrent_file)
        str_repr = str(ti)
        
        assert "Tracker URL: http://example.com/announce" in str_repr
        assert "Length: 2048" in str_repr
        assert "Info Hash:" in str_repr
        assert "Piece Length:" in str_repr