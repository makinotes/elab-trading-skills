# 工具登记表（elab-research 可扩展的核心）

> 编排时从这挑工具。**表是活的**——网上出新工具，按"怎么加"评估后加进来即可被编排。
> ⚠️ 包名/接口名会变，以官方文档为准；具体函数签名不确定就标 [需核对]，别编。

## 〇、默认取数栈（开箱即用 · 研究一个标的默认从这几个拿）

仅在本次方法确需取数时选用下表；给定材料或本地计算可跳过。公开栈是候选组合，不代表每次全调或覆盖率承诺：

| 需求 | 默认用 | 补充 |
|---|---|---|
| 行情/历史/期权链 | 先按共享契约选择已验证的 provider；任务允许公开源时可用 **yfinance** | OpenBB（一站式）/ stooq（日级兜底）|
| 实时报价/财报日历 | **finnhub**（免费 tier，有 key） | yfinance 兜底 |
| EOD 历史/指数 | **stooq**（免费无 key，稳） | yfinance |
| 财报原文 10-K/Q | **edgartools** | — |
| 期权 IV/希腊字母 | **py_vollib** | py_vollib_vectorized（批量）|
| EdgeLab 雷达/恐慌 | 自研 API（会员 token，见"自研"节） | — |

> provider 选择算法只维护在 `_shared/broker-connectors.md §二`，包括已保存默认和唯一可用连接。无可用连接时，任务允许才用公开源并披露；“只用某家”失败不得切源。财报原文等补充证据也需符合用户的数据范围限制。

> **🔑 凭据纪律（硬规则）**：优先使用官方 OAuth、OpenD 或 CLI 原生凭据存储。确实使用 API key/App Secret/Access Token 的工具只能从环境变量或专用本地凭据存储读取，**禁硬编码进 skill/脚本，禁写入 `~/.elab/`、研报、存档、日志或任何输出**。

## 一、登记表（每个工具：装/调 + 输入输出 + 状态）

