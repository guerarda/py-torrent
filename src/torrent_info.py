import hashlib
import requests

from .bencode import Decoder, Encoder

PEER_ID = "Hj5kP9xZ2qLmNb7vYc3w"


class TorrentFile:
    def __init__(self, metainfo: dict):
        self.metainfo = metainfo

    def __str__(self):
        str = f"Tracker URL: {self.url}\n"
        str += f"Length: {self.length}\n"
        str += f"Info Hash: {self.info_hash[1]}\n"
        str += f"Piece Length: {self.piece_length}\n"
        str += "\n".join([x.hex() for x in self.pieces])
        return str

    @property
    def info(self):
        return self.metainfo[b"info"]

    @property
    def info_hash(self):
        data = Encoder().encode(self.info)
        sha1_hash = hashlib.sha1(data)
        return (sha1_hash.digest(), sha1_hash.hexdigest())

    @property
    def url(self):
        return self.metainfo[b"announce"].decode()

    @property
    def length(self):
        return self.info[b"length"]

    @property
    def pieces(self):
        all = self.info[b"pieces"]
        pieces = [all[i : i + 20] for i in range(0, len(all), 20)]
        return pieces

    @property
    def piece_length(self):
        return self.info[b"piece length"]

    def get_peers(self):
        req = {
            "info_hash": self.info_hash[0],
            "peer_id": PEER_ID,
            "port": 6881,
            "uploaded": 0,
            "downloaded": 0,
            "left": self.length,
            "compact": 1,
        }

        r = requests.get(self.url, params=req)

        if r.ok:
            d = Decoder(r.content).read_dict()
            all_peers = d[b"peers"]

            peer_list = []
            peers = [all_peers[i : i + 6] for i in range(0, len(all_peers), 6)]

            for p in peers:
                ip = ".".join([repr(int(x)) for x in p[:4]])
                port = int.from_bytes(p[4:])

                peer_list.append((ip, port))

            return peer_list

        else:
            raise Exception(r.status_code)

    @classmethod
    def from_file(cls, file: str) -> "TorrentFile | None":
        with open(file, mode="rb") as f:
            d = Decoder(f.read())
        metainfo = d.read_dict()
        return TorrentFile(metainfo)
