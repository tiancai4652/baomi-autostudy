---
name: baomi-autostudy
description: 自动完成"保密观/中国保密在线"(baomi.org.cn) 年度保密教育培训的在线课时挂机。需要本地 camofox-browser 服务（MCP camofox_* 工具）且 userId=baomi 已登录。USE WHEN 过保密观课时, baomi 学时, 保密教育挂课, 中国保密在线学习, 攒学时, 学时不够, 看保密课. NOT FOR 其他网站。
---

# 保密观（baomi.org.cn）自动过课

## 机制（已实测逆向，2026-09 有效）

- 登录：账号密码 + 滑块，无 API 登录。**Edge/手机 App 同账号会互踢**（单点登录）：挂机期间人别在别处登保密观，被踢后页面跳 `/login`（登录态需人工重登一次并固化）。
- 课程页 → 点 `.course-item` → 弹新 tab `/bmVideo?...` 播放器。
- 播放器前端有"页面计时器"`playItem.studyTime`：**每秒 +1**（与倍速、seek 无关），
  每 5 分钟（300s）心跳上报一次 `saveCoursePackage.do`，页面 ended/切集/卸载时也上报。
- 服务端认账：按"每次上报的计时器值"对该集 `totalStudyTime` 取 **max 累计**，上限 = 该集时长 `resourceLength`。
- **计时器跨集接力**：同一页面里切集（commonMeth 路径）计时器不清零；但**ended 后 SPA 常不自动接力**（实测），
  要靠调度器"关闭旧页→点击开下一集"，重开页计时器从 0 起。
- 所以"进度可以跳，但要讲技巧"：倍速/seek **不增加**认账（认账=计时器=页面秒数），
  但 seek 到结尾可提前触发切集，让计时器无间断滚到下一集。
- **多开并行**：不同 sessionKey 的多个播放器 tab 各自计时、各自心跳，服务端按集分别 max 累计 → 学时线性加速。
- 学时换算：**grade = 累计认账秒 / ~2550**（实测 25371s → 4.08；单集认账封顶片长）。
  全课 41 集、总时长 13872s ≈ 5.40 学时，**需 4.00 学时** ≈ 2880s 认账。
- 考试：学满 4.00 解锁。20 题（单选15+判断5）、60 合格、90 优秀；不限次数不限时，最高分计入证书。

## 前置条件