### 数据聚合
- **OpenBB**（`pip install openbb`）🟢 —— `from openbb import obb`，取行情/财报/新闻/**期权链**。输入 ticker，输出结构化数据。一站式
- **yfinance**（`pip install yfinance`）🟢 —— **默认行情源**，轻量取行情/历史/期权链；免费无 key，偶尔不稳做兜底
- **finnhub**（`pip install finnhub-python`，免费 tier 需 key）🟢 —— 实时报价 / 财报日历 / 基本面；免费额度够个人研究
- **stooq**（`pandas-datareader` 或直接 CSV URL，无 key）🟢 —— 免费 EOD 历史 + 指数，稳，yfinance 抽风时兜底

### 券商 / 自己数据（需自己账户凭据）
- **富途官方 Futu Agent Skills + OpenD** 🟢 —— 资讯/公告/研报、行情/K 线、期权链/Greeks、账户/持仓/订单/成交；需 OpenD、SDK 和账户权限。EdgeLab v0.4.0 只调用读取能力，不调用官方 Skill 中的交易脚本。安装与验收见 `_shared/broker-connectors.md`。
- **长桥官方 `longbridge` CLI / hosted MCP** 🟢 —— 资讯、行情、基本面、期权、账户、持仓、订单、成交；CLI 是独立的 `longbridge-terminal`，不是 `pip install longbridge` SDK。机器读取加 `--format json`；只读 OAuth 权限与安装见 `_shared/broker-connectors.md`。
- **IBKR 官方 MCP** 🟢 —— 账户、现金、保证金、持仓、盈亏、历史交易、期权链与风险暴露。公开连接器生成的交易 Instructions 仍需在 IBKR 平台确认，但 EdgeLab v0.4.0 不生成 Instructions，只读取；批量历史可用 Flex Query 文件。见 `_shared/broker-connectors.md`。

### 财报 / SEC
- **edgartools**（`pip install edgartools`）🟢 —— 拉解析 10-K/10-Q/8-K。输入 ticker，输出财报文本/财务数据 → 喂你自己的财报分析 prompt

### 期权计算
- **py_vollib**（`pip install py_vollib`）🟢 —— 逐条算 IV、希腊字母、BS 定价。输入期权参数（标的价/行权/到期/无风险利率/期权价），输出 IV/Delta/Gamma/theta/Vega
- **py_vollib_vectorized**（`pip install py_vollib_vectorized`，**独立包，接口不同**）🟢 —— 批量/向量化算 IV 希腊字母，整列数据时用。`pip install py_vollib` 不会带它
- **QuantLib-Python**（`pip install QuantLib`）🟡 —— 工业级衍生品定价，重、API 陡，复杂结构才用

### 回测
- **vectorbt**（`pip install vectorbt`）🟡 —— 向量化回测验想法；学习曲线陡，验策略假设时用

### 自研（EdgeLab 权益内 · 会员 token gated）
- **EdgeLab 市场数据 API** 🔵 —— 取恐慌指数 / 期权 / 美港股 / 13F / 拥挤度等**市场数据与指标**（客观数字，无买卖指令、无方向建议）。**唯一数据源 + 唯一对外 API，直接调，不是 MCP**：
  1. 读 token：`cat ~/.elab/token`（`mk_live_…` key；如何获取见 EdgeLab 会员说明，不在本技术文档描述）
  2. 发现可用数据集：`curl -H "Authorization: Bearer $(cat ~/.elab/token)" https://invest.makinote.cn/api/v1/radars` → 返回数据集类型 + 各自最新日期
  3. 取数据：`curl -H "Authorization: Bearer $(cat ~/.elab/token)" "https://invest.makinote.cn/api/v1/signals?type=<数据集id>&limit=10"`（端点路径 `signals` 是历史命名，返回的是市场数据/指标）
     - 参数：`type`（数据集 id）、`date`/`since`/`until`（YYYY-MM-DD）、`limit`（1..100，默认 30）。**先调 `/radars` 拿到当前可用 type 列表再查**（别写死）
     - 12 个对外数据集 type：`fear_card`(恐慌指数) / `options_radar`(期权数据) / `trading_premarket`·`trading_midday`·`trading_close`(美股盘前/午间/收盘数据) / `hk_close`(港股收盘) / `hk_ipo`(港股打新) / `whale`(机构持仓) / `x_radar`(X 资讯) / `briefing_relay`(投资简报) / `thirteenf`(13F 异动) / `crowding`(拥挤度)
     - 返回已**合规投影**（荐股类字段已剥、方向/点评已脱敏）的中性市场数据；**模型拿到只做数据呈现和方法层分析，不转成"该买/卖/看这个"的方向建议**（930）
  4. **优雅降级（按状态码）**：
     - 401（无 token/无效/过期）→ 说明本次实际需要但缺失的数据项及影响。任务允许公开替代源时披露来源后继续；只用自研时不切源。无关问题不调用该 API，也不因缺会员 key 自动降低质量或插入促销文案。
     - 429（限速，120 req/min/同出口 IP，多会员共享）→ 退避重试；多数 agent runtime 不会自动重试，提示用户稍后重跑
     - 503（`not_ready`，该日期数据仍在合规处理）→ 报告该日期缺失；任务允许替代时点才查询其它日期，披露实际时间且不得超过研究截止时间，不能冒充原日期数据。
     - 500（服务故障）→ 报告失败和缺口；仅在任务允许替代源时披露后切换，遵守与 401 相同的范围限制。
  - 注：token 只在 skill 调 API 时用；和网站登录解耦（网站不经过这个 API）

### 可选研究 Agent（逐项验证）
- 能力发现、权限、证据核验与候选官方链接统一见 `external-research.md`。未安装/未实测的项目不标成已支持。
- FinGPT、FinRobot、TradingAgents等不能凭名称统一判无效，也不能凭回测宣传判有效；分别评估研究流程价值、数据可靠性、成本和收益证据。研究引擎输出与原始行情/财报数据区分。

## 二、怎么加一个工具 / action（扩展机制）

**Step 1 按用途评估**：
- □ 当前接口可调用且维护状态可查？ □ 许可证允许预期集成与分发方式？ □ 对当前任务有可验证增益（证据/计算/反证）？ □ 数据质量、延迟、覆盖率满足场景？ □ 权限、依赖、成本与故障边界可控？
- 区分文档审查、确定性测试、隔离行为验证与真实连接验证。机构采用不是通用研究工具的必需条件，收益曲线也不是研究可靠性的证明。

**Step 2 写登记条目**（按类别加到 §一）：
```
- **<名字>**（`pip install <pkg>`）🟢/🟡 —— <一句话：怎么调、吃什么输入、吐什么输出、衔接谁>
```

**Step 3 标接口衔接**：吃什么输入、吐什么输出、和现有工具怎么接（如"edgartools 出财报文本 → 财报分析 prompt"）。

**Step 4 标合规**：输出是纯数据/指标（OK）还是带方向建议（要剥掉方向再用）。

## 三、怎么保持更新（诚实版：结构化流程，非魔法自动）

skill 是静态指令，"更新"靠流程：
- **触发**：① 遇到新工具即时评估 ② 定期（如每季）派一个调研 agent 扫"近期靠谱的开源投研/期权工具"
- **评估**：按 §二 的用途与证据逐项检查；旧结论注明版本和时间，不永久拒绝某类项目。
- **落地**：过筛的按 §二 Step 2-4 加进表；券商类同时更新 `_shared/broker-connectors.md`，并改相关主 Skill 的 `version` + `last_updated`
- 调研 agent prompt 可复用"查开源 trade/投研工具 + 真能用 vs 玩具分级"那套
