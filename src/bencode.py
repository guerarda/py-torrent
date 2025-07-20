class Decoder:
    def __init__(self, source: bytes):
        self.source = source
        self.current = 0
        self.contents = None

    def decode(self) -> bytes | int | list | dict | None:
        return self.decode_one()

    def decode_one(self) -> bytes | int | list | dict:
        c = self.peek()
        match c:
            case _ if c.isdigit():
                return self.read_string()

            case b"i":
                return self.read_integer()

            case b"l":
                return self.read_list()

            case b"d":
                return self.read_dict()

            case _:
                raise NotImplementedError

    def read_string(self) -> bytes:
        len = self.read_number()
        self.expect(b":")

        string = bytearray()
        for _ in range(len):
            string += self.advance()

        return bytes(string)

    def read_integer(self) -> int:
        self.expect(b"i")

        n = self.read_number()

        # if n == 0 and (self.current - start > 1):
        #     raise ValueError("Invalid encoding for the integer 0")

        # if chr(self.source[start]) == "0":
        #     raise ValueError("Integer encoded with leading zero is invalid")

        self.expect(b"e")

        return n

    def read_list(self) -> list:
        self.expect(b"l")

        lst = []
        while self.peek() != b"e":
            lst.append(self.decode_one())

        self.expect(b"e")

        return lst

    def read_dict(self) -> dict:
        self.expect(b"d")

        keys = []
        values = []

        while self.peek() != b"e":
            k = self.read_string()
            # if keys and k < keys[-1]:
            #     raise ValueError(
            #         f"Dictionary keys are not sorted. '{k}' after '{keys[-1]}'"
            #     )

            keys.append(k)
            values.append(self.decode_one())

        self.expect(b"e")

        return dict(zip(keys, values))

    def read_number(self) -> int:
        number = b""
        while self.peek() in b"0123456789-":
            number += self.advance()
        return int(number)

    def peek(self) -> bytes:
        return self.source[self.current].to_bytes()

    def advance(self) -> bytes:
        c = self.source[self.current]
        self.current += 1
        return c.to_bytes()

    def expect(self, char: bytes) -> bytes:
        if self.peek() != char:
            raise ValueError(f"Expected {char}, got {self.peek()} instead")

        return self.advance()

    def is_at_end(self) -> bool:
        return self.current >= len(self.source)


class Encoder:
    def encode(self, obj: bytes | int | list | dict) -> bytes:
        return self.encode_one(obj)

    def encode_one(self, obj: bytes | int | list | dict) -> bytes:
        match obj:
            case dict():
                return self.encode_dict(obj)

            case list():
                return self.encode_list(obj)

            case int():
                return self.encode_int(obj)

            case bytes():
                return self.encode_string(obj)

            case _:
                raise NotImplementedError

    def encode_string(self, s: bytes) -> bytes:
        return str(len(s)).encode() + b":" + s

    def encode_int(self, i: int) -> bytes:
        return f"i{i}e".encode()

    def encode_list(self, lst: list) -> bytes:
        bstr = bytearray(b"l")
        for i in lst:
            bstr += self.encode_one(i)
        bstr += b"e"
        return bytes(bstr)

    def encode_dict(self, d: dict) -> bytes:
        bstr = bytearray(b"d")
        for k, v in sorted(d.items()):
            bstr.extend(self.encode_string(k))
            bstr.extend(self.encode_one(v))
        bstr += b"e"
        return bytes(bstr)
