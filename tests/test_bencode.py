import pytest
from src.bencode import Decoder, Encoder


class TestDecoder:
    """Test suite for the Bencode Decoder."""

    def test_decode_string(self):
        """Test decoding of bencode strings."""
        decoder = Decoder(b"4:spam")
        assert decoder.decode() == b"spam"

    def test_decode_empty_string(self):
        """Test decoding of empty string."""
        decoder = Decoder(b"0:")
        assert decoder.decode() == b""

    def test_decode_integer(self):
        """Test decoding of positive integers."""
        decoder = Decoder(b"i42e")
        assert decoder.decode() == 42

    def test_decode_negative_integer(self):
        """Test decoding of negative integers."""
        decoder = Decoder(b"i-42e")
        assert decoder.decode() == -42

    def test_decode_zero(self):
        """Test decoding of zero."""
        decoder = Decoder(b"i0e")
        assert decoder.decode() == 0

    def test_decode_list(self):
        """Test decoding of lists."""
        decoder = Decoder(b"l4:spam4:eggse")
        assert decoder.decode() == [b"spam", b"eggs"]

    def test_decode_empty_list(self):
        """Test decoding of empty list."""
        decoder = Decoder(b"le")
        assert decoder.decode() == []

    def test_decode_nested_list(self):
        """Test decoding of nested lists."""
        decoder = Decoder(b"ll4:spamee")
        assert decoder.decode() == [[b"spam"]]

    def test_decode_dict(self):
        """Test decoding of dictionaries."""
        decoder = Decoder(b"d3:cow3:moo4:spam4:eggse")
        assert decoder.decode() == {b"cow": b"moo", b"spam": b"eggs"}

    def test_decode_empty_dict(self):
        """Test decoding of empty dictionary."""
        decoder = Decoder(b"de")
        assert decoder.decode() == {}

    def test_decode_nested_dict(self):
        """Test decoding of nested dictionaries."""
        decoder = Decoder(b"d4:dictd3:key5:valueee")
        assert decoder.decode() == {b"dict": {b"key": b"value"}}

    def test_decode_complex_structure(self):
        """Test decoding of complex nested structure."""
        decoder = Decoder(b"d4:listl4:spam4:eggse3:inti42ee")
        assert decoder.decode() == {b"list": [b"spam", b"eggs"], b"int": 42}

    def test_decode_invalid_type(self):
        """Test that invalid bencode raises exception."""
        decoder = Decoder(b"x")
        with pytest.raises(NotImplementedError):
            decoder.decode()

    def test_decode_missing_end_marker(self):
        """Test that missing end marker raises exception."""
        decoder = Decoder(b"i42")
        with pytest.raises(IndexError):
            decoder.decode()

    def test_decode_invalid_string_length(self):
        """Test that invalid string length raises exception."""
        decoder = Decoder(b"5:spam")  # Says 5 bytes but only 4
        with pytest.raises(IndexError):
            decoder.decode()


