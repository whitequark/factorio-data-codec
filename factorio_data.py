import typing
import enum
import struct
import json


class ImmutableString:
    value: typing.Union[None, bytes]

    def __init__(self, value: typing.Union[None, bytes]):
        self.value = value

    @classmethod
    def load(cls, stream: typing.BinaryIO):
        is_none, = struct.unpack("<B", stream.read(1))

        if is_none:
            return cls(None)

        else:
            value_len, = struct.unpack("<B", stream.read(1))
            if value_len == 0xff:
                value_len, = struct.unpack("<I", stream.read(4))

            return cls(stream.read(value_len))

    def save(self, stream: typing.BinaryIO):
        stream.write(struct.pack("<B", self.value is None))

        if self.value is not None:
            if len(self.value) >= 0xff:
                stream.write(struct.pack("<BI", 0xff, len(self.value)))
            else:
                stream.write(struct.pack("<B", len(self.value)))

            stream.write(self.value)

    def __eq__(self, other):
        return self.value == other.value

    def __repr__(self):
        return f"ImmutableString({self.value!r})"


class PropertyTree:
    class Type(enum.Enum):
        Null        = 0 # originally `None`
        Bool        = 1
        Number      = 2
        String      = 3
        List        = 4
        Dictionary  = 5

    key: ImmutableString
    value: typing.Union[None, bool, float, ImmutableString, list]
    type: Type
    any_type: bool

    def __init__(self,
            key: typing.Union[None, ImmutableString],
            value: typing.Union[bool, float, ImmutableString, list],
            type: Type,
            any_type: bool = False
    ):
        if key is None:
            key = ImmutableString(None)

        self.key = key
        self.value = value
        self.type = type
        self.any_type = any_type

    @classmethod
    def load(cls, stream: typing.BinaryIO):
        value_type_raw, any_type, = struct.unpack("<BB", stream.read(2))
        value_type = cls.Type(value_type_raw)

        if value_type == cls.Type.Null:
            value = None

        if value_type == cls.Type.Bool:
            value, = struct.unpack("<B", stream.read(1))
            value = bool(value)

        if value_type == cls.Type.Number:
            value, = struct.unpack("<d", stream.read(8))

        if value_type == cls.Type.String:
            value = ImmutableString.load(stream)

        if value_type in (cls.Type.List, cls.Type.Dictionary):
            count, = struct.unpack("<I", stream.read(4))
            value = []

            for _ in range(count):
                key = ImmutableString.load(stream)
                item = cls.load(stream)
                item.key = key
                value.append(item)

        return cls(None, value, value_type, bool(any_type))

    def save(self, stream: typing.BinaryIO):
        stream.write(struct.pack("<BB", self.type.value, self.any_type))

        if self.type == self.Type.Null:
            pass

        if self.type == self.Type.Bool:
            stream.write(struct.pack("<B", self.value))

        if self.type == self.Type.Number:
            stream.write(struct.pack("<d", self.value))

        if self.type == self.Type.String:
            self.value.save(stream)

        if self.type in (self.Type.List, self.Type.Dictionary):
            stream.write(struct.pack("<I", len(self.value)))

            for item in self.value:
                item.key.save(stream)
                item.save(stream)

    def __eq__(self, other):
        return (self.key == other.key and self.value == other.value and
                self.type == other.type and self.any_type == other.any_type)

    def __repr__(self):
        return f"PropertyTree({self.key.value!r}, {self.value!r}, {self.type!r}, anyType={self.any_type!r})"


class ModSettings:
    data: PropertyTree
    version: typing.Tuple[int, int, int, int]
    has_quality: bool

    def __init__(self, data: PropertyTree, version: typing.Tuple[int, int, int, int], has_quality: bool):
        self.data = data
        self.version = version
        self.has_quality = has_quality

    @classmethod
    def load(cls, stream: typing.BinaryIO):
        # Factorio 1.1.110 becomes (1, 1, 110, 0)
        version = struct.unpack("<HHHH", stream.read(8))
        has_quality, = struct.unpack("<B", stream.read(1))
        data = PropertyTree.load(stream)

        if version < (0, 18, 0, 0):
            raise Exception(f"Cannot load settings from Factorio {version!r}: settings version too low")

        return cls(data, version, bool(has_quality))

    def save(self, stream: typing.BinaryIO):
        stream.write(struct.pack("<HHHH", *self.version))
        stream.write(struct.pack("<B", self.has_quality))
        self.data.save(stream)

    def __eq__(self, other):
        return self.data == other.data and self.version == other.version and self.has_quality == other.has_quality

    def __repr__(self):
        return f"ModSettings({self.data!r}, version={self.version!r}, has_quality={self.has_quality!r})"


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ImmutableString):
            if obj.value is None:
                return None
            else:
                return obj.value.decode()

        if isinstance(obj, PropertyTree):
            if obj.type == PropertyTree.Type.Null:
                return None

            if obj.type == PropertyTree.Type.Bool:
                return obj.value

            if obj.type == PropertyTree.Type.Number:
                return obj.value # this might not round-trip if it gets rounded

            if obj.type == PropertyTree.Type.String:
                return obj.value

            if obj.type == PropertyTree.Type.List:
                return [item for item in obj.value]

            if obj.type == PropertyTree.Type.Dictionary:
                return {item.key.value.decode(): item for item in obj.value}

        if isinstance(obj, ModSettings):
            return {
                "!type": "ModSettings",
                "version": obj.version,
                "has_quality": obj.has_quality,
                "data": obj.data
            }

        return super().default(obj)


