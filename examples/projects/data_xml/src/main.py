import xml.etree.ElementTree as ET
node=ET.fromstring("<app><title>PCIDE</title></app>")
print(node.findtext("title"))
