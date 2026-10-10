import struct
raw=struct.pack("<IH",123,7)
print(len(raw),struct.unpack("<IH",raw))
