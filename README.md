# baomi-autostudy

2026 年度全国保密教育线上培训（[保密观 / 中国保密在线 baomi.org.cn](https://www.baomi.org.cn)）的 AI agent 自动过课 skill：**学时挂机 + 在线考试 + 证书**。

一次真实任务的全程沉淀：学时 0 → 4.08（105 分钟）→ 考试 100 分优秀 → 证书秒出。

> ⚠️ 合规提示：本仓库为学习/研究性质的自动化工具，仅适用于本人账号完成单位要求的普法培训。
> 平台侧年度培训通常不计入任何资格认证，但请自行评估所在单位的合规要求，风险自负。

## 它解决什么

年度保密教育培训要求：**看满 4 学时（≈4 小时视频）→ 20 题在线考试（60 合格/90 优秀，不限次数）**。
纯手工 = 盯着浏览器 4 小时。本 skill 让 agent 全程代劳，人只做两件事：**首次登录**、**证书上打印名字**。

## 工作原理（逆向实测，细节见 [SKILL.md](SKILL.md)）

| 机制 | 结论 |
|---|---|
| 学时认账 | 播放器页面的"计时器"秒数（每秒 +1，倍速/seek 不加成），每 5 分钟心跳上报，卸载/播完也上报；服务端按集取 max 累计、封顶片长 |
| 加速手段 | ① 多开页面真并行（每页独立计时）② 分段 seek 提前触发播完切集，让计时器不浪费 ③ 已完成集自动秒过 |
| 登录 | 账号密码 + 滑块，**必须人工一次**；登录态由 camofox 持久化，之后全自动 |
| 考试 | 随机抽题 + **选项乱序** → 必须按"题干关键词→选项内容"匹配题库作答；JS 模拟点击不可靠，必须走 CDP 真实点击 |
| 互踢 | 单点登录：挂机/考试期间本人别在 Edge/App 登同账号 |

## 快速开始

这是个 **agent skill** —— 装好后对 AI 说一句话就行，不用敲命令。

**1) 安装 skill**（三选一，装完重启 agent 会话）：

```bash
# opencode
git clone https://github.com/tiancai4652/baomi-autostudy ~/.config/opencode/skills/baomi-autostudy
# claude code
git clone https://github.com/tiancai4652/baomi-autostudy ~/.claude/skills/baomi-autostudy
# codex（无原生 skills 机制：把 SKILL.md 路径加进 ~/.codex/AGENTS.md 即可）
```

**2) 依赖**（agent 都能自己装，你也可以先跑）：本地 [camofox-browser](https://github.com/jo-inc/camofox-browser)
（隐身浏览器服务 `localhost:9377`）+ Python 3.9+（仅标准库）。首次使用需人工登录一次保密观（agent 会弹窗让你输密码+滑块，之后登录态自动保持）。
也可以直接对 agent 说："帮我装 camofox，然后过2026保密观"。

**3) 开喊**：

```
你：帮我过2026保密观
ai：当前学时 0/4.00。开始挂机学习，4 页并行约需 1-2 小时，我会持续汇报进度…
    （到 4.00 后）学时完成，进入考试：20 题按题库作答，自检 20/20 已选中。交卷？
你：交
ai：考试 100 分（优秀），证书已生成，去课程页"证书"栏输入你的姓名下载打印。
```

agent 会自己命中 SKILL.md 并按里面的 SOP 执行（挂机、考试、证书全流程）。

<details>
<summary>手动命令模式（调试用）</summary>

```bash
python3 tools/sup4.py 4        # 4 页并行挂机，到 4.00 自动停
python3 tools/baomi.py totals  # 查进度
python3 exam_take.py           # 答题自检；exam_take.py x --submit 交卷
```

</details>

## 题库（bank.json）

44 题实测沉淀（题干关键词 → 答案内容）。考试结果页会公布每题正确答案，
跑一次考试即可回填错题 —— 亲测第 1 轮 80 分，回填修正后第 2 轮 **100 分**。
平台换题就重复这个过程，题库只会越滚越全。

## 目录

```
SKILL.md        agent 作业手册（机制逆向 + SOP + 坑列表，先读这个）
bank.json       考试题库（关键词→答案内容）
exam_take.py    考试执行器（真实点击、答题自检、交卷读分）
tools/ev.py     camofox REST 最小封装
tools/baomi.py  学时查询/开集 CLI
tools/sup4.py   学时调度器（并行挂机、自愈、到标自动停）
tools/jump.js   页内跳集脚本（片长自适应分段 seek + 已完成秒过）
```

## 已知边界

- 平台改版即失效风险：机制（计时器/心跳/接口）是 2026-09 逆向的，改版后按 SKILL.md 的"机制"一节重新对
- 挂机期间浏览器 session 30 分钟无调用会被回收（调度器自带轮询保活）
- 倍速、直连 API 伪造上报：实测**不可行/不必要**，别走邪路