class JSONDecoder(json.JSONDecoder):
    def __init__(self, strict=True):
        super().__init__(object_hook=self.object_hook, strict=strict)

    def object_hook(self, obj):
        if obj is None:
            return PropertyTree(None, None, PropertyTree.Type.Null)

        if isinstance(obj, bool):
            return PropertyTree(None, obj, PropertyTree.Type.Bool)

        if isinstance(obj, float):
            return PropertyTree(None, obj, PropertyTree.Type.Number)

        if isinstance(obj, str):
            return PropertyTree(None, ImmutableString(obj.encode()), PropertyTree.Type.String)

        if isinstance(obj, list):
            return PropertyTree(None, obj, PropertyTree.Type.List)

        if isinstance(obj, dict):
            if "!type" in obj:
                if obj["!type"] == "ModSettings":
                    return ModSettings(obj["data"], (*obj["version"],), obj["has_quality"])
                else:
                    raise Exception(f"Unknown object type {obj['!type']}")

            else:
                items = []
                for key, value in obj.items():
                    item = self.object_hook(value)
                    item.key = ImmutableString(key.encode())
                    items.append(item)

                return PropertyTree(None, items, PropertyTree.Type.Dictionary)

        if isinstance(obj, PropertyTree):
            return obj

        raise NotImplementedError(f"Cannot convert {obj!r}")


def selftest():
    with open("example-mod-settings.dat", "rb") as selftest_dat:
        settings_1 = ModSettings.load(selftest_dat)
    json_data = json.dumps(settings_1, indent=2, cls=JSONEncoder)
    settings_2 = json.loads(json_data, cls=JSONDecoder)
    with open("roundtrip-mod-settings.dat", "wb") as roundtrip_dat:
        settings_2.save(roundtrip_dat)

    assert settings_1 == settings_2
    assert open("example-mod-settings.dat", "rb").read() == open("roundtrip-mod-settings.dat", "rb").read()


def main():
    import sys
    import argparse
    import io

    parser = argparse.ArgumentParser(description="""
    Converts Factorio settings in `mod-settings.dat` to JSON and back.
    """)
    parser.add_argument("input", type=argparse.FileType("rb"),
        help="Input file (.dat or .json).")
    parser.add_argument("output",  type=argparse.FileType("wb"), nargs='?',
        help="Output file (.json or .dat). Based on the input filename if omitted.")

    args = parser.parse_args()

    if args.input.name.endswith(".dat"):
        print(f"Reading DAT file '{args.input.name}'...", file=sys.stderr)
        mod_settings = ModSettings.load(args.input)
        default_output_name = args.input.name[:-4] + ".json"

    elif args.input.name.endswith(".json"):
        print(f"Reading JSON file '{args.input.name}'...", file=sys.stderr)
        mod_settings = json.load(args.input, cls=JSONDecoder)
        default_output_name = args.input.name[:-5] + ".dat"

    else:
        print(f"Input filename '{args.input.name}' does not end with .dat or .json.", file=sys.stderr)
        sys.exit(1)

    output = args.output
    if output is None:
        output = open(default_output_name, "wb")

    if output.name.endswith(".dat"):
        print(f"Writing DAT file '{output.name}'...", file=sys.stderr)
        mod_settings.save(output)

    elif output.name.endswith(".json"):
        print(f"Writing JSON file '{output.name}'...", file=sys.stderr)
        text_output = io.TextIOWrapper(output, encoding="utf-8")
        json.dump(mod_settings, text_output, indent=4, cls=JSONEncoder)

    else:
        print(f"Output filename '{output.name}' does not end with .dat or .json.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # selftest()
    main()
