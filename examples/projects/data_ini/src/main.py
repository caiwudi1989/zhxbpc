import configparser,io
c=configparser.ConfigParser()
c.read_string("[app]\nwidth=640\n")
print(c.getint("app","width"))
