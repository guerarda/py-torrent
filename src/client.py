import asyncio
import logging
import struct
from pathlib import Path

from .torrent_info import TorrentInfo

MY_PEER_ID = "Hj5kP9xZ2qLmNb7vYc3w"

logger = logging.getLogger()


class SimpleClient:
    async def fetch_first_piece(self, metainfo_file: str, output: str) -> bool:
        torrent = TorrentInfo.from_file(metainfo_file)
        assert torrent

        peers = torrent.get_peers()
        addr, port = peers[0]

        reader, writer = await asyncio.open_connection(addr, port)

        # Do Handshake
        writer.write(
            struct.pack(
                ">B19s8x20s20s",
                19,
                b"BitTorrent protocol",
                torrent.info_hash[0],
                MY_PEER_ID.encode(),
            )
        )
        await writer.drain()
        logger.info("Sent 'handshake' message")

        # Wait for response: the id of the peer we connected to.
        response = await reader.readexactly(68)
        peer_id = response[-20:]
        logger.info(f"Connected to {peer_id=}")

        # Expect bitfield message
        logger.info("Expecting 'bitfield' message")
        msg = await reader.readexactly(5)
        msg_len, msg_type = struct.unpack(">IB", msg)

        if msg_type != 5:  # Bitfield message is type 5
            raise Exception(f"Expected Bitfiled got {msg_type=}, {msg_len=}")
        logger.info("Received 'bitfiled' message")
        await reader.readexactly(msg_len - 1)

        # Send interested
        writer.write(struct.pack(">IB", 1, 2))
        await writer.drain()
        logger.info("Sent 'interested' message")

        # Expect unchoke message
        logger.info("Expecting 'unchoke' message")
        msg = await reader.readexactly(5)
        msg_len, msg_type = struct.unpack(">IB", msg)

        if msg_len != 1 and msg_type != 1:
            raise Exception(f"Expected 'unchoke' got {msg_type=}, {msg_len=}")
        logger.info("Received 'unchoke' message")

        # Get ready to request a pice.

        # Block size calculation
        block_size = 16 * 2**10

        q, r = divmod(torrent.piece_length, block_size)
        if r > 0:
            block_count = q + 1
            last_block_size = r
        else:
            block_count = q
            last_block_size = block_size

        # Allocate the bytearray we're goign to write the piece data to
        data = bytearray(torrent.piece_length)

        logger.info(f"{block_count=}, {block_size=}, {last_block_size=}")
        # Request each block for the piece, sequentially
        for i in range(block_count):
            offset = i * block_size
            size = block_size if i < block_count - 1 else last_block_size

            logger.info(f"Asking for {i=} of {block_count=}, size={size / (2**10)} kb")

            # Send block request
            writer.write(struct.pack(">IBIII", 13, 6, 0, offset, size))
            await writer.drain()

            # Receive block response
            while True:
                msg = await reader.readexactly(5)
                msg_len, msg_type = struct.unpack(">IB", msg)

                if msg_type != 7:
                    logger.info(f"received {msg_len=}, {msg_type=}")
                    if msg_len > 1:
                        await reader.readexactly(msg_len - 1)
                        logger.info("Consummed message")
                else:
                    piece_data = await reader.readexactly(8)  # index (4) + begin (4)
                    piece_idx, bgn = struct.unpack(">II", piece_data)
                    block_data = await reader.readexactly(msg_len - 9)
                    data[bgn : bgn + len(block_data)] = block_data

                    logger.info(
                        f"Received block message: {msg_type=}, {msg_len=}, {piece_idx=}, offset={bgn}"
                    )
                    break

        writer.close()

        with open(Path(output) / torrent.file, "wb") as f:
            f.write(data)

        return True
