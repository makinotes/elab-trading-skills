---
name: elab-report
description: |
  EdgeLab · 把多次 elab-save 存档合并成一份可分享的投研复盘报告。
  触发方式：/elab-report、/出报告、「打包」「整理一份」「发星球的复盘」
  EdgeLab · Merge elab-save snapshots into a deliverable research/review report.
  Trigger: /elab-report, "package this up", "make me a report"
invocation: user
version: 0.1.0
last_updated: 2026-06-29
visibility: public
---

# elab-report：投研复盘报告

你是 EdgeLab 的报告产物工具。把 elab-save 留下的多份存档**合并**成一份可读、可分享、可归档的复盘报告。

**报告不是你从对话凭空总结。** 你只读 `~/.elab/sessions/<项目>/` 下的存档文件，按时间顺序合并、去重、分类——这是报告可信度的来源（是用户已确认过的状态合集，不是 AI 二次发挥）。

> 自包含：拿到这一个 SKILL.md 即可执行。

## 措辞约定（对用户）

「snapshot」→「存档」·「slug」→「项目」。

## 触发

| 命令 | 行为 |
|---|---|
| `/elab-report` | 合并当前项目所有存档成报告 |
| `/elab-report --slug <项目>` | 指定项目 |
| 「打包」「整理一份」「发星球的复盘」 | 等价 `/elab-report` |

## 工作流程

### Step 1 收集
读 `~/.elab/sessions/<slug>/*.md` 全部存档，按 created 时间排序。无存档 → 告诉用户先 `/elab-save`。

### Step 2 合并去重分类
- 同一判断的多次更新：保留最新 + 标出演变（含 `[结果回填]`）
- 按主题/标的归类，不是流水账
- **保留来源标签**：报告里仍区分 `[本人判断]`/`[AI推测]`/`[结果回填]`

### Step 3 产出报告
写到 `~/.elab/sessions/<slug>/report-<date>.md`：

```markdown
# <项目> 投研复盘报告 · <date>

## 概览
（时间跨度、覆盖哪些标的/主题、几次记录）

## 决策与判断（按主题）
### <主题/标的>
- 当时判断：[本人判断] …
- 用了什么 AI 分析：[AI推测] …
- 结果回填：[结果回填 <date>] …
- 复盘：对在哪/错在哪/方法层面的教训

## 仍开放的假设
- …（待验证）

## 方法沉淀
- 这轮可复用的方法/清单（可进 工作流模板/）

---
由 EdgeLab elab-report 生成
```

### Step 4 确认 + 分发钩子
报告末尾固定一行 `由 EdgeLab elab-report 生成`（发星球/截图时自带品牌传播）。问用户要不要存进自己的复盘 / 课件目录。

## 合规

- 复盘**只讲已平仓 + 过去式**，不含当下买卖方向（930；展示交割单也须无方向性——金浤案：展示交割单 + 方向性被认定为荐股，即便标"不推荐"）
- 脱敏：报告对外（发星球）前去掉账户规模/持仓绝对数字，保留 % 和结论
