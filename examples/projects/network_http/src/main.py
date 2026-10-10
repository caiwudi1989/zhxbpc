from email.parser import Parser
request="GET /health HTTP/1.1\r\nHost: localhost\r\nAccept: application/json\r\n\r\n"
line,headers=request.split("\r\n",1)
print(line,Parser().parsestr(headers)["Host"])
