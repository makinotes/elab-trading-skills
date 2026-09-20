# 怎么造一个新 elab- skill

> 给扩展者 / fork 者。这套 skill 的可复制骨架 = 纯路由入口 + 状态三件套 + 来源标签 + 不可改快照 + 工具登记表 + 合规护栏内嵌。照下面做，新 skill 能无缝接进来。

## 1. 命名 + 放哪
- 目录名 = 调用名：`elab-<功能>`（kebab-case，功能性英文）。Claude Code 里就是斜杠命令名，Codex 里是 `$` mention 名，通用 Agent Skills 规范里是 skill name。
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

### 5.1 评测资产分仓
- 公开 `elab-skills` 只放安装和使用所需的 skill、脚本、参考文档、虚构样例，以及不包含评测题/答案的普通确定性单测。
- Goldset、评测题、标准答案、rubric、judge prompt、transcript、评分结果和审计报告只进私有 `edgelab101/elab-skills-internal`，不得提交到公开仓。
- 公开仓的变更说明只描述产品行为和用户可见修复，不公开 case 编号、判分细则或内部验收分数。

## 6. 加一个外部工具 / 数据源
走 `elab-research/references/tool-registry.md` §二：按接口、许可证、任务增益、数据质量、权限与成本逐项评估，再写登记条目。外部研究 Agent 另读 `external-research.md`；只审过文档不算已连接。

研究方法扩展见 `elab-research/references/research-methods.md`：注明适用问题、必需数据、步骤与失效条件，保留作者与来源。品牌露出遵循 `_shared/credit.md`，不将通用或第三方方法重命名为杰尼马原创，不给每个新方法增加顶层 Skill。

## 7. 合规护栏内嵌（投资场景，其他领域换对应合规）
每个 skill 的"风格 & 合规"段写死领域红线。本套 = 930：不给买卖方向、不晒收益、不点"现在买 X"；市场数据只做客观呈现不做方向研判。合规当作 skill 的一等约束，不是事后补。

## 8. 提交前自检
- [ ] `python3 scripts/privacy_gate.py` 通过（只报告文件名，不回显命中的私密内容）
- [ ] frontmatter 8 字段齐（含 requires/outputs）
- [ ] 自包含（或明确声明依赖 `_shared/schema.md` / tool-registry）
- [ ] 路由：在 `elab/SKILL.md` 路由表加一行
- [ ] 脱敏扫描（public repo）：无 IP/token/路径/key/持仓数字
- [ ] 分仓检查：无 Goldset/rubric/judge prompt/transcript/评分或审计资产
- [ ] 合规段在位（无荐股措辞）
- [ ] version + last_updated 填了（按 `CHANGELOG.md` 的 patch/minor/major 约定 bump）
- [ ] **`CHANGELOG.md` 加一条**（PR 必带：改了哪个 skill、新版本、一句话改了啥）

## 9. 版本、评测与发布门禁

- `_shared/SUITE_VERSION` 是整套发行版本；每个 Skill 的 frontmatter `version` 是组件版本。新增跨 Skill 能力时两者都要按 semver-ish 规则更新。
- 所有正式发布使用不可变的 `vX.Y.Z` Git tag。发版记录必须能定位源 commit 和上一已知稳定 tag/commit；不要发布无版本改动。
- 上线前必须完成静态审查、普通确定性测试、隔离行为评测、跨 Skill/问题路由回归，以及 Claude Code、Codex、CodeBuddy、WorkBuddy 的安装与兼容验收。任何 hard gate 失败都先修复，再重跑完整要求集。
- 具体评测题、标准答案、判分细则、transcript、结果和审计证据只保存在私有 `elab-skills-internal`；公共 PR 只写用户可见行为和普通验证，不泄漏评测资产。
- 合并并打 tag 后才算正式上线。需要回退时使用 `bash update.sh --to vX.Y.Z` 安装上一稳定发布，不重写历史 tag。
