"""执行 YAML 工作流。Shell 默认不执行，HTTP 默认拒绝内网地址。"""

from __future__ import annotations

import ipaddress
import json
import re
from collections import defaultdict
from urllib.parse import urlparse

import yaml

from workflow_hub.expr import ExprError, evaluate

MAX_CONTEXT_BYTES = 16384
KNOWN = {"start", "end", "http", "script", "condition", "delay", "approval", "shell", "agent"}


class WorkflowError(ValueError):
    pass


class SecurityError(WorkflowError):
    pass


class NodeFailed(WorkflowError):
    pass


def parse_workflow(text: str) -> dict:
    data = yaml.safe_load(text)
    validate(data)
    return data


def validate(data: dict) -> None:
    if not isinstance(data, dict):
        raise WorkflowError("工作流必须是映射")
    if data.get("version") != 1:
        raise WorkflowError("只接受 version: 1")
    if not str(data.get("name") or "").strip():
        raise WorkflowError("工作流需要名称")
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 100:
        raise WorkflowError("节点数量必须在 1 到 100")
    ids = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise WorkflowError("节点 id 必须是非空字符串")
        if node.get("type") not in KNOWN:
            raise WorkflowError(f"未知节点类型 {node.get('type')}")
        config = node.get("config") or {}
        retry = int((config.get("retry") or {}).get("max") or 0)
        if retry < 0 or retry > 5:
            raise WorkflowError("重试次数必须在 0 到 5")
        timeout = config.get("timeout_seconds", 30)
        if not isinstance(timeout, (int, float)) or not 0 < float(timeout) <= 300:
            raise WorkflowError("timeout_seconds 必须大于 0 且不超过 300")
        ids.append(node["id"])
    if len(ids) != len(set(ids)):
        raise WorkflowError("节点 id 不能重复")
    declared = data.get("inputs") or []
    if not isinstance(declared, list):
        raise WorkflowError("inputs 必须是列表")
    input_names = []
    for item in declared:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.isidentifier():
            raise WorkflowError("输入名称必须是合法标识符")
        input_names.append(name)
    if len(input_names) != len(set(input_names)):
        raise WorkflowError("输入名称不能重复")
    if sum(1 for node in nodes if node["type"] == "start") != 1:
        raise WorkflowError("必须有且只有一个 start")
    if not any(node["type"] == "end" for node in nodes):
        raise WorkflowError("至少要有一个 end")
    known = set(ids)
    graph = {item: [] for item in ids}
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if source not in known or target not in known:
            raise WorkflowError("边引用了不存在的节点")
        when = edge.get("when")
        if when is True:
            edge["when"] = "true"
        elif when is False:
            edge["when"] = "false"
        when = edge.get("when")
        if when not in (None, "true", "false"):
            raise WorkflowError("边的 when 只能是 true 或 false")
        graph[source].append(target)
    if _cycle(graph):
        raise WorkflowError("工作流不允许循环")


def _cycle(graph: dict) -> bool:
    color = {}

    def walk(node: str) -> bool:
        color[node] = 1
        for nxt in graph[node]:
            if color.get(nxt) == 1 or (color.get(nxt) != 2 and walk(nxt)):
                return True
        color[node] = 2
        return False

    return any(walk(node) for node in graph if color.get(node) != 2)


_URL_VAR = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def fill_http_url(url: str, context: dict) -> str:
    """只替换已经存在的字符串变量。替换后再做公网地址检查。"""

    def replace(match: re.Match) -> str:
        value = context.get(match.group(1))
        if not isinstance(value, str) or not value:
            raise WorkflowError("HTTP 地址里的变量必须是已有的非空字符串")
        return value

    return _URL_VAR.sub(replace, url)


def assert_public_url(url: str, resolver) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SecurityError("HTTP 节点只允许 http 或 https")
    host = parsed.hostname
    try:
        addresses = resolver(host)
    except OSError as exc:
        raise SecurityError("无法确认目标地址，已拒绝请求") from exc
    if not addresses:
        raise SecurityError("目标没有地址，已拒绝请求")
    for raw in addresses:
        addr = ipaddress.ip_address(raw)
        if any(
            (
                addr.is_private,
                addr.is_loopback,
                addr.is_link_local,
                addr.is_multicast,
                addr.is_reserved,
                addr.is_unspecified,
            )
        ):
            raise SecurityError("HTTP 节点拒绝访问内网、本机和链路本地地址")