1. [camofox-browser](https://github.com/jo-inc/camofox-browser) 在跑：`curl -s localhost:9377/health`。
2. camofox 用户 `userId=baomi` 已登录且持久化（`~/.camofox/profiles/` 有该用户的 storage-state）。
   首次登录/登录失效时（桌面模式人工登录一次）：
   ```bash
   CAMOFOX_INTERACTIVE=desktop node server.js   # 在 camofox-browser 目录
   curl -X POST localhost:9377/tabs -H 'content-type: application/json' \
     -d '{"userId":"baomi","sessionKey":"login","url":"https://www.baomi.org.cn/"}'
   # 在弹出的窗口人工登录（账号密码+滑块），然后固化：
   curl -X DELETE localhost:9377/sessions/baomi
   ```

## 工具脚本（本仓库 tools/）

```bash
python3 tools/baomi.py totals     # 服务端权威学时 {grade,total,studyRes}
python3 tools/baomi.py episodes   # 课程页列（含 status0=待学习）
python3 tools/baomi.py start 3    # 点第3个课程项 → 自动抓新播放器 tab
python3 tools/sup4.py 4           # 学时调度器：维持4页并行、精确开集、自愈、到4.00自动停
python3 tools/jump.js             # （由调度器注入页面）片长自适应分段跳+已完成秒过
```

或直接调 camofox REST/MCP（`camofox_*` 工具，userId 固定 `baomi`）：
- 开播放器：POST /tabs `{"userId":"baomi","sessionKey":"studyN","url":"<bmVideo链接>"}`
- 查状态：evaluate `document.querySelector("video").currentTime`
- 查学时：GET `/portal/main-api/v2/coursePacket/getCourseUserStatistic?coursePacketId=312bc914-8e11-421b-b9bc-e900fe1a4e50&token=<localStorage.webToken>`（在已登录页面上下文里 fetch）

## 标准作业流程（2026-09-15 实测跑通：1.19→4.08 用时 105 分钟）

1. `tools/baomi.py totals` 看当前学时；课程页（sessionKey=main）确认登录。
2. 起调度器：`python3 tools/sup4.py 4`（4 页并行）；赶时间可再起一个
   `python3 tools/sup4.py 3`（重叠部分由已完成秒过消化）。日志自定。
3. jump3（`~/tools/baomi/jump.js`）在每个播放器页内自治：
   - 查服务端该集 `totalStudyTime >= 0.92×片长` → seek 到末尾秒过（**已完成集不重复看**）
   - 未完成：按片长分段"真实播一段→seek 下一段"，尾部真实看完触发 ended
   - 死帧（readyState=0）自动 reload 自愈
4. sup4 负责：从课程页 DOM **精确点击**开指定集（点 i 项开的可能偏移，靠队列顺序消化）、
   ended-stuck>45s 关闭重开、tab 消失自动补位、轮询 totals、`grade>=4.00` 自动收工。
5. 收尾（必须按此顺序，保证账目完整）：先逐个 DELETE `/tabs/{id}`（触发 beforeunload 上报），
   再 DELETE `/sessions/baomi`（固化 storage-state 并关浏览器），复查 totals。
6. 达到 4.00 后：考试（见下节）→ 课程页"证书"栏输入姓名下载打印。

实测性能：4 页 ≈ +0.07 学时/分钟，7 页 ≈ +0.1；单页认账速率 = 真实秒数。
课程总时长 13872s（3.85 小时），0→4.00 单页理论 72h，4 页并行实测从 1.19 到 4.08 用 1.8 小时。

## 考试（2026-09-15 实测：80→100 分，证书已出）

流程：课程页左栏"考试"→ 开始考试（`/bmExam`）→ 20 题（单选15+判断5）→ 交卷 → `/bmExamResult` → 课程页"证书"生成证书号。

**题库机制（血泪教训）：**
- 题库大、每次**随机抽题**、**选项乱序** —— 绝不按"第 N 题选 X"位置表答，必须按**题干关键词 → 选项内容**匹配（`bank.json` 已沉淀 44 题）。
- 结果页 `/bmExamResult` 会**完整公布正确答案** → 错题答案照抄进 bank.json，越考题库越全。
- 不限次数、不限时、最高分记录（80 和 100 都记）。

**操作机制：**
- Element UI radio：**必须用 camofox `click(ref)` 真实点击**（snapshot 里 `radio "A. xxx" [e23]`）。
  JS 里 `el.click()` 偶发不同步 Vue model（实测 80 分那次就是 2 题没落上）。
- snapshot 的 radio 是**平铺**的，分组要用 evaluate 按 `.el-radio-group` 拿题文 + 选项，
  两边按 `选项文本` 对齐后取 ref。
- **交卷按钮**：`div/span 文本==="交卷"` 的 JS click 可用；交卷瞬间 evaluate 会 500（页面跳转），忽略，10s 后读结果。
- 答题节奏：2.5s/题 + 检查停顿，整卷 2-3 分钟，模拟真人（别 0.5s 一题）。
- 未命中 bank 的题：开研究 tab 用百度搜（camofox 过检测好使），确认答案后补 bank 再交卷。
- **30 分钟空闲回收 session 会连考试页一起关**（实测丢过一次进行中的考试）：答题全程保持 REST 调用不断。

用法：
```bash
python3 exam_take.py            # 答题+自检（不交卷）
python3 exam_take.py x --submit # 交卷并读分
# 未命中 bank 的题会列出来：研究 tab 搜答案 -> 补 bank.json -> 重跑（交卷前题目不落错）
```

## 坑

- aliplayer 倍速只在当集生效，切集回 1x；倍速不影响认账，别费劲。
- seek 到结尾 ≠ 完成该集，认账仍以计时器为准。
- `resourceLength` 单位是秒；**学时 = 累计认账秒 / ~2550**（实测 25371s→4.08；单集封顶片长）。
- 页面卸载（关 tab）瞬间会最后一次上报，正常关不丢数据。
- 心跳周期 300s，上报延迟最多 5 分钟才见涨，别误判为失败。
- session 30 分钟无 REST 调用即空闲回收（学习页、考试页全没）；长任务保持轮询。
- camoufox 启动报 "manifest.json is missing"：UBO 解包目录丢失，修复
  `unzip -o ubo.xpi -d ~/Library/Caches/camoufox/Camoufox.app/Contents/Resources/addons/UBO`
  （xpi 从 addons.mozilla.org 下）。
- Edge 与 camofox 同账号互踢（单点登录）：挂机期间人别用 Edge 登保密观。
- 考试按**内容**对答案、用**真实点击**答题 —— 这两条错一条就考不到满分。
