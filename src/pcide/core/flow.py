from __future__ import annotations

import graphlib
import math
import threading
import time
from dataclasses import dataclass

from .runtime_api import ocr_mock, screenshot_mock, yolo_mock

NODE_KINDS = ("log", "sleep", "screenshot.mock", "ocr.mock", "yolo.mock", "fail", "plugin.call")


class FlowError(ValueError):
    pass


def validate_flow(flow):
    if not isinstance(flow, dict) or flow.get("version", 1) != 1:
        raise FlowError("unsupported flow schema")
    nodes, edges = flow.get("nodes"), flow.get("edges", [])
    if not isinstance(nodes, list) or len(nodes) > 256 or not isinstance(edges, list) or len(edges) > 1024:
        raise FlowError("invalid flow nodes/edges")
    ids = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise FlowError("invalid node identity")
        if node["id"] in ids:
            raise FlowError("duplicate node identity")
        ids.add(node["id"])
        if node.get("kind") not in NODE_KINDS or not isinstance(node.get("config", {}), dict):
            raise FlowError("unknown node kind/config")
        if node["kind"] == "sleep":
            seconds = node.get("config", {}).get("seconds", 0)
            if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 <= seconds <= 3600:
                raise FlowError("sleep seconds must be 0..3600")
        position = node.get("position", [0, 0])
        if not isinstance(position, list) or len(position) != 2 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in position):
            raise FlowError("invalid node position")
    graph = {node_id: set() for node_id in ids}
    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2 or any(value not in ids for value in edge):
            raise FlowError("edge references unknown node")
        graph[edge[1]].add(edge[0])
    try:
        tuple(graphlib.TopologicalSorter(graph).static_order())
    except graphlib.CycleError as exc:
        raise FlowError("flow cycle detected") from exc
    return flow


@dataclass
class FlowResult:
    ok: bool
    outputs: list
    error: str = ""
    cancelled: bool = False


class FlowRunner:
    def __init__(self, max_nodes=256):
        self.max_nodes = max_nodes
        self.cancel_event = threading.Event()
        self.lock = threading.Lock()

    def cancel(self):
        self.cancel_event.set()

    def run(self, flow, timeout=30, on_output=None, registry=None):
        if not self.lock.acquire(blocking=False):
            return FlowResult(False, [], "flow is already active")
        self.cancel_event.clear()
        outputs = []
        deadline = time.monotonic() + timeout
        try:
            validate_flow(flow)
            nodes = {n["id"]: n for n in flow["nodes"]}
            dependencies = {n: set() for n in nodes}
            for source, target in flow.get("edges", []):
                dependencies[target].add(source)
            for node_id in graphlib.TopologicalSorter(dependencies).static_order():
                if self.cancel_event.is_set():
                    return FlowResult(False, outputs, "cancelled", True)
                if time.monotonic() >= deadline:
                    return FlowResult(False, outputs, "flow timeout")
                node = nodes[node_id]
                kind, config = node["kind"], node.get("config", {})
                if kind == "sleep":
                    seconds = config.get("seconds", 0)
                    remaining = max(0, deadline - time.monotonic())
                    if self.cancel_event.wait(min(seconds, remaining)):
                        return FlowResult(False, outputs, "cancelled", True)
                    if seconds >= remaining or time.monotonic() >= deadline:
                        return FlowResult(False, outputs, "flow timeout")
                    result = {"seconds": seconds}
                elif kind == "log":
                    result = {"message": str(config.get("message", ""))}
                elif kind == "screenshot.mock":
                    result = screenshot_mock(config.get("name", "screen"))
                elif kind == "ocr.mock":
                    result = ocr_mock(config.get("image", "screen"), config.get("text", "OK"))
                elif kind == "yolo.mock":
                    result = yolo_mock(config.get("image", "screen"), config.get("label", "object"))
                elif kind == "plugin.call":
                    if registry is None:
                        raise FlowError("plugin registry unavailable")
                    result = registry.call(config["plugin"], config["capability"], config.get("params", {}), max(.1, deadline - time.monotonic()))
                else:
                    raise FlowError(config.get("message", "explicit flow failure"))
                record = {"node": node_id, "result": result}
                outputs.append(record)
                if on_output:
                    on_output(record)
            return FlowResult(True, outputs)
        except Exception as exc:
            return FlowResult(False, outputs, str(exc))
        finally:
            self.lock.release()
