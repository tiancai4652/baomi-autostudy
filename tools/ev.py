#!/usr/bin/env python3
"""Helper: run a JS expression against a camofox tab (userId=baomi).

Usage: ev.py <tabId-prefix> <js-file>        # expression from file
       ev.py <tabId-prefix> -- '<expr>'      # inline expression
Prints the JSON result.
"""
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error

TAB_CACHE = "/tmp/baomi-tabs.json"


def tabs(user="baomi"):
    with urllib.request.urlopen(f"http://localhost:9377/tabs?userId={user}", timeout=30) as r:
        return json.load(r)["tabs"]


def resolve(prefix):
    for t in tabs():
        if t["tabId"].startswith(prefix):
            return t["tabId"]
    sys.exit(f"no tab matching {prefix}")


def ev(tab_prefix, js):
    body = json.dumps({"userId": "baomi", "expression": js}).encode()
    req = urllib.request.Request(
        f"http://localhost:9377/tabs/{resolve(tab_prefix)}/evaluate",
        data=body, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        return f"EVAL-ERR {e.code}: {e.read().decode()[:300]}"
    return out.get("result", out)


def api(method, path, payload=None):
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"http://localhost:9377{path}", data=body,
                                 headers={"content-type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


if __name__ == "__main__":
    prefix = sys.argv[1]
    if sys.argv[2] == "--":
        js = sys.argv[3]
    elif len(sys.argv[2]) < 200 and Path(sys.argv[2]).exists():
        js = open(sys.argv[2]).read()
    else:
        js = sys.argv[2]
    out = ev(prefix, js)
    print(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=1))
