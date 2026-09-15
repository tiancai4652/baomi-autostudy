#!/usr/bin/env python3
"""baomi exam taker: bank-driven, real camofox clicks, verified, then submit.

  python3 exam_take.py <tabPrefix>            # answer + verify, NOT submit
  python3 exam_take.py <tabPrefix> --submit   # and submit + read result

Questions are randomly drawn from a large pool with shuffled option order,
so ALWAYS match answers by option TEXT to the bank, never by position.
Unmatched stems -> DDG/baidu search in a research tab, then add to bank.json.
"""
import json
import os
import re
import sys
import time
import urllib.request

BASE = "http://localhost:9377"
USER = "baomi"
BANK = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank.json")))["byKeyword"]


def rest(method, path, payload=None, timeout=120):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ev(tab, js):
    return rest("POST", f"/tabs/{tab}/evaluate", {"userId": USER, "expression": js})["result"]


GROUPS_JS = '''(() => {
  const radios = [...document.querySelectorAll(".el-radio")];
  const m = new Map();
  radios.forEach(r => { const g = r.closest(".el-radio-group");
    if (!m.has(g)) m.set(g, []); m.get(g).push(r); });
  return JSON.stringify([...m.values()].map(g => ({
    stem: g[0].closest(".ques_options-box").previousElementSibling.innerText.replace(/\\s+/g," ").slice(0,160),
    opts: g.map(r => r.innerText.trim())
  })));
})()'''

REFS_JS = None  # snapshot parsed in python


def snapshot_refs(tab):
    snap = rest("GET", f"/tabs/{tab}/snapshot?userId={USER}", None, 90)["snapshot"]
    out = {}
    for m in re.finditer(r'- radio "([A-F])[\.、]\s*([^"]*)" \[e(\d+)\]', snap):
        out[(m.group(1), m.group(2))] = m.group(3)
    return out


def bank_pick(stem, opts):
    for kw, ans in BANK.items():
        if kw in stem:
            hit = [o for o in opts if ans in o or o[2:].strip() in ans or ans[:6] in o]
            if hit:
                return kw, hit[0]
    return None, None


def main():
    tab = None
    for t in rest("GET", f"/tabs?userId={USER}")["tabs"]:
        if "/bmExam" in t["url"]:
            tab = t["tabId"]; break
    if not tab:
        sys.exit("no /bmExam tab open")
    groups = json.loads(ev(tab, GROUPS_JS))
    refs = snapshot_refs(tab)
    print(f"{len(groups)} groups, {len(refs)} radio refs", flush=True)

    unresolved = []
    for i, g in enumerate(groups):
        kw, opt = bank_pick(g["stem"], g["opts"])
        if not opt:
            unresolved.append((i, g["stem"], g["opts"]))
            continue
        letter = opt[0]
        ref = refs.get((letter, opt[3:].strip()))
        if not ref:
            for (L, txt), r in refs.items():
                if L == letter and txt[:8] in opt:
                    ref = r; break
        if not ref:
            unresolved.append((i, g["stem"], g["opts"])); continue
        rest("POST", f"/tabs/{tab}/click", {"userId": USER, "ref": f"e{ref}"})
        print(f"g{i:02d} [{kw[:12]}] -> {opt[:24]}", flush=True)
        time.sleep(2.5)

    if unresolved:
        print("UNRESOLVED — look them up before submit:", flush=True)
        for i, stem, opts in unresolved:
            print(f"  g{i} {stem[:60]} :: {opts}", flush=True)
        sys.exit(2)

    time.sleep(2)
    sel = json.loads(ev(tab, '''(() => {
      const radios = [...document.querySelectorAll(".el-radio")];
      const m = new Map();
      radios.forEach(r => { const g = r.closest(".el-radio-group");
        if (!m.has(g)) m.set(g, []); m.get(g).push(r); });
      return JSON.stringify([...m.values()].map(g => g.some(r => r.className.includes("is-checked"))));
    })()'''))
    print("selected:", sum(sel), "/", len(sel), flush=True)
    if not all(sel):
        sys.exit("NOT ALL SELECTED — abort")

    if "--submit" in sys.argv:
        time.sleep(10)
        try:
            ev(tab, '''(() => {
              const b = [...document.querySelectorAll("div,button,span")]
                .filter(e => e.textContent.replace(/\\s/g,"") === "交卷" && e.childElementCount <= 1);
              b[b.length - 1].click(); return "clicked";
            })()''')
        except Exception:
            pass
        time.sleep(3)
        try:
            ev(tab, '''(() => { const b = [...document.querySelectorAll(".el-message-box__btns button,.el-button")]
              .find(e => /确定|确认/.test(e.textContent)); if (b) b.click(); return 1 })()''')
        except Exception:
            pass
        time.sleep(12)
        href = ev(tab, "location.pathname")
        score = ev(tab, '(document.body.innerText.match(/考试成绩\\s*(\\d+)/)||[])[1]')
        print("after submit:", href, "score:", score, flush=True)


if __name__ == "__main__":
    main()