def _context_size(context: dict) -> None:
    if len(json.dumps(context, ensure_ascii=False).encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise WorkflowError("上下文超过 16384 字节")


def dry_run(workflow: dict) -> dict:
    """只给出依赖顺序。不调用 HTTP、模型、Shell，也不读取审批结果。"""
    validate(workflow)
    nodes = {node["id"]: node for node in workflow["nodes"]}
    incoming = {node_id: 0 for node_id in nodes}
    outgoing = defaultdict(list)
    for edge in workflow.get("edges") or []:
        outgoing[edge["from"]].append(edge["to"])
        incoming[edge["to"]] += 1
    start = next(node["id"] for node in workflow["nodes"] if node["type"] == "start")
    ready = sorted((node_id for node_id, count in incoming.items() if count == 0), key=lambda item: (item != start, item))
    order = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for nxt in outgoing[node_id]:
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
    return {
        "name": workflow["name"],
        "order": order,
        "steps": [{"id": node_id, "type": nodes[node_id]["type"]} for node_id in order],
        "node_count": len(nodes),
        "executed": False,
        "network": False,
        "shell_executed": False,
    }


def execute(workflow: dict, inputs: dict | None = None, transport=None, resolver=None, approvals=None, prior=None, provider=None) -> dict:
    validate(workflow)
    context = dict(inputs or {})
    for item in workflow.get("inputs") or []:
        if item.get("required") and item["name"] not in context:
            raise WorkflowError(f"缺少必填输入 {item['name']}")
    _context_size(context)
    nodes = {node["id"]: node for node in workflow["nodes"]}
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for edge in workflow.get("edges") or []:
        outgoing[edge["from"]].append(edge)
        incoming[edge["to"]].append(edge)
    start = next(node["id"] for node in workflow["nodes"] if node["type"] == "start")
    activated = {start}
    completed = set()
    states = {node_id: "pending" for node_id in nodes}
    logs = []
    attempts = {node_id: 0 for node_id in nodes}
    paused_at = None
    steps = 0
    approvals = dict(approvals or {})
    for node_id, output in (prior or {}).items():
        if node_id not in nodes:
            raise WorkflowError("恢复记录里有未知节点")
        states[node_id] = "succeeded"
        completed.add(node_id)
        activated.add(node_id)
        _restore_context(nodes[node_id], output if isinstance(output, dict) else {}, context)
        _activate(nodes[node_id], output, outgoing[node_id], activated)

    while True:
        steps += 1
        if steps > 200:
            raise WorkflowError("执行步数超过上限")
        ready = []
        for node_id in list(activated):
            if node_id in completed:
                continue
            preds = [edge["from"] for edge in incoming[node_id] if edge["from"] in activated]
            if all(pred in completed for pred in preds):
                ready.append(node_id)
        if not ready:
            break
        for node_id in ready:
            node = nodes[node_id]
            config = node.get("config") or {}
            retry = int((config.get("retry") or {}).get("max") or 0)
            try:
                output = _run_node(node, context, transport, resolver, approvals, provider)
                attempts[node_id] += 1
                states[node_id] = "succeeded"
                completed.add(node_id)
                logs.append({"node": node_id, "status": "succeeded", "output": output})
                _activate(node, output, outgoing[node_id], activated)
            except NodeFailed as exc:
                attempts[node_id] += 1
                logs.append({"node": node_id, "status": "retry", "message": str(exc), "attempt": attempts[node_id]})
                if attempts[node_id] <= retry:
                    continue
                states[node_id] = "failed"
                return _result(workflow, "failed", states, logs, context, attempts, str(exc))
            except SecurityError as exc:
                states[node_id] = "failed"
                logs.append({"node": node_id, "status": "blocked", "message": str(exc)})
                return _result(workflow, "failed", states, logs, context, attempts, str(exc))
            except WorkflowError as exc:
                if str(exc).startswith("等待审批:"):
                    paused_at = node_id
                    states[node_id] = "paused"
                    logs.append({"node": node_id, "status": "paused"})
                    return _result(workflow, "paused", states, logs, context, attempts, None, paused_at)
                states[node_id] = "failed"
                logs.append({"node": node_id, "status": "failed", "message": str(exc)})
                return _result(workflow, "failed", states, logs, context, attempts, str(exc))
    for node_id, state in states.items():
        if state == "pending":
            states[node_id] = "skipped"
    status = "succeeded" if any(nodes[node_id]["type"] == "end" and states[node_id] == "succeeded" for node_id in states) else "failed"
    return _result(workflow, status, states, logs, context, attempts, None if status == "succeeded" else "没有到达 end")


def _restore_context(node, output, context) -> None:
    kind = node["type"]
    config = node.get("config") or {}
    if kind == "script" and config.get("action") == "set":
        key = config.get("key") or ""
        if isinstance(key, str) and key.isidentifier():
            source = config.get("from")
            if isinstance(source, str) and source.isidentifier() and source in context:
                context[key] = context[source]
            else:
                context[key] = config.get("value")
            _context_size(context)
        return
    if kind == "http":
        written = output.get("context")
        if isinstance(written, dict):
            for key, value in written.items():
                if isinstance(key, str) and key.isidentifier():
                    context[key] = value
            _context_size(context)


def _activate(node, output, edges, activated) -> None:
    if node["type"] == "condition":
        value = bool(output.get("value"))
        for edge in edges:
            when = edge.get("when")
            if when is None or (when == "true" and value) or (when == "false" and not value):
                activated.add(edge["to"])
        return
    for edge in edges:
        activated.add(edge["to"])


def _run_node(node, context, transport, resolver, approvals, provider=None):
    kind = node["type"]
    config = node.get("config") or {}
    timeout = float(config.get("timeout_seconds", 30))
    if kind == "start":
        return {"started": True}
    if kind == "end":
        return {"finished": True}
    if kind == "delay":
        seconds = float(config.get("seconds") or 0)
        if seconds < 0:
            raise WorkflowError("等待时间不能为负")
        if seconds > timeout:
            raise WorkflowError("节点超时")
        return {"delayed": seconds}
    if kind == "condition":
        try:
            value = bool(evaluate(config.get("expression") or "false", context))
        except ExprError as exc:
            raise WorkflowError(str(exc)) from exc
        return {"value": value}
    if kind == "script":
        if config.get("action") != "set":
            raise SecurityError("script 节点只允许 action: set，不执行任意代码")
        key = config.get("key") or ""
        if not key.isidentifier():
            raise SecurityError("变量名不合法")
        source = config.get("from")
        if source is not None:
            if not isinstance(source, str) or not source.isidentifier() or source not in context:
                raise SecurityError("script 的 from 必须是已有变量")
            context[key] = context[source]
        else:
            context[key] = config.get("value")
        _context_size(context)
        return {"set": key}
    if kind == "shell":
        return {"executed": False, "status": "pending_approval"}
    if kind == "approval":
        decision = approvals.get(node["id"])
        if isinstance(decision, dict):
            if decision.get("approved") is True:
                return {"approved": True, "by": str(decision.get("by") or "")}
            if decision.get("approved") is False:
                raise NodeFailed("审批被拒绝")
        if decision is True:
            return {"approved": True, "by": ""}
        if decision is False:
            raise NodeFailed("审批被拒绝")
        raise WorkflowError(f"等待审批:{node['id']}")
    if kind == "agent":
        if provider is None:
            raise WorkflowError("没有配置模型提供方，已拒绝发送请求")
        prompt = str(config.get("prompt") or "")
        return {"text": provider.complete(prompt)}
    if kind == "http":
        url = fill_http_url(str(config.get("url") or ""), context)
        assert_public_url(url, resolver or _default_resolver)
        if transport is None:
            raise WorkflowError("没有配置 HTTP 传输，拒绝直接访问网络")
        result = transport(config.get("method") or "GET", url, timeout)
        written = {}
        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(key, str) and key.isidentifier():
                    context[key] = value
                    written[key] = value
            _context_size(context)
        return {"called": True, "context": written}
    raise WorkflowError(f"未实现的节点 {kind}")


def _default_resolver(host: str):
    import socket

    return [item[4][0] for item in socket.getaddrinfo(host, None)]


def _redact_text(text: str) -> str:
    text = re.sub(r"ghp_[A-Za-z0-9]{20,}", "[REDACTED_TOKEN]", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "[REDACTED_TOKEN]", text)
    return text


def _redact_value(value):
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    return value


def _result(workflow, status, states, logs, context, attempts, error, paused_at=None) -> dict:
    return {
        "name": workflow["name"],
        "status": status,
        "states": states,
        "logs": _redact_value(logs),
        "context": _redact_value(context),
        "attempts": attempts,
        "error": error,
        "paused_at": paused_at,
        "shell_executed": False,
    }
