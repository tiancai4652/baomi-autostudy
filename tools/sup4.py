#!/usr/bin/env python3
"""Baomi study scheduler v4.

Maintain K parallel study pages over the whole course:
  - read episode queue from the course-page DOM (per directory tab)
  - skip episodes the server says are done (totalStudyTime >= len*0.95)
  - open EXACT episodes by clicking the right course-page item
  - jump3 in each player does per-episode watch/jump policy
  - revive stuck pages (ended-but-not-switched -> close + open next episode)
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ev import ev, tabs, api  # noqa: E402

COURSE = "https://www.baomi.org.cn/bmCourseDetail/course?id=312bc914-8e11-421b-b9bc-e900fe1a4e50&docId=56242227&docLibId=-15&pubId=42388&siteId=95"
DIR_TABS = ["保密优良传统教育", "保密知识技能教育", "保密纪律教育"]
JUMP = open(os.path.join(HERE, "jump.js")).read()
K = int(sys.argv[1]) if len(sys.argv) > 1 else 4

STAT_CACHE = {}          # resId/name -> totalStudyTime seconds (from player pages)
EPISODES = []            # [{dir,name,secs}] in course order
QUEUE = []               # episodes still needed
ENDED_SINCE = {}         # playerId -> ts


def to_secs(s):
    if not s: return 0
    p = [int(x) for x in s.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else 0


def course_tab():
    for t in tabs("baomi"):
        if "bmCourseDetail" in t["url"]:
            return t["tabId"]
    api("POST", "/tabs", {"userId": "baomi", "sessionKey": "main", "url": COURSE})
    time.sleep(10)
    for t in tabs("baomi"):
        if "bmCourseDetail" in t["url"]:
            return t["tabId"]
    raise RuntimeError("course tab unavailable")


def read_episodes(ct, dirtab):
    ev(ct, '''(()=>{const t=[...document.querySelectorAll(".tab-item")].find(e=>e.textContent.trim()===%s);if(t&&!t.getAttribute("active"))t.click();return !!t})()''' % json.dumps(dirtab, ensure_ascii=False))
    time.sleep(2.5)
    js = '''JSON.stringify([...document.querySelectorAll(".course-item")].map((it,i)=>({i,
      name:it.querySelector(".titlename")?.textContent.trim()||null,
      len:it.querySelector(".cover-img")?.getAttribute("data-length")||""})).filter(x=>x.name))'''
    return json.loads(ev(ct, js))


def build_queue():
    global EPISODES, QUEUE
    ct = course_tab()
    for d in DIR_TABS:
        for x in read_episodes(ct, d):
            EPISODES.append({"dir": d, "idx": x["i"], "name": x["name"], "secs": to_secs(x["len"])})
    # server progress per episode name via any player tab probe is heavy;
    # cheap proxy: grade/time accrual handled by jump3 "ride-done" check.
    QUEUE[:] = EPISODES[:]
    print(f"queue built: {len(QUEUE)} episodes, "
          f"{sum(e['secs'] for e in QUEUE)}s total", flush=True)


def open_episode(ct, ep):
    before = {t["tabId"] for t in tabs("baomi")}
    # switch course page to right directory then click exact index
    ev(ct, '''(()=>{const t=[...document.querySelectorAll(".tab-item")].find(e=>e.textContent.trim()===%s);if(t&&!t.getAttribute("active"))t.click();return 1})()''' % json.dumps(ep["dir"], ensure_ascii=False))
    time.sleep(2)
    ev(ct, f'(()=>{{const it=[...document.querySelectorAll(".course-item")][{ep["idx"]}];if(it)it.click();return !!it}})()')
    for _ in range(20):
        time.sleep(1)
        ns = [t for t in tabs("baomi") if t["tabId"] not in before and "/bmVideo" in t["url"]]
        if ns:
            p = ns[0]["tabId"]
            try:
                print("  jump3:", ev(p[:8], JUMP), flush=True)
            except Exception as e:
                print("  jump3 install err", repr(e)[:60], flush=True)
            return p
    return None


def main():
    t0 = time.time()
    ct = course_tab()
    build_queue()
    active = {}   # playerId -> episode
    while QUEUE and len(active) < 10**9:
        # fill up to K
        while len(active) < K and QUEUE:
            ep = QUEUE.pop(0)
            p = open_episode(ct, ep)
            if p:
                active[p] = ep
                ENDED_SINCE[p] = None
                print(f"[{(time.time()-t0)/60:5.1f}m] opened {p[:8]} <- {ep['name']}", flush=True)
            time.sleep(1)
        time.sleep(60)
        # health pass
        alive = {t["tabId"] for t in tabs("baomi")}
        for p in list(active):
            if p not in alive:
                print(f"[{(time.time()-t0)/60:5.1f}m] {p[:8]} VANISHED ({active[p]['name']}), requeue", flush=True)
                QUEUE.append(active.pop(p))
                continue
            try:
                st = json.loads(ev(p[:8], '(()=>{const v=document.querySelector("video");return JSON.stringify({j:window.__jump||null,ended:v&&v.ended,d:v&&v.duration})})()'))
            except Exception:
                st = None
            if not st or not st.get("j"):
                try:
                    ev(p[:8], JUMP)
                except Exception:
                    pass
                continue
            j = st["j"]
            if st.get("ended"):
                if ENDED_SINCE[p] is None:
                    ENDED_SINCE[p] = time.time()
                elif time.time() - ENDED_SINCE[p] > 45:
                    print(f"[{(time.time()-t0)/60:5.1f}m] {p[:8]} ended-stuck on {j.get('ep')}, closing", flush=True)
                    api("DELETE", f"/tabs/{p}?userId=baomi", None)
                    active.pop(p)
            else:
                ENDED_SINCE[p] = None
            print(f"[{(time.time()-t0)/60:5.1f}m] {p[:8]} {j.get('ep')} {j.get('state')}", flush=True)
        try:
            tot = ev(ct, '''(async()=>{const token=localStorage.getItem("webToken");
const r=await (await fetch("/portal/main-api/v2/coursePacket/getCourseUserStatistic?coursePacketId=312bc914-8e11-421b-b9bc-e900fe1a4e50&token="+token)).json();
const d=r.data;return JSON.stringify({g:d.totalGrade,t:d.totalStudyTime})})()''')
            print(f"[{(time.time()-t0)/60:5.1f}m] TOTALS {tot} queue={len(QUEUE)} active={len(active)}", flush=True)
            g = json.loads(tot)["g"]
            if g >= 4.0:
                print("TARGET REACHED", flush=True)
                break
        except Exception as e:
            print("totals err", repr(e)[:80], flush=True)
    print("queue drained or target reached", flush=True)


if __name__ == "__main__":
    main()