class TestEncoder:
    """Test suite for the Bencode Encoder."""

    def test_encode_string(self):
        """Test encoding of strings."""
        encoder = Encoder()
        assert encoder.encode(b"spam") == b"4:spam"

    def test_encode_empty_string(self):
        """Test encoding of empty string."""
        encoder = Encoder()
        assert encoder.encode(b"") == b"0:"

    def test_encode_integer(self):
        """Test encoding of positive integers."""
        encoder = Encoder()
        assert encoder.encode(42) == b"i42e"

    def test_encode_negative_integer(self):
        """Test encoding of negative integers."""
        encoder = Encoder()
        assert encoder.encode(-42) == b"i-42e"

    def test_encode_zero(self):
        """Test encoding of zero."""
        encoder = Encoder()
        assert encoder.encode(0) == b"i0e"

    def test_encode_list(self):
        """Test encoding of lists."""
        encoder = Encoder()
        assert encoder.encode([b"spam", b"eggs"]) == b"l4:spam4:eggse"

    def test_encode_empty_list(self):
        """Test encoding of empty list."""
        encoder = Encoder()
        assert encoder.encode([]) == b"le"

    def test_encode_nested_list(self):
        """Test encoding of nested lists."""
        encoder = Encoder()
        assert encoder.encode([[b"spam"]]) == b"ll4:spamee"

    def test_encode_dict(self):
        """Test encoding of dictionaries."""
        encoder = Encoder()
        # Dict keys are sorted alphabetically in bencode
        assert (
            encoder.encode({b"spam": b"eggs", b"cow": b"moo"})
            == b"d3:cow3:moo4:spam4:eggse"
        )

    def test_encode_empty_dict(self):
        """Test encoding of empty dictionary."""
        encoder = Encoder()
        assert encoder.encode({}) == b"de"

    def test_encode_nested_dict(self):
        """Test encoding of nested dictionaries."""
        encoder = Encoder()
        assert (
            encoder.encode({b"dict": {b"key": b"value"}}) == b"d4:dictd3:key5:valueee"
        )

    def test_encode_complex_structure(self):
        """Test encoding of complex nested structure."""
        encoder = Encoder()
        data = {b"list": [b"spam", b"eggs"], b"int": 42}
        # Keys are sorted: "int" comes before "list"
        assert encoder.encode(data) == b"d3:inti42e4:listl4:spam4:eggsee"

    def test_encode_dict_sorts_keys(self):
        """Test that dictionary keys are sorted."""
        encoder = Encoder()
        data = {b"z": b"last", b"a": b"first", b"m": b"middle"}
        assert encoder.encode(data) == b"d1:a5:first1:m6:middle1:z4:laste"

    def test_encode_invalid_type(self):
        """Test that encoding invalid type raises exception."""
        encoder = Encoder()
        with pytest.raises(NotImplementedError):
            encoder.encode("string")  # str instead of bytes


class TestRoundTrip:
    """Test that encoding and decoding are inverse operations."""

    @pytest.fixture
    def encoder(self):
        return Encoder()

    @pytest.fixture
    def decoder_factory(self):
        """Factory to create decoders with different inputs."""

        def _decoder(data):
            return Decoder(data)

        return _decoder

    def test_roundtrip_string(self, encoder, decoder_factory):
        """Test roundtrip for strings."""
        original = b"hello world"
        encoded = encoder.encode(original)
        decoded = decoder_factory(encoded).decode()
        assert decoded == original

    def test_roundtrip_integer(self, encoder, decoder_factory):
        """Test roundtrip for integers."""
        original = 12345
        encoded = encoder.encode(original)
        decoded = decoder_factory(encoded).decode()
        assert decoded == original

    def test_roundtrip_list(self, encoder, decoder_factory):
        """Test roundtrip for lists."""
        original = [b"a", b"b", b"c", 1, 2, 3]
        encoded = encoder.encode(original)
        decoded = decoder_factory(encoded).decode()
        assert decoded == original

    def test_roundtrip_dict(self, encoder, decoder_factory):
        """Test roundtrip for dictionaries."""
        original = {b"name": b"test", b"value": 123, b"items": [b"a", b"b"]}
        encoded = encoder.encode(original)
        decoded = decoder_factory(encoded).decode()
        assert decoded == original

    def test_roundtrip_complex(self, encoder, decoder_factory):
        """Test roundtrip for complex nested structure."""
        original = {
            b"files": [
                {b"length": 12345, b"path": [b"dir", b"file.txt"]},
                {b"length": 67890, b"path": [b"another.txt"]},
            ],
            b"name": b"test torrent",
            b"piece length": 262144,
            b"pieces": b"hash" * 5,
        }
        encoded = encoder.encode(original)
        decoded = decoder_factory(encoded).decode()
        assert decoded == original


@pytest.mark.parametrize(
    "encoded,expected",
    [
        (b"4:test", b"test"),
        (b"i0e", 0),
        (b"le", []),
        (b"de", {}),
    ],
)
def test_parametrized_decode(encoded, expected):
    """Parametrized test for various decode scenarios."""
    decoder = Decoder(encoded)
    assert decoder.decode() == expected


@pytest.mark.parametrize(
    "data,expected",
    [
        (b"test", b"4:test"),
        (0, b"i0e"),
        ([], b"le"),
        ({}, b"de"),
    ],
)
def test_parametrized_encode(data, expected):
    """Parametrized test for various encode scenarios."""
    encoder = Encoder()
    assert encoder.encode(data) == expected
