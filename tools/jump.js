(() => {
  if (window.__jump) return "already: " + JSON.stringify(window.__jump);
  // Self-contained episode sweeper, lives inside one /bmVideo page.
  // Walks this page's own episode directory; per-episode policy:
  //   server total >= len        -> ride (seconds-skip to end instantly)
  //   len > 360 (long)           -> real 90s -> jump to len-150 -> real 60s -> jump to len-40 -> ride
  //   len <= 360 (short)         -> real min(len*0.4,120) -> jump to len-45 -> ride
  // Page timer (=credit) keeps running across episodes; ended -> next episode auto.
  const CID = "312bc914-8e11-421b-b9bc-e900fe1a4e50";
  const S = { ep: "?", state: "init", hops: 0, pending: null, done: 0, skipped: 0, stuck: 0 };
  window.__jump = S; window.__jumpLog = [];

  const token = () => localStorage.getItem("webToken");
  const getJSON = (u) => fetch(u).then(r => r.json()).catch(() => null);
  const dir = new URLSearchParams(location.search).get("directoryId");

  let list = null, pos = 0;
  const loadList = async () => {
    const j = await getJSON(`/portal/main-api/v2/coursePacket/getCourseResourceList?coursePacketId=${CID}&directoryId=${dir}&token=${token()}`);
    list = ((j || {}).data || {}).listdata || [];
    const cur = new URLSearchParams(location.search).get("resourceId");
    pos = Math.max(0, list.findIndex(r => r.SYS_UUID === cur));
    return list;
  };

  const statOf = async (resId) => {
    const j = await getJSON(`/portal/main-api/v2/coursePacket/getResourceUserStatistic?coursePacketId=${CID}&resourceDirectoryId=${resId}&token=${token()}`);
    return (j || {}).data || {};
  };

  const v = () => document.querySelector("video");

  const gotoEpisode = (i) => {
    pos = i; S.hops = 0;
    const q = new URLSearchParams(location.search);
    q.set("resourceId", list[i].SYS_UUID);
    history.pushState({}, "", "/bmVideo?" + q);
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  const planFor = (len) => len > 360
    ? [90, len - 150, Math.min(len - 60, 150), len - 40]
    : [Math.min(len * 0.4, 120), len - 45];

  let busy = false;
  const step = async () => {
    if (busy) return; busy = true;
    try {
      const vv = v();
      if (!vv) { S.state = "no-video"; return; }
      if (location.pathname === "/login") { S.state = "KICKED"; return; }
      if (!list) await loadList();
      const cur = new URLSearchParams(location.search).get("resourceId");
      let i = list.findIndex(r => r.SYS_UUID === cur);
      if (i < 0) i = pos;
      if (i !== pos) { pos = i; S.hops = 0; }
      const ep = list[pos]; const len = (ep || {}).resourceLength || vv.duration || 0;
      S.ep = (ep && ep.name || "").slice(0, 16);
      if (!len) { S.state = "loading"; return; }
      if (vv.readyState === 0 && (vv.paused || !vv.src)) {
        if (++S.stuck > 4) { S.stuck = 0; location.reload(); }
        S.state = "stuck"; return;
      }
      S.stuck = 0;
      const st = await statOf(ep.SYS_UUID);
      if ((st.totalStudyTime || 0) >= len * 0.92) {      // done -> seconds-skip
        S.state = "ride-done";
        if (vv.duration) vv.currentTime = vv.duration - 1;
        vv.play().catch(() => {});
        return;
      }
      const plan = planFor(len);
      if (vv.paused) { vv.play().catch(() => {}); }
      if (S.pending) { S.state = "play"; return; }
      if (vv.duration - vv.currentTime <= 2 && !vv.ended) { S.state = "riding"; return; }
      if (S.hops < plan.length) {
        const target = Math.min(Math.max(plan[S.hops], 5), len - 2);
        if (vv.currentTime < target) {
          const wait = Math.max(1, target - vv.currentTime);
          S.state = `play->${Math.round(target)}`;
          S.pending = setTimeout(() => { S.pending = null;
            const x = v(); if (x && x.duration) { x.currentTime = Math.min(target, x.duration - 2); S.hops++; } }, wait * 1000);
        } else S.hops++;
      } else {
        S.state = "riding";
        if (vv.duration) vv.currentTime = Math.min(plan[plan.length - 1], vv.duration - 2);
      }
    } finally { busy = false; }
  };
  setInterval(step, 6000); step();
  return "jump3 installed";
})()
