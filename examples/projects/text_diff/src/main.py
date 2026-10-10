import difflib
print("".join(difflib.unified_diff(["old\n"], ["new\n"], fromfile="v1", tofile="v2")))
