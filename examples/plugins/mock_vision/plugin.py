from pcide.runtime_api import ocr_mock, yolo_mock


def plugin_entry(request):
    params = request.get("params", {})
    if request["capability"] == "ocr":
        return ocr_mock(params.get("image", "screen"), params.get("text", "OK"))
    return yolo_mock(params.get("image", "screen"), params.get("label", "object"))
