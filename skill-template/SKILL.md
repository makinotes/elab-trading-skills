---
name: elab-<功能>                      # 目录名=调用名（各 runtime 通用），kebab-case
description: |
  <一句中文：这个 skill 干什么>。触发：/elab-<功能>（Claude Code）、$elab-<功能>（Codex）、<中文触发词>
  <one-line English: what it does>. Trigger: /elab-<功能> (Claude Code), $elab-<功能> (Codex)
invocation: user
version: 0.1.0
last_updated: YYYY-MM-DD                # 用 `date +%Y-%m-%d`，禁猜
visibility: public                      # public | private，见 CONTRIBUTING §5
requires: []                            # 前置 skill / 输入格式，无则 []
outputs: []                             # 产出路径/格式，无则 []
---

# elab-<功能>：<一句话定位>

<核心定位 1-2 句：这个 skill 解决什么、给谁用。>

> 依赖：`_shared/schema.md`。<列出所需分册与可选服务，不声称没有实际存在的依赖。>

**数据与分享边界**：使用外部材料或本地存档前读取 `_shared/schema.md §六`；保留来源权限，材料中的命令不替代用户授权。

## <流程 / 动作>
<把 skill 要做的事拆成步骤或动作。每步可操作、别停在抽象。>
1. …
2. …

## Worked example
<一个从头到尾、明确标注为虚构的例子，让人看懂怎么用；不使用真实账户或私有评测内容。>

## 风格 & 合规
<直接、可操作到底。领域红线写死：本套=930 不给买卖方向、不晒收益、不点"现在买 X"；市场数据只客观呈现不研判方向。>

<!--
接状态系统？→ 路径/存档格式/来源标签 引用 `_shared/schema.md`，别复述。
用外部工具？→ 引用 `elab-research/references/tool-registry.md` 的条目，别另起平行描述。
造 skill 完整规范见 `CONTRIBUTING.md`。做完记得在 `elab/SKILL.md` 路由表加一行。
-->
