import base64
raw="中文".encode("utf-8")
encoded=base64.b64encode(raw)
print(base64.b64decode(encoded).decode("utf-8"))
