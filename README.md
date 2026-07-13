# EdgeLab Skills

一套用于 **AI × 美股期权投研** 的 agent skills。把投研决策、对标、概念拆解、复盘的方法论沉淀成可复用的工作流。**不绑定特定 AI 产品**：Claude Code、OpenAI Codex，以及任何按 [Agent Skills 规范](https://developers.openai.com/codex/skills)（`SKILL.md` + YAML frontmatter）加载 skill 的第三方 agent（如 workbuddy 等）都能装能用——整套 skill 只依赖"能读文件 + 能跑 shell"。

> **内核命题**：AI 时代散户的护城河不是"知道得更多"，是把判断过程摊开——人和 AI 各担其责、每个决策可回溯。看得见的决策，才可能被迭代成 edge。整套 skill 都是这一句的展开（详见 `elab/SKILL.md`）。

> 这些 skill **公开免费**，谁都能装。其中 `elab-research` 的「自研数据」模式（雷达 / 恐慌指数）需要 EdgeLab 会员 token 才能读取——没有 token 会**优雅降级**到公开工具（OpenBB 等），其余功能照常用。

## 安装

把 skill 目录放进你所用 agent 的 skills 目录即可。先 clone：

```bash
git clone https://github.com/edgelab101/elab-skills.git
```

**Claude Code**（个人 skills 目录 `~/.claude/skills/`）：

```bash
mkdir -p ~/.claude/skills/
cp -R elab-skills/elab* elab-skills/_shared ~/.claude/skills/   # _shared 是通用规范，别漏
```

**OpenAI Codex**（个人 `~/.codex/skills/`，项目级用 `.codex/skills/`）：

```bash
mkdir -p ~/.codex/skills/
cp -R elab-skills/elab* elab-skills/_shared ~/.codex/skills/
```

**其他第三方 agent**（workbuddy 等，凡支持 Agent Skills 规范 / `SKILL.md` 目录式加载的）：把 `elab*` + `_shared` 拷进它的 skills 目录，或直接把本 repo 目录指给它。**连 skill 机制都没有的 agent 也能用**：让它读 `elab/SKILL.md` 当入口路由、按需读各 `elab-<名>/SKILL.md` 照着执行即可。

> 想免每次 cp，可改用软链（`git pull` 后自动生效），以 Claude Code 为例：
> ```bash
> cd elab-skills
> for d in elab elab-* _shared; do ln -sfn "$(pwd)/$d" ~/.claude/skills/$d; done
> ```

**触发方式按 runtime 不同**：Claude Code 用斜杠命令（`/elab`）或自然语言；Codex 用 `$` mention（`$elab`）、`/skills` 或自然语言隐式匹配；其他 agent 按其调用习惯。skill 内文说的 `/elab-xxx` 泛指"调用对应 skill"。

## 更新

skill 会持续迭代。**一键更新（推荐）**——在 elab-skills 目录里跑：

```bash
bash update.sh
```

它自动：`git pull` → 显示 CHANGELOG 本次变更 → 同步到已安装的 skills 目录（`~/.claude/skills/` 和 `~/.codex/skills/` 都检测；cp 或软链装法都自动处理，含 `_shared`）。

**自动更新（可选，一次性设置）**——跑一次，之后每天自动跟进最新版：

```bash
bash install-autoupdate.sh        # 默认每天 9:00；bash install-autoupdate.sh 21 改 21:00
```

> 手动等价：`git pull` 后，cp 装的重跑上面的 `cp -R` 行，软链装的即自动生效。
> 每次改动都记在 `CHANGELOG.md`（版本 + 一句话），pull 完扫一眼就知道变了什么。
> ⚠️ 自动更新 = 主理人 push 后静默跟进；想先看变更再更就别开，用手动。

> ⚠️ **本地改过 skill 文件的注意**：更新会覆盖你的改动——`update.sh`（cp 装法）同步时整目录覆盖，开了自动更新更是每天静默覆盖；软链装法 `git pull` 时直接冲突。想自定义，三选一：
> ① 改进建议**提 PR**（见 `CONTRIBUTING.md`），合并后所有人受益；
> ② **fork / 复制一份出去改**，代价是脱离更新通道，之后自己手动合并上游；
> ③ **个人偏好写进你 agent 的全局配置**（Claude Code 的 `CLAUDE.md` / Codex 的 `AGENTS.md`）去覆盖行为，不动 skill 文件本身——这样既保留偏好又不挡更新（推荐）。

## Skill 清单

**🔧 基础设施**
- `elab` — 主入口路由，按意图分发到下面的 skill
- `elab-save` / `elab-restore` / `elab-report` — 投研状态三件套：存档 / 接续 / 合并成复盘报告

**📊 投研 / 决策**
- `elab-diagnosis` — 投资决策消解：「该不该 X」先判断问题成不成立，把决策权还给你
- `elab-benchmark` — 五重过滤对标：谁真赚到、我能不能复制，识破晒单造假
- `elab-deconstruct` — 期权概念拆解：IV / Delta 中性 / 对冲… 拆到可操作
- `elab-trade` — 期权 / 股票决策日志：四层结构 + 来源标签 + 不可改快照
- `elab-research` — 投研编排器：多模式调度数据 / 工具（含会员自研数据模式）

## 数据接入（可选 · 会员）

`elab-research` 的自研模式可接入 EdgeLab 雷达 / 恐慌指数数据。接入方式：把会员 token 存到 `~/.elab/token`，skill 会自动带上。没有 token 时不影响其他功能。

## 合规

这些 skill 用于**投资者教育与方法论**，不构成投资建议、不荐股、不喊单、不承诺收益。所有决策由使用者自行作出。

## License

**CC BY-NC 4.0**（署名-非商业性使用）——可自由使用、修改、分享，但**禁止商业用途**（不得转卖、打包进付费产品/课程/服务）。详见 [LICENSE](LICENSE)。
