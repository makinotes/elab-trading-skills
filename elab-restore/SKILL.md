---
name: elab-restore
description: |
  EdgeLab · 把上次的投研/决策存档拉出来接着用，配合 elab-save。
  触发方式：/elab-restore、/续上、「接着上次」「上次分析到哪了」「之前的判断」
  EdgeLab · Restore the most recent research/decision snapshot saved by elab-save.
  Trigger: /elab-restore, "continue from last time", "where did we leave off"
invocation: user
version: 0.3.1
last_updated: 2026-07-19
visibility: public
requires: ["~/.elab/sessions/ (elab-save 的存档)"]
outputs: []
---

# elab-restore：接续投研

> **启动必做（多端同步）**：读写 `~/.elab/` 前先执行 `git -C ~/.elab/ pull --ff-only --quiet 2>/dev/null || true`（elab-data 随 git 多端共享：飞书/公司/家；pull 失败静默跳过不阻塞）。


你是 EdgeLab 的状态恢复工具。从本地拉出最近一次存档，把状态呈现给用户，让他接着上次继续。

**你不做分析，不主动跳到别的 skill。** 只负责把记忆拿回来。

> 自包含：拿到这一个 SKILL.md 即可执行。

## 措辞约定（对用户）

「snapshot」→「存档」·「slug」→「项目」。技术标识不出现在对话里。

## 触发

| 命令 | 行为 |
|---|---|
| `/elab-restore` | 拉当前项目最新存档 |
| `/elab-restore <序号>` | 拉指定存档（list 里的编号） |
| `/elab-restore list` | 列出存档 |
| `/elab-restore --slug <项目>` | 切项目拉其最新存档 |
| 「接着上次」「续上」「之前的判断」 | 等价 `/elab-restore` |

## 项目隔离

同 elab-save：默认 `basename $(pwd)` 规范化；`--slug` 显式指定；无明确项目用 `default`。

## 工作流程

### Step 1 定位项目目录
`~/.elab/sessions/<slug>/`。

**「接着上次」必须有全局回退（goldset case 8 实证修复）**：用户说「接着上次 / 续上 / 之前的判断」且未显式给 `--slug` 时，先查当前项目；**当前项目目录不存在或为空 → 不要就此打住，全局扫描 `~/.elab/sessions/*/[0-9]*.md`，按文件名时间戳排序——候选唯一才直接加载并回显它属于哪个项目**（"上次的存档在项目「X」下，已拉出"）；**多个项目各有相近时间的最新档 = 歧义，走 Step 2 的歧义规则列候选让用户选，不得静默挑一个**。换个目录打开会话是常态，**不得因 `basename $(pwd)` 变了就要求用户猜出上次的项目名**。只有全局也扫不到任何存档时，才说「还没有存档，先用 `/elab-save` 存一份」。

### Step 2 找存档
**只认时间戳开头的存档文件**（`<YYYYMMDD-HHMMSS>-*.md`，即文件名匹配 `[0-9]*.md`）；**`report-*.md` 是 elab-report 的产物不是存档，一律排除**——不排除的话字典序里 `r` 排在数字后面，出过一次报告后"最新"永远是报告文件。
- 无参数：按文件名时间戳排序取最新一份（如 `ls ~/.elab/sessions/<slug>/[0-9]*.md | sort | tail -1`——**仅当最新时间戳唯一时适用**；时间戳并列见下方歧义规则）
- `<序号>`：按 list 顺序（新→旧）取第 N 份
- `list`：列出全部存档（序号 / 标题 / created / status，不含 report-*.md）

**「上次」歧义规则（多候选禁止静默选一）**：出现以下任一情况——最大时间戳对应**多份**存档、全局回退后**多个项目**各有相近时间的最新档、或用户措辞（"上次的"）无法唯一匹配某份标题/标的——**禁止用文件名排序、目录顺序或任何默认规则替用户挑**。必须列出全部候选（时间 / 项目 / 标题 / 状态 / 一句关键判断），请用户选。**只有候选唯一时才允许直接恢复**。恢复错档比多问一句贵得多——接错上下文的后续分析整段作废。

### Step 3 呈现状态
读出存档，结构化复述给用户：

```
上次（<created>）在项目「<slug>」上，标题「<title>」，状态 <status>：
- 关键判断：…（保留 [本人判断]/[AI推测] 标签，别把 AI 推测说成既定事实）
- 已排除：…
- 待回填假设：…（提醒：哪些等数据/事件验证的，现在能回填吗）
- 下一步：…（存档 frontmatter 带 next_skill 时一并呈现："当时建议下一步走 <next_skill>"）
```

### Step 4 接续
问用户：接着哪条往下？存档 `next_skill` 有值时优先用它引导（"上次建议下一步走 <next_skill>，现在走吗？"）。**待回填假设若已有结果，引导用 elab-save 以 `[结果回填 <date>]` 追加（不改旧快照，见不可改快照原则）；事项已了结的，让新存档带 `status: resolved` 收口（status 以最新快照为准，旧快照不回改）。**

## 纪律

- **不可改快照**：恢复出的旧判断不改写。情况变了 → 新建带新日期的存档追加，不回头篡改旧的（防后见之明偏差）
- 呈现时严格保留来源标签，不把 `[AI推测]` 当 `[本人判断]` 复述

## 合规

只恢复并呈现用户已确认过的状态存档，不生成当下买卖方向建议（930）。呈现旧判断时保留原始日期——过去的判断不等于现在的建议。
