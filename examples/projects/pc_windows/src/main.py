from pcide.runtime_api import list_windows
windows=list_windows()
print("window_count",len(windows))
for window in windows[:5]: print(window["title"])
