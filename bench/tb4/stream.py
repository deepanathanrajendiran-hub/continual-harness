"""Parse Claude Code stream-json output (Harbor's agent/claude-code.txt) and session JSONL files."""
import json
import re
from pathlib import Path

SUBCOMMANDS = ("doctor", "status", "start", "check", "review", "complete", "abandon", "reopen",
               "recall", "step-begin", "step-attach", "step-finish", "step-recover")
_SUB = re.compile(
    r"(?:(?<![\w.-])harness\.py[\"']?|\$\{?HARNESS\}?[\"']?|--project[ \t]+(?:\"[^\"]*\"|'[^']*'|\S+)|--runtime[ \t]+\S+)"
    r"[ \t]+(" + "|".join(re.escape(s) for s in SUBCOMMANDS) + r")(?![\w-])")
_API = re.compile(r"hit your usage limit|usage limit|rate.?limit|not logged in|invalid api key|"
                  r"authentication|oauth|api error|overloaded", re.I)
# Only the bundled CLI takes --runtime claude (it is required) or lives under skills/horizon; a task's own
# harness.py does neither, so it never counts as a Horizon call.
_HORIZON = re.compile(r"--runtime[ \t=]+[\"']?claude\b|\$\{?HARNESS\b|skills/horizon/")
_USAGE = re.compile(r"hit your [\w ]*limit|usage limit|usage_limit_reached", re.I)
_USAGE_ERRORS = ("rate_limit", "billing_error")
_PROJECT = re.compile(r"""(?:--project[ \t]+|\bPROJECT=)("[^"]*"|'[^']*'|[^\s;&|)]+)""")
_DECODER = json.JSONDecoder()


def parse_lines(text: str) -> list:
    events = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        events.append(obj if isinstance(obj, dict) else {"type": "_raw", "text": stripped})
    return events


def read_events(path: Path) -> list:
    return parse_lines(path.read_text(errors="replace")) if path.exists() else []


def result_record(events):
    return next((e for e in events if e.get("type") == "result"), None)


def init_info(events) -> dict:
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    return {"version": init.get("claude_code_version"), "model": init.get("model")}


def rate_limit_info(events):
    for event in reversed(events):
        if event.get("type") == "rate_limit_event":
            info = event.get("rate_limit_info") or {}
            windows = info.get("unifiedWindows") or {}
            five, seven = windows.get("five_hour") or {}, windows.get("seven_day") or {}
            return {"status": info.get("status"), "five_hour": five.get("utilization"),
                    "five_hour_resets_at": five.get("resetsAt", info.get("resetsAt")),
                    "seven_day": seven.get("utilization"), "seven_day_resets_at": seven.get("resetsAt"),
                    # the window the server says is limiting (e.g. seven_day_sonnet), which unifiedWindows omits
                    "limit_type": info.get("rateLimitType"), "limit_utilization": info.get("utilization"),
                    "limit_resets_at": info.get("resetsAt")}
    return None


