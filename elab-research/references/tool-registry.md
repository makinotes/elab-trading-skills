# 工具登记表（elab-research 可扩展的核心）

> 编排时从这挑工具。**表是活的**——网上出新工具，按"怎么加"评估后加进来即可被编排。
> ⚠️ 包名/接口名会变，以官方文档为准；具体函数签名不确定就标 [需核对]，别编。

## 一、登记表（每个工具：装/调 + 输入输出 + 状态）

### 数据聚合
- **OpenBB**（`pip install openbb`）🟢 —— `from openbb import obb`，取行情/财报/新闻/**期权链**。输入 ticker，输出结构化数据。一站式，优先用
- **yfinance**（`pip install yfinance`）🟢 —— 轻量取行情/历史/期权链；免费但偶尔不稳，做兜底

### 券商 / 自己数据
- **futu-api**（富途，需 FutuOpenD 常驻）🟢 —— 接富途行情/会员自己持仓
- **longbridge**（长桥，需 API 凭据）🟢 —— 接长桥行情/持仓。⚠️ 官方已把包从 `longport` 重命名为 `longbridge`（`longport` 已废弃），`pip install longbridge`，import 走 `from longbridge.openapi import ...`

### 财报 / SEC
- **edgartools**（`pip install edgartools`）🟢 —— 拉解析 10-K/10-Q/8-K。输入 ticker，输出财报文本/财务数据 → 喂你自己的财报分析 prompt

### 期权计算
- **py_vollib**（`pip install py_vollib`）🟢 —— 逐条算 IV、希腊字母、BS 定价。输入期权参数（标的价/行权/到期/无风险利率/期权价），输出 IV/Delta/Gamma/theta/Vega
- **py_vollib_vectorized**（`pip install py_vollib_vectorized`，**独立包，接口不同**）🟢 —— 批量/向量化算 IV 希腊字母，整列数据时用。`pip install py_vollib` 不会带它
- **QuantLib-Python**（`pip install QuantLib`）🟡 —— 工业级衍生品定价，重、API 陡，复杂结构才用

### 回测
- **vectorbt**（`pip install vectorbt`）🟡 —— 向量化回测验想法；学习曲线陡，验策略假设时用

### 自研（EdgeLab 权益内 · 会员 token gated）
- **EdgeLab 雷达数据 API** 🔵 —— 取恐慌指数 / 期权 / 美港股 / 13F / 拥挤度等雷达信号。**唯一数据源 + 唯一对外 API，直接调，不是 MCP**：
  1. 读会员 token：`cat ~/.elab/token`（你的 `mk_live_…` key，进星球后主理人发你）
  2. 发现可用雷达：`curl -H "Authorization: Bearer $(cat ~/.elab/token)" https://invest.makinote.cn/api/v1/radars` → 返回雷达类型 + 各自最新日期
  3. 取信号：`curl -H "Authorization: Bearer $(cat ~/.elab/token)" "https://invest.makinote.cn/api/v1/signals?type=<雷达id>&limit=10"`
     - 参数：`type`（雷达 id）、`date`/`since`/`until`（YYYY-MM-DD）、`limit`（1..100，默认 30）。**先调 `/radars` 拿到当前可用 type 列表再查**（别写死）
     - 12 个对外雷达 type：`fear_card`(恐慌) / `options_radar`(期权) / `trading_premarket`·`trading_midday`·`trading_close`(美股盘前/午间/收盘) / `hk_close`(港股收盘) / `hk_ipo`(港股打新) / `whale`(机构持仓) / `x_radar`(X 资讯) / `briefing_relay`(投资简报) / `thirteenf`(13F 异动) / `crowding`(拥挤度)
     - 返回已**合规投影**（荐股类字段已剥、点评已脱敏）的安全数据
  4. **优雅降级（按状态码）**：
     - 401（无 token/非会员/退费/过期）→ 不崩，提示"雷达数据要会员 key（进星球向主理人要 key 存到 `~/.elab/token`）"，回落公开工具（OpenBB 等）继续跑
     - 429（限速，120 req/min/同出口 IP，多会员共享）→ 退避重试；Claude Code 无自动重试，提示用户稍后重跑
     - 503（`not_ready`，该日期数据仍在合规处理）→ 去掉 `date` 参数查最近 N 条，或换日期
     - 500（服务故障，多为限流后端抖动）→ 同 401 处理，回落公开工具，别卡死
  - 注：token 只在 skill 调 API 时用；和网站登录解耦（网站不经过这个 API）

### ❌ 别接（玩具行，警示）
- **FinGPT / FinRobot / TradingAgents 等 LLM trade agent** 🔴 —— demo/回测过拟合，实盘没用、整合不值。这正是"复合开源 trade agent"最该避的坑

## 二、怎么加一个工具 / action（扩展机制）

**Step 1 过玩具筛**（4 关，不过进 🔴 警示行）：
- □ 能本地跑/接 Python？ □ 维护活跃（近半年有更新）？ □ license 可商用集成？ □ 实盘/机构真在用 vs 只是回测曲线好看？

**Step 2 写登记条目**（按类别加到 §一）：
```
- **<名字>**（`pip install <pkg>`）🟢/🟡 —— <一句话：怎么调、吃什么输入、吐什么输出、衔接谁>
```

**Step 3 标接口衔接**：吃什么输入、吐什么输出、和现有工具怎么接（如"edgartools 出财报文本 → 财报分析 prompt"）。

**Step 4 标合规**：输出是纯数据/指标（OK）还是带方向建议（要剥掉方向再用）。

## 三、怎么保持更新（诚实版：结构化流程，非魔法自动）

skill 是静态指令，"更新"靠流程：
- **触发**：① 遇到新工具即时评估 ② 定期（如每季）派一个调研 agent 扫"近期靠谱的开源投研/期权工具"
- **评估**：用 §二 Step 1 四关筛（上次调研已把 LLM trade agent 全筛进 🔴）
- **落地**：过筛的按 §二 Step 2-4 加进表，改主 SKILL 的 `version` + `last_updated`
- 调研 agent prompt 可复用"查开源 trade/投研工具 + 真能用 vs 玩具分级"那套
