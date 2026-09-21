# EdgeLab Skills

> **by 杰尼马（EdgeLab）** · 公众号 杰尼马 · X [@jienima8635](https://x.com/jienima8635)

中文（下方） ｜ [**English**](#english)

[![license](https://img.shields.io/badge/license-CC%20BY--NC%204.0-informational)](LICENSE)

用于**股票与期权研究、交易决策梳理和复盘记录**的 11 个 Agent Skills：研究标的与板块、拆解概念、计算策略风险收益、审阅公开博主证据，并保存、接续和整理你的研究过程。

提供通用 `SKILL.md` 指令与 Claude Code、Codex、CodeBuddy、WorkBuddy 的安装路径。具体可用的数据、工具和执行方式取决于宿主能力、已安装依赖及用户授权；支持安装不等于所有宿主的行为效果相同。

> **内核命题**：AI 时代散户的护城河不是"知道得更多"，是把判断过程摊开——人和 AI 各担其责、每个决策可回溯。看得见的决策，才可能被迭代成 edge。整套 skill 都是这一句的展开（详见 `elab/SKILL.md`）。

> 这些 skill **源码公开、非商业使用免费**。其中 `elab-research` 的「自研数据」模式（雷达 / 恐慌指数）需要 EdgeLab 会员 token 才能读取。没有 token 时可尝试公开数据路径；能否取到数据取决于已安装工具和数据源可用性。

当前版本以 [`_shared/SUITE_VERSION`](_shared/SUITE_VERSION) 为准；每版改了什么见 [CHANGELOG](CHANGELOG.md)，可回退版本见 [Tags](https://github.com/edgelab101/elab-skills/tags)。

**发布状态**：本次更新为预发布。正式版与预发布的区分见 [Releases](https://github.com/edgelab101/elab-skills/releases)；实际宿主行为和可选接口仍需按自身环境确认。

**语言范围**：本页提供中英文介绍；大多数 `SKILL.md` 执行说明和各 Skill 的 README 仍以中文为主。英文提问可以尝试，但英文工作流尚未完成系统行为验收。

## 首次试用（无需会员 token）

按下方[安装说明](#安装)装好后，用 Codex 输入 `$elab-deconstruct`、Claude Code 输入 `/elab-deconstruct`，接着提问：

> Delta 中性是不是等于没有风险？请用虚构例子解释净 Delta、Gamma 和 Vega 的区别，不查询实时行情。

这个例子只需要概念拆解，不需要券商账户或 EdgeLab 会员数据。核对回答是否说明净 Delta 接近零仍有其他风险，并把例子标为虚构。

## 每个 Skill 是做什么的？

点击名称查看用途、输入、产出和使用边界。不确定选哪个时，从 **elab 主入口**开始。

| Skill | 做什么 | 什么时候用 |
|---|---|---|
| [elab](elab/README.md) | 按问题选择对应 Skill，并引导连接或选择券商数据源 | 不知道该用哪个工具，或想指定富途、长桥、IBKR 数据 |
| [elab-research](elab-research/README.md) | 研究股票、ETF、期权或板块，汇集数据、风险与反证 | 想了解标的基本面、期权环境、板块拥挤度或当前行情 |
| [elab-diagnosis](elab-diagnosis/README.md) | 梳理交易决策中的依据、风险、规则与情绪，检查整套打法 | 卡在“该不该买、卖、加仓”，需要把问题想清楚 |
| [elab-trade](elab-trade/README.md) | 记录交易决策，读取持仓与成交，复盘交割单并整理交易规则 | 要立案、更新判断、回填结果，或复盘自己的交易 |
| [elab-model](elab-model/README.md) | 用本地脚本计算期望收益、Kelly 比例和期权结构的风险收益 | 已有胜率、盈亏或合约参数，想把数学关系算清楚 |
| [elab-deconstruct](elab-deconstruct/README.md) | 解释期权与投资概念的定义、操作含义、易混点和失效条件 | 想弄懂 IV、Delta 中性、对冲，或辨别模糊术语 |
| [elab-benchmark](elab-benchmark/README.md) | 检查交易者或策略的证据、方法与可复制条件 | 想判断某套打法值不值得学、哪些部分可以借鉴 |
| [elab-futu-research](elab-futu-research/README.md) | 归档富途或老虎博主公开内容，按时点证据审阅观点与声称的交易 | 要研究博主历史发言、比较多人方法或整理证据 |
| [elab-save](elab-save/README.md) | 把当前研究的判断、假设和下一步保存为本地存档 | 这次聊完，想保留进度供下次接着用 |
| [elab-restore](elab-restore/README.md) | 找回已有存档，呈现之前的判断、待办与未解问题 | 换了会话，需要接着上次研究 |
| [elab-report](elab-report/README.md) | 将多份已有存档按时间与主题合并为投研复盘报告 | 想整理一段时间的研究与决策变化，复核后分享 |

**容易混淆的区别**：研究外部标的用 `research`；梳理眼前决策用 `diagnosis`；记录与复盘自己的交易用 `trade`。`save` 保存一次进度，`restore` 找回进度，`report` 合并多次存档。

券商连接是[共享能力](_shared/broker-connectors.md)，不计入 11 个顶层 Skill。公开市场数据交给 `research`，用户账户与成交数据交给 `trade`；`futu-research` 只研究公开社区内容，**不是富途账户接口**。

研究时可以说“比较这家公司两期财报”“分析产业链瓶颈”“按我提供的方法研究”或“请外部研究 Agent 找反证”。`elab-research` 会按问题选方法并核验证据；外部 Agent 是按需验证的可选执行方式，不代表已安装或已连接。通用方法、用户方法与第三方方法分别保留出处，品牌署名由杰尼马（EdgeLab）统一维护，日常短答保持简洁。

## 安装

### 一键装（推荐）

需要 Git、Bash 和 Python 3.9+（标准库，无需额外安装包）。

```bash
git clone https://github.com/edgelab101/elab-skills.git
cd elab-skills
bash install.sh
```

脚本按本机目录识别安装目标，把 11 个 `elab*` skill 和 `_shared` 装进对应 skills 目录。`elab-futu-research` 已内置，不再需要单独安装另一个仓库。支持以下四种安装路径；这张表说明安装位置，不代表四个宿主均已完成行为实测：

安装和更新用本机 `.elab-install.json` 清单管理套件文件，先检查所有目标再暂存与替换；失败会回滚。复制模式保留未管理文件和第三方扩展，软链模式遇混合目录会停止。`_shared` 必须单独验证归属；源码与替换目标相交时拒绝安装。清单内的本地修改仍会被替换，请先备份。

没有清单的旧安装只自动接管与当前源一致、或匹配本地 `vX.Y.Z` tag 同路径内容的文件。未知的同路径文件会使迁移停止，原目录保持不变；请先备份并处理冲突，不要直接删除共享目录来绕过检查。

| Agent | 个人 skills 目录 |
|---|---|
| Claude Code | `~/.claude/skills/` |
| OpenAI Codex | `~/.codex/skills/` |
| CodeBuddy | `~/.codebuddy/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` |

其他用法：

```bash
bash install.sh --list          # 只看识别到哪些 agent，不动文件
bash install.sh --link          # 软链模式：以后 git pull 就自动更新，不用重装
bash install.sh claude codex    # 只装指定的
```

### 手动装

不想跑脚本，或者用的 agent 不在上面这张表里：确认目标目录没有需要保留的同名文件后，把 `elab*` 和 `_shared` 拷进它的 skills 目录。

```bash
mkdir -p ~/你的agent/skills/
cp -R elab-skills/elab* elab-skills/_shared ~/你的agent/skills/   # _shared 是通用规范，别漏
```

能读文件和运行命令的 Agent 可尝试读取 `elab/SKILL.md`，再按需读取各 `elab-<名>/SKILL.md` 手动执行。数据获取和计算仍需相应的运行环境、工具及权限；没有原生 Skill 机制时，不保证自动发现、路由或完整能力可用。

### 怎么触发

按 runtime 不同：Claude Code 用斜杠命令 `/elab` 或直接说人话；Codex 用 `$elab` mention、`/skills`，或自然语言隐式匹配；CodeBuddy / WorkBuddy 按其调用习惯。skill 内文写的 `/elab-xxx` 泛指「调用对应 skill」。

拿不准用哪个：Codex 输入 `$elab`，Claude Code 输入 `/elab`；主入口会把你路由到对应 skill。

你也可以直接说：“我要用富途数据”“以后默认用长桥”“用 IBKR 查看我的历史成交”。`elab` 会先检查连接并给出当前 runtime 的安装/授权方法；验证通过后，公开市场、资讯和期权数据交给 `elab-research`，账户、持仓、订单与成交交给 `elab-trade`。连接器说明见 [`_shared/broker-connectors.md`](_shared/broker-connectors.md)。

## 更新

skill 会持续迭代。**一键更新（推荐）**——在 elab-skills 目录里跑：

```bash
bash update.sh
bash update.sh --to vX.Y.Z   # 将 vX.Y.Z 换成 Tags 中实际存在的版本；不改变当前 Git 工作树
```

它要求干净的 Git 工作树，先获取上游版本并显示变更，完成预检和暂存后再更新源码与已安装套件。四个 runtime 都会检测，但只更新已有本套件安装的目标；复制和软链模式均按安装清单处理。显式 `--to` 回退会改成固定版本的复制安装。

默认更新会先备份受影响的源码顶层目录（包含其中的 ignored 文件，需要相应磁盘空间）。Git 检出失败时直接恢复原文件与安装，并把失败现场保留在仓库旁的 `.elab-checkout-backup-*` 目录，控制台会给出路径；确认不需要其中的改动后再手动清理。

**自动更新（可选，一次性设置）**——跑一次，之后每天自动跟进最新版：

```bash
bash install-autoupdate.sh        # 默认每天 9:00；bash install-autoupdate.sh 21 改 21:00
```

> 手动等价：`git pull` 后，cp 装的重跑一次 `bash install.sh`，软链装的即自动生效。
> 每次改动都记在 `CHANGELOG.md`（版本 + 一句话），pull 完扫一眼就知道变了什么。
> 正式版本使用 `vX.Y.Z` Git tag；`--to` 只接受已发布 tag，方便错误版本快速回退。
> ⚠️ 自动更新 = 主理人 push 后静默跟进；想先看变更再更就别开，用手动。

> ⚠️ **本地改过 skill 文件的注意**：清单内的套件文件会被新版本替换，先备份；未管理文件在复制模式保留。软链安装的源码有本地改动时，`update.sh` 会停止。想自定义，三选一：
> ① 改进建议**提 PR**（见 `CONTRIBUTING.md`），合并后所有人受益；
> ② **fork / 复制一份出去改**，代价是脱离更新通道，之后自己手动合并上游；
> ③ **个人偏好写进你 agent 的全局配置**（Claude Code 的 `CLAUDE.md` / Codex 的 `AGENTS.md` / CodeBuddy 与 WorkBuddy 的对应全局规则文件）去覆盖行为，不动 skill 文件本身——这样既保留偏好又不挡更新（推荐）。

## 公开博主研究说明

`elab-futu-research` 使用 Python 3.9+ 标准库，无需 API key，不登录账户，也不读取浏览器 Cookie。运行前必须明确选择时间范围；公开接口、限流和平台可见性决定归档边界。虚构样例见 [报告](docs/elab-futu-research/sample-report.md) 与 [概览卡](docs/elab-futu-research/sample-card.png)。

## 券商数据接入（可选）

v0.4.0 支持引导连接富途官方 Agent Skills + OpenD、长桥官方 CLI/MCP、IBKR 官方 MCP。默认只读，可用于资讯、行情、期权、账户、持仓、订单和成交；不会因为一句“我要用某家数据”就自动安装软件、扩大 OAuth 权限或执行交易。

连接偏好只保存 provider 名称到 `~/.elab/broker-connectors.json`，不保存账户、密码、Token 或 App Secret。每次真实取数仍现场验证连接、权限、时间戳和实时/延迟状态。

## EdgeLab 会员数据（可选）

`elab-research` 的自研模式可接入 EdgeLab 雷达 / 恐慌指数数据。接入方式：把会员 token 存到 `~/.elab/token`，并设为仅本人可读写（`chmod 600 ~/.elab/token`）；客户端在进程内读取，勿把 token 发到对话。客户端拒绝重定向，错误只输出状态码和脱敏说明。没有 token 时仍可使用不依赖会员数据的功能。

## 合规

这些 skill 用于**投资者教育与方法论**，不构成投资建议、不荐股、不喊单、不承诺收益。所有决策由使用者自行作出。

本仓库是公开产品仓，只接收安装所需的 skill、脚本、文档、虚构样例与普通单测。个人对话、账户数据、真实持仓、飞书暂存及内部评测资产不得进入本仓库；提交前运行 `python3 scripts/privacy_gate.py`，GitHub CI 也会执行同一检查。

## 作者

**杰尼马**（EdgeLab）。专注美港股与期权研究，持续记录方法、工具与实盘。

- 公众号：**杰尼马**
- X：[@jienima8635](https://x.com/jienima8635)
- GitHub：[edgelab101](https://github.com/edgelab101)

扫码加我，备注 `elab`：

| 微信 | 飞书 |
|:---:|:---:|
| <img src="docs/contact/wechat-qr.jpg" alt="微信二维码" width="200"> | <img src="docs/contact/feishu-qr.png" alt="飞书二维码" width="200"> |

扫不了码（GitHub 图片在部分网络下加载不出来）就用文字：微信号 **flywithmk**，或点[飞书加联系人](https://www.feishu.cn/invitation/page/add_contact/?token=5d4qe0e8-1811-42d5-80e3-89f8bf4017b7&unique_id=2Kjla8sxnu-QcdiaY7tT0g==)。

用得上就点个 star，有问题开 issue。

---

## English

**Release status:** This update is a prerelease. See [Releases](https://github.com/edgelab101/elab-skills/releases) for stable and preview versions; host behavior and optional integrations still need confirmation in your environment.

**EdgeLab Skills** — 11 Agent Skills for equity and options research, trade journaling, and review. They use portable `SKILL.md` instructions that agents can read; available behavior depends on the host and its tools.

> **Core premise**: in the AI era a retail investor's moat is not knowing more — it is making the reasoning visible. Human and AI each own their part, and every decision can be traced back. A decision you can see is a decision you can iterate into an edge.

The source is public and noncommercial use is free. One optional mode in `elab-research` reads EdgeLab's own data (a fear index and crowding radar) and needs a member token. Without a token, public data paths may be available depending on installed tools and source availability.

The current version is in [`_shared/SUITE_VERSION`](_shared/SUITE_VERSION); see [CHANGELOG](CHANGELOG.md) for changes and [Tags](https://github.com/edgelab101/elab-skills/tags) for versions you can roll back to.

**Language status:** This page has an English overview. Most `SKILL.md` instructions and individual skill guides are still written in Chinese. You can try English prompts, but the English workflows have not completed comprehensive behavioral validation.

### The 11 skills

| Skill | What it does |
|---|---|
| [`elab`](elab/README.md) | Entry point — routes your question to the right skill, guides broker connection |
| [`elab-research`](elab-research/README.md) | Research a stock, ETF, option or sector; picks a method per question, ends with forced self-refutation |
| [`elab-diagnosis`](elab-diagnosis/README.md) | Work through a trading decision — rationale, risk, rules, emotion; or audit your whole approach |
| [`elab-trade`](elab-trade/README.md) | Log decisions before entry, update positions, diagnose broker statements, distil a playbook |
| [`elab-model`](elab-model/README.md) | Local scripts for expected value, Kelly fraction and options structure math |
| [`elab-deconstruct`](elab-deconstruct/README.md) | Break options concepts (IV, delta-neutral, hedging) down to operational atoms |
| [`elab-benchmark`](elab-benchmark/README.md) | Check whether a trader's claimed results and method are real and reproducible |
| [`elab-futu-research`](elab-futu-research/README.md) | Archive public Futu/Tiger blogger pages and audit claims against point-in-time prices |
| [`elab-save`](elab-save/README.md) · [`elab-restore`](elab-restore/README.md) · [`elab-report`](elab-report/README.md) | Save research state, resume it in a new session, merge snapshots into a review report |

### Install

Requires Git, Bash and Python 3.9+; no additional Python packages are needed.

```bash
git clone https://github.com/edgelab101/elab-skills.git
cd elab-skills
bash install.sh          # detects your runtime and installs
bash install.sh --list   # show detected runtimes only, change nothing
bash install.sh --link   # symlink mode: `git pull` is all you need to update
```

Installs into `~/.claude/skills/`, `~/.codex/skills/`, `~/.codebuddy/skills/` or `~/.workbuddy/skills/`. Installation uses an ownership manifest, preflights all targets and stages replacements with rollback. Copy mode preserves unmanaged files and third-party extensions; link mode refuses mixed directories. `_shared` must establish its own ownership. Updates require a clean checkout and touch only existing suite installations. Back up edits to managed files first. For any other agent, copy `elab*` and `_shared` into its skills directory — `_shared` is required. Supporting an install path is not a claim that every host behaves identically; available data and tools depend on the host, installed dependencies and your own authorisation.

Legacy files without a manifest must match the current source or a local release tag before adoption; unknown conflicts stop migration without replacing the old installation. Default updates back up affected checkout directories, including ignored files. Failed Git updates restore the old checkout and retain recovery copies beside the repository; the error message gives their location.

Trigger with `/elab` (Claude Code), `$elab` (Codex), or just describe what you need.

For a first try without a broker account or member token, invoke `/elab-deconstruct` in Claude Code or `$elab-deconstruct` in Codex, then ask: “Does delta-neutral mean risk-free? Use a hypothetical example to explain net delta, gamma and vega. Do not look up live market data.” Check that the answer names risks beyond net delta and labels the example as hypothetical.

### Boundaries

These skills are for **investor education and method** — no recommendations, no signals, no stock picks, no promised returns. Every decision is yours. Broker connectors (Futu, Longbridge, IBKR) are read-only and never installed or authorised without your explicit action. `elab-futu-research` works only on public pages: it does not log in, read cookies, or collect private messages.

Licensed **CC BY-NC 4.0** — noncommercial use, sharing and adaptation are permitted with attribution. The restriction covers uses primarily intended for commercial advantage or monetary compensation; it is broader than resale. This project is *source-available*, not OSI-approved open source. See the [license](LICENSE) and [Creative Commons summary](https://creativecommons.org/licenses/by-nc/4.0/).

Questions or corrections: open an issue, or reach me on WeChat **flywithmk** / X [@jienima8635](https://x.com/jienima8635).

## License

**CC BY-NC 4.0**（署名-非商业性使用）——源码公开，允许在遵守署名等许可条件下进行非商业使用、修改和分享。限制包括但不限于转卖或打包进付费产品；具体范围以 [LICENSE](LICENSE) 和 [Creative Commons 许可说明](https://creativecommons.org/licenses/by-nc/4.0/)为准。

> 说明：非商业条款使 CC BY-NC **不属于 OSI 定义的「开源许可证」**。对外请称这套 skill「源码公开、非商业使用免费」，不要把限制简化为「仅禁止商业转售」。
