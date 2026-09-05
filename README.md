# EdgeLab Skills

> **by 杰尼马（EdgeLab）** · 公众号 杰尼马 · X [@jienima8635](https://x.com/jienima8635)

用于**股票与期权研究、交易决策梳理和复盘记录**的 11 个 Agent Skills：研究标的与板块、拆解概念、计算策略风险收益、审阅公开博主证据，并保存、接续和整理你的研究过程。

提供通用 `SKILL.md` 指令与 Claude Code、Codex、CodeBuddy、WorkBuddy 的安装路径。具体可用的数据、工具和执行方式取决于宿主能力、已安装依赖及用户授权；支持安装不等于所有宿主的行为效果相同。

> **内核命题**：AI 时代散户的护城河不是"知道得更多"，是把判断过程摊开——人和 AI 各担其责、每个决策可回溯。看得见的决策，才可能被迭代成 edge。整套 skill 都是这一句的展开（详见 `elab/SKILL.md`）。

> 这些 skill **公开免费**，谁都能装。其中 `elab-research` 的「自研数据」模式（雷达 / 恐慌指数）需要 EdgeLab 会员 token 才能读取——没有 token 会**优雅降级**到公开工具（OpenBB 等），其余功能照常用。

当前套件版本：**0.4.3**（安装后也可查看 `_shared/SUITE_VERSION`）。本版更新功能导航与使用说明，执行规则不变；上一稳定版本为 **0.4.2**。

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

## 安装

### 一键装（推荐）

```bash
git clone https://github.com/edgelab101/elab-skills.git
cd elab-skills
bash install.sh
```

脚本按本机目录识别安装目标，把 11 个 `elab*` skill 和 `_shared` 装进对应 skills 目录。`elab-futu-research` 已内置，不再需要单独安装另一个仓库。支持以下四种安装路径；这张表说明安装位置，不代表四个宿主均已完成行为实测：

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

不想跑脚本，或者用的 agent 不在上面这张表里：把 `elab*` 和 `_shared` 拷进它的 skills 目录就行。

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
bash update.sh --to v0.4.2   # 安装/回退到已发布版本；不改变当前 Git 工作树
```

它自动：`git pull` → 显示 CHANGELOG 本次变更 → 同步到已安装的 skills 目录（Claude Code / Codex / CodeBuddy / WorkBuddy 四个都检测；cp 或软链装法都自动处理，含 `_shared`）。

**自动更新（可选，一次性设置）**——跑一次，之后每天自动跟进最新版：

```bash
bash install-autoupdate.sh        # 默认每天 9:00；bash install-autoupdate.sh 21 改 21:00
```

> 手动等价：`git pull` 后，cp 装的重跑一次 `bash install.sh`，软链装的即自动生效。
> 每次改动都记在 `CHANGELOG.md`（版本 + 一句话），pull 完扫一眼就知道变了什么。
> 正式版本使用 `vX.Y.Z` Git tag；`--to` 只接受已发布 tag，方便错误版本快速回退。
> ⚠️ 自动更新 = 主理人 push 后静默跟进；想先看变更再更就别开，用手动。

> ⚠️ **本地改过 skill 文件的注意**：更新会覆盖你的改动——`update.sh`（cp 装法）同步时整目录覆盖，开了自动更新更是每天静默覆盖；软链装法 `git pull` 时直接冲突。想自定义，三选一：
> ① 改进建议**提 PR**（见 `CONTRIBUTING.md`），合并后所有人受益；
> ② **fork / 复制一份出去改**，代价是脱离更新通道，之后自己手动合并上游；
> ③ **个人偏好写进你 agent 的全局配置**（Claude Code 的 `CLAUDE.md` / Codex 的 `AGENTS.md` / CodeBuddy 与 WorkBuddy 的对应全局规则文件）去覆盖行为，不动 skill 文件本身——这样既保留偏好又不挡更新（推荐）。

## 公开博主研究说明

`elab-futu-research` 使用 Python 3.9+ 标准库，无需 API key，不登录账户，也不读取浏览器 Cookie。运行前必须明确选择时间范围；公开接口、限流和平台可见性决定归档边界。虚构样例见 [报告](docs/elab-futu-research/sample-report.md) 与 [概览卡](docs/elab-futu-research/sample-card.png)。

## 券商数据接入（可选）

v0.4.0 支持引导连接富途官方 Agent Skills + OpenD、长桥官方 CLI/MCP、IBKR 官方 MCP。默认只读，可用于资讯、行情、期权、账户、持仓、订单和成交；不会因为一句“我要用某家数据”就自动安装软件、扩大 OAuth 权限或执行交易。

连接偏好只保存 provider 名称到 `~/.elab/broker-connectors.json`，不保存账户、密码、Token 或 App Secret。每次真实取数仍现场验证连接、权限、时间戳和实时/延迟状态。

## EdgeLab 会员数据（可选）

`elab-research` 的自研模式可接入 EdgeLab 雷达 / 恐慌指数数据。接入方式：把会员 token 存到 `~/.elab/token`，skill 会自动带上。没有 token 时不影响其他功能。

## 合规

这些 skill 用于**投资者教育与方法论**，不构成投资建议、不荐股、不喊单、不承诺收益。所有决策由使用者自行作出。

本仓库是公开产品仓，只接收安装所需的 skill、脚本、文档、虚构样例与普通单测。个人对话、账户数据、真实持仓、飞书暂存及内部评测资产不得进入本仓库；提交前运行 `python3 scripts/privacy_gate.py`，GitHub CI 也会执行同一检查。

## 作者

**杰尼马**（EdgeLab）。专注美港股与期权研究，持续记录方法、工具与实盘。

- 公众号：**杰尼马**
- X：[@jienima8635](https://x.com/jienima8635)
- GitHub：[edgelab101](https://github.com/edgelab101)

用得上就点个 star，有问题开 issue。

## License

**CC BY-NC 4.0**（署名-非商业性使用）——可自由使用、修改、分享，但**禁止商业用途**（不得转卖、打包进付费产品/课程/服务）。详见 [LICENSE](LICENSE)。
