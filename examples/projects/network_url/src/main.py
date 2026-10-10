from urllib.parse import urlencode,urlparse,parse_qs
url="https://example.invalid/search?"+urlencode({"q":"PC 软件"})
print(parse_qs(urlparse(url).query))
