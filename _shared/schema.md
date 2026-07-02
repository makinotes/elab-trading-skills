# EdgeLab 共享契约（SSOT）

> 状态目录、存档格式、来源标签的**唯一定义源**。任何 skill 接入状态系统或用来源标签，**引用这里，不各自复述**（防多份文字漂移）。改约定只改这一处。

## 一、目录约定（`~/.elab/`）

| 路径 | 谁写 | 谁读 | 内容 |
|---|---|---|---|
| `~/.elab/sessions/<slug>/<时间戳>-<标题slug>.md` | elab-save | elab-restore / elab-report | 投研状态存档（跨会话记忆） |
| `~/.elab/trades/<标的>/` | elab-trade Mode A | elab-trade | 交易决策四层结构（01_事实/02_规律/03_定格/04_待解） |
| `~/.elab/token` | 安装时写 | elab-research 自研模式 | 会员 `mk_live_` API key（一行） |

- **slug 规范**：默认 `basename $(pwd)`，非 `[a-z0-9-]` 替换成 `-`；家目录/无明确项目 = `default`；显式 `--slug <名>`。
- **时间戳**：`date +%Y%m%d-%H%M%S`（禁猜）。
- **写文件前必 `mkdir -p` 目标目录**。

## 二、session 存档 frontmatter（elab-save 写 / elab-restore 读）

```yaml
---
title: <标题>
slug: <项目>
created: <YYYY-MM-DD>
status: open | resolved
source_skill: <来自哪个 elab- skill 或 对话>
next_skill: <建议下一步，可空>
---
```
正文四段：`## 关键判断` / `## 已排除的方向` / `## 待回填假设` / `## 下一步`。

## 三、来源标签系统（强制 · 认知卫生 + 930 护栏）

每条信息标清来自谁、事实还是判断、何时说的。默认 `[本人判断]` 可省。强制标：
- `[AI推测]` / `[AI关键标注]`（带风险/概率） / `[AI元记录]`（AI 反思自己行为）
- `[结果回填 YYYY-MM-DD]` / `[修正 YYYY-MM-DD]` / `[AI暂定模式 YYYY-MM-DD]`

三规则：① AI 标签不能省 ② 确认/反驳 AI 推测用**追加**不覆盖 ③ 事实、当时判断、结果回填分开写，**禁后见之明倒灌**。
> `[AI推测]` 不能当 `[本人判断]` 复述——AI 时代的认知卫生 + 930 边界。

## 四、不可改快照原则

决策/判断快照写完不改；情况变了**新建带日期版本**追加，不回头篡改旧的（防后见之明偏差）。笔误修正在文件末尾追加 `[笔误修正 date: 原→改]`，不重建。

## 五、工具层

所有外部工具/数据源的登记（装/调/输入输出/状态）在 **`elab-research/references/tool-registry.md`**（唯一工具登记源）。新 skill 要用工具，引用那里的条目，别在自己的分册里另起一份平行描述。
