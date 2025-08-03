# py-torrent

A very simple BitTorrent Client.


## Testing
This project uses `uv` and `pytest`
```sh
uv run pytest tests/test_bittorent.py::test_simple_download -s -v --log-level=DEBUG -o log_cli=true
```