def _blocks(event) -> list:
    content = (event.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return ""


def tool_uses(events):
    for event in events:
        if event.get("type") == "assistant":
            for block in _blocks(event):
                if block.get("type") == "tool_use":
                    yield event, block


def tool_results(events) -> dict:
    out = {}
    for event in events:
        if event.get("type") == "user":
            for block in _blocks(event):
                if block.get("type") == "tool_result":
                    out[block.get("tool_use_id")] = (_text(block.get("content")), bool(block.get("is_error")))
    return out


def bash_commands(events) -> list:
    return [str((b.get("input") or {}).get("command") or "") for _, b in tool_uses(events) if b.get("name") == "Bash"]


def json_objects(text: str) -> list:
    out, i = [], 0
    while True:
        j = text.find("{", i)
        if j < 0:
            return out
        try:
            obj, end = _DECODER.raw_decode(text, j)
        except json.JSONDecodeError:
            i = j + 1
            continue
        if isinstance(obj, dict):
            out.append(obj)
        i = end


def horizon_calls(events) -> list:
    results = tool_results(events)
    calls = []
    for event, block in tool_uses(events):
        if block.get("name") != "Bash":
            continue
        command = str((block.get("input") or {}).get("command") or "")
        subcommands = _SUB.findall(command)
        if not subcommands or not _HORIZON.search(command):
            continue
        text, is_error = results.get(block.get("id"), ("", None))
        objects = json_objects(text)
        calls.append({
            "subcommands": subcommands, "command": command, "is_error": is_error,
            "subagent": event.get("parent_tool_use_id") is not None,
            "summaries": [o for o in objects if "slug" in o and "status" in o],
            "errors": [o for o in objects if "error" in o and "message" in o and "slug" not in o],
            "doctor": [o for o in objects if "implementation" in o and "state" in o],
        })
    return calls


def _api_error_text(event):
    kind = event.get("type")
    if kind == "_raw":
        return event["text"][:300] if _API.search(event["text"]) or _USAGE.search(event["text"]) else None
    if kind == "error":
        return json.dumps(event)[:300]
    if kind == "assistant" and (event.get("error") or event.get("is_api_error_message")):
        # 2.1.293 ends a turn on an API error with a synthetic main-session message carrying `error`
        text = _text((event.get("message") or {}).get("content"))
        return f"assistant error={event.get('error') or event.get('api_error')}: {text[:200]}"
    if kind == "result" and (event.get("is_error") or str(event.get("subtype", "")).startswith("error")):
        # name the fields, not a json.dumps prefix: the error fields sit at the end of a 2.1.293 result line
        return (f"result {event.get('subtype')} status={event.get('api_error_status')} "
                f"api_error={event.get('api_error')}: {str(event.get('result') or '')[:200]}")
    if kind == "rate_limit_event":
        status = str((event.get("rate_limit_info") or {}).get("status") or "")
        return None if not status or status.startswith("allowed") else f"rate_limit_event status={status}"
    if kind == "system" and "error" in str(event.get("subtype", "")):
        return json.dumps(event)[:300]
    return None


def terminal_api_error(events):
    """The last API/usage/auth error, unless the main agent spoke again after it (a retry).

    Only a clean main-session assistant event counts as speaking again; the synthetic API-error
    message Claude Code writes when a turn ends on an error is itself an error."""
    last = None
    for index, event in enumerate(events):
        text = _api_error_text(event)
        if text:
            last = (index, text)
    if last is None:
        return None
    index, text = last
    if any(e.get("type") == "assistant" and e.get("parent_tool_use_id") is None and not _api_error_text(e)
           for e in events[index + 1:]):
        return None
    return text

def usage_limit_evidence(events):
    """Why this stream shows a subscription usage or rate limit stop, or None.

    Claude Code 2.1.293 words the stop "You've hit your session limit" (or weekly/Sonnet limit), which
    Harbor's patterns miss, so the structured fields are read directly."""
    for event in events:
        kind = event.get("type")
        if kind == "rate_limit_event":
            status = str((event.get("rate_limit_info") or {}).get("status") or "")
            if status and not status.startswith("allowed"):
                return f"rate_limit_event status={status}"
        elif kind == "assistant" and (event.get("error") in _USAGE_ERRORS
                                      or event.get("api_error") == "usage_limit_reached"):
            return f"assistant error={event.get('error') or event.get('api_error')}"
        elif kind == "result" and (event.get("api_error_status") == 429
                                   or event.get("api_error") == "usage_limit_reached"
                                   or (event.get("is_error") and _USAGE.search(str(event.get("result") or "")))):
            return f"result status={event.get('api_error_status')}: {str(event.get('result') or '')[:200]}"
        elif kind == "_raw" and _USAGE.search(event["text"]):
            return event["text"][:200]
    return None


def ledger_candidates(events, workdir: str) -> list:
    out = []

    def add(path):
        if path not in out:
            out.append(path)

    for call in horizon_calls(events):
        for doctor in call["doctor"]:
            state = doctor.get("state")
            if isinstance(state, str) and state.startswith("/"):
                add(state.rstrip("/"))
    for command in bash_commands(events):
        for match in _PROJECT.finditer(command):
            value = match.group(1).strip("\"'")
            if value.startswith("/") and "$" not in value:
                add(value.rstrip("/") + "/.claude/harness")
    add(workdir.rstrip("/") + "/.claude/harness")
    return out
