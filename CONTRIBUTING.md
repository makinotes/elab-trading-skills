# 怎么造一个新 elab- skill

> 给扩展者 / fork 者。这套 skill 的可复制骨架 = 纯路由入口 + 状态三件套 + 来源标签 + 不可改快照 + 工具登记表 + 合规护栏内嵌。照下面做，新 skill 能无缝接进来。

## 1. 命名 + 放哪
- 目录名 = 斜杠命令名：`elab-<功能>`（kebab-case，功能性英文）。
- 放 repo 根：`elab-<功能>/SKILL.md`。多文件用 `elab-<功能>/references/*.md`。
- fork 到别的领域：把前缀 `elab-` 换成你的品牌前缀，`~/.elab/` 换成 `~/.<brand>/`，其余骨架不动。

## 2. frontmatter（必填，照抄字段）
```yaml
---
name: elab-<功能>
description: |
  <一句中文功能描述>。触发：/elab-<功能>、<中文触发词>
  <one-line English>. Trigger: /elab-<功能>
invocation: user
version: 0.1.0
last_updated: YYYY-MM-DD
visibility: public | private   # 见 §5
requires: []                   # 前置 skill / 输入格式，见 §4
outputs: []                    # 产出路径/格式，见 §4
---
```
- 双语 description（跨语言传播）。`version` + `last_updated` 改动必更。

## 3. 正文骨架（自包含）
- 第一行原则：`> 自包含：拿到这一个 SKILL.md 即可执行`。开源 skill 不依赖服务器/其他文件。
- 结构：核心定位（1-2 句）→ 流程/动作 → worked example → 风格 & 合规段。
- **接状态系统 / 用来源标签的，引用 `_shared/schema.md`，不自己复述路径和标签定义。**
- **用外部工具的，引用 `elab-research/references/tool-registry.md` 的条目，不另起平行描述。**

## 4. skill 间依赖（frontmatter 声明，可读可组合）
- `requires:` = 这个 skill 依赖的前置（如 `["elab-save 的存档"]`）或输入格式；无则 `[]`。
- `outputs:` = 产出到哪（如 `["~/.elab/sessions/"]`）或产出格式；让下游 skill 知道从哪接。
- 这俩是**声明性文档**（不运行时解析），但有了它一眼能画出 skill 依赖图，是"可组合"的前提。

## 5. visibility 分级
- `public`：通用方法/工具，已脱敏（无持仓/真实成交/账户线索/私有信源/API key），无荐股措辞 → 进公开 repo。
- `private`：含真实持仓/账户/私有管道 → 只进私有 repo。
- 判定：把这 skill 原样给陌生人看，会不会泄露账户/持仓/私有系统？会 → private。

## 6. 加一个外部工具 / 数据源
走 `elab-research/references/tool-registry.md` §二：**玩具筛 5 关**（能本地跑/维护活跃/license 可商用/实盘机构真在用/数据质量满足场景）→ 过筛写登记条目 → 标接口衔接 + 合规。

## 7. 合规护栏内嵌（投资场景，其他领域换对应合规）
每个 skill 的"风格 & 合规"段写死领域红线。本套 = 930：不给买卖方向、不晒收益、不点"现在买 X"；市场数据只做客观呈现不做方向研判。合规当作 skill 的一等约束，不是事后补。

## 8. 提交前自检
- [ ] frontmatter 8 字段齐（含 requires/outputs）
- [ ] 自包含（或明确声明依赖 `_shared/schema.md` / tool-registry）
- [ ] 路由：在 `elab/SKILL.md` 路由表加一行
- [ ] 脱敏扫描（public repo）：无 IP/token/路径/key/持仓数字
- [ ] 合规段在位（无荐股措辞）
- [ ] version + last_updated 填了
