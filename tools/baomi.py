#!/usr/bin/env python3
"""Baomi (baomi.org.cn 保密观) study runner over camofox-browser (userId=baomi).

  totals                 course grade / totalStudyTime from server
  episodes               list episodes visible on the open course tab (name|len|resId)
  start N [--session X]  click the Nth 待学习 episode on the course tab, open a study tab
  watch [--every 60]     poll every page's video pos + server totals until grade >= 4.0
  close --session X      close study tabs of one session
"""
import argparse
import os
import json
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ev import ev, tabs, api  # noqa: E402

USER = "baomi"
COURSE_ID = "312bc914-8e11-421b-b9bc-e900fe1a4e50"

STATE_JS = '''(() => {
  const v = document.querySelector("video");
  if (!v) return "no-video";
  return JSON.stringify({ t: +v.currentTime.toFixed(0), d: v.duration, p: v.paused });
})()'''

TOTALS_JS = '''(async()=>{const token=localStorage.getItem("webToken");
const r=await (await fetch("/portal/main-api/v2/coursePacket/getCourseUserStatistic?coursePacketId=%s&token="+token)).json();
const d=r.data;return JSON.stringify({grade:d.totalGrade,total:d.totalStudyTime,studyRes:d.studyResourceNum})})()''' % COURSE_ID

EPISODES_JS = '''JSON.stringify([...document.querySelectorAll(".course-item")].map(it=>{
  const a=it.querySelector("a")||it.closest("a");
  const m=(it.getAttribute("data-res")||"");
  return {name:it.querySelector(".titlename")?.textContent.trim(),
          status:it.className.match(/status\\d/)?.[0],
          len:it.querySelector(".cover-img")?.getAttribute("data-length")};
}))'''


def course_tab():
    for t in tabs(USER):
        if "/bmCourseDetail/course" in t["url"]:
            return t["tabId"]
    for t in tabs(USER):
        if "baomi.org.cn" in t["url"]:
            return t["tabId"]
    raise SystemExit("no baomi tab. Open the course page first via camofox create_tab.")


def totals():
    return json.loads(ev(course_tab(), TOTALS_JS))


def open_episode_from_course(idx):
    """Click episode idx in the course tab; returns the new player tab id."""
    before = {t["tabId"] for t in tabs(USER)}
    js = '''(()=>{const items=[...document.querySelectorAll(".course-item")];
      items[%d].click();return "clicked %d"})()''' % (idx, idx)
    ev(course_tab(), js)
    for _ in range(30):
        time.sleep(1)
        new = [t for t in tabs(USER) if t["tabId"] not in before and "/bmVideo" in t["url"]]
        if new:
            return new[0]["tabId"]
    raise SystemExit("player tab did not appear")


def cmd_totals(_a):
    print(json.dumps(totals(), ensure_ascii=False))


def cmd_episodes(_a):
    print(ev(course_tab(), EPISODES_JS))


def cmd_start(a):
    tab = open_episode_from_course(a.n)
    print("study tab:", tab)
    time.sleep(8)
    print(ev(tab[:8], STATE_JS))


def cmd_watch(a):
    target = 4.0
    while True:
        line = {"ts": int(time.time()), **totals()}
        pages = []
        for t in tabs(USER):
            if "/bmVideo" in t["url"]:
                try:
                    s = ev(t["tabId"][:8], STATE_JS)
                    pages.append(json.loads(s) if s != "no-video" else s)
                except Exception:
                    pages.append("busy")
        line["pages"] = pages
        print(json.dumps(line, ensure_ascii=False), flush=True)
        if line["grade"] >= target:
            print("GRADE TARGET REACHED", flush=True)
            return
        time.sleep(a.every)


def cmd_close(a):
    for t in tabs(USER):
        if (t.get("listItemId") or "").startswith("study"):
            api("DELETE", f"/tabs/{t['tabId']}?userId={USER}", None)
            print("closed", t["tabId"][:8])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("totals")
    sub.add_parser("episodes")
    p = sub.add_parser("start"); p.add_argument("n", type=int)
    p = sub.add_parser("watch"); p.add_argument("--every", type=int, default=60)
    p = sub.add_parser("close")
    a = ap.parse_args()
    {"totals": cmd_totals, "episodes": cmd_episodes, "start": cmd_start,
     "watch": cmd_watch, "close": cmd_close}[a.cmd](a)
