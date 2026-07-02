# EdgeLab Skills

一套用于 **AI × 美股期权投研** 的 Claude Code skills。把投研决策、对标、概念拆解、复盘的方法论沉淀成可复用的工作流。

> **内核命题**：AI 时代散户的护城河不是"知道得更多"，是把判断过程摊开——人和 AI 各担其责、每个决策可回溯。看得见的决策，才可能被迭代成 edge。整套 skill 都是这一句的展开（详见 `elab/SKILL.md`）。

> 这些 skill **公开免费**，谁都能装。其中 `elab-research` 的「自研数据」模式（雷达 / 恐慌指数）需要 EdgeLab 会员 token 才能读取——没有 token 会**优雅降级**到公开工具（OpenBB 等），其余功能照常用。

## 安装

把 skill 目录放进 Claude Code 的 skills 目录即可：

```bash
git clone https://github.com/edgelab101/elab-skills.git
mkdir -p ~/.claude/skills/
cp -R elab-skills/elab* ~/.claude/skills/
```

> 想免每次 cp，可改用软链（这样 `git pull` 后自动生效，不用再 cp）：
> ```bash
> for d in elab-skills/elab*; do ln -sfn "$(pwd)/$d" ~/.claude/skills/$(basename "$d"); done
> ```

## 更新

skill 会持续迭代。更新分两步：

```bash
cd elab-skills
git pull                       # 拉最新
cat CHANGELOG.md | head -30    # 看这次改了啥（版本 + 变更）
```

- **用 `cp -R` 装的**：`git pull` 后再重跑一次 `cp -R elab-skills/elab* ~/.claude/skills/` 覆盖旧版
- **用软链装的**：`git pull` 即自动生效，无需再 cp

> 每次改动都记在 `CHANGELOG.md`（版本号 + 一句话），pull 完扫一眼就知道变了什么、要不要重看某个 skill。

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
