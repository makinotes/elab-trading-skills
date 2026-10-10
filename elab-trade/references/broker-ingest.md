# 券商数据接入参考（富途 / 长桥 / IBKR）

> `elab-trade` Mode B 的离线文件导入与批量历史回退分册。先确认用户用哪家券商，再翻到对应小节。富途/长桥/IBKR 的实时只读连接、安装、provider 选择和安全边界统一见 `_shared/broker-connectors.md`；不要在这里维护第二套连接说明。
> ⚠️ 接口名、菜单路径、字段名会随券商版本变——本册标的是"方法和该找什么"，具体名称**以券商当前界面/官方文档为准**，对不上让用户截图导出列名给你，现场映射。

---

## 通用：本 skill 最终要的标准 schema

不管哪家，归一成这张表（每行一笔**成交 fill**，不是订单 order）：

`provider | account_alias | fill_id | order_id | trade_date | symbol | underlying | side(BUY/SELL/SELL_SHORT/BUY_TO_CLOSE) | open_close | qty | price | fee | currency | [expiry | strike | cp | multiplier]`

期权：`qty`=张数（1 张=100 股），多 `expiry/strike/cp`。

**导入前必清洗（高频坑）**：① 一笔大单拆成多行成交（同时间同价/同 order_id）——按 order_id 合并或保留明细但标记，否则 FIFO 把一笔当多笔 ② 手续费/佣金可能单独成行——并进对应成交的 `fee` ③ 重复导出行去重 ④ 开平仓字段（BTO/STC/BTC/STO）缺失时**不要默认 BUY=开仓**，先让用户核对方向。

---

## 1. 富途 / moomoo

### 接入流程
- **手动（推荐起步）**：富途牛牛 **PC 客户端** → 交易 → 历史成交 / 交割单 → 选时间段 → 导出 Excel/CSV。移动端能查、导出用 PC 顺手
- **程序化**：按 `_shared/broker-connectors.md` 连接富途官方 Futu Agent Skills + OpenD，优先调用官方读取能力拉历史成交；具体脚本/接口以已安装官方 Skill 与当前 `--help` 为准

### 接口
- 官方 Skill / SDK：前提是账户已完成 OpenAPI 权限流程、OpenD 在跑且用户已登录；EdgeLab 连接器只读
- 不想搞 API 就纯手动导出，足够复盘用

### 提醒用户
- OpenD 要本地常驻、占端口；首次要在富途开 API 权限
- 导出文件常含**账户号/资金额**——给我前自己删，只留成交字段
- 期权代码格式（富途的期权 symbol）注意拆出 underlying/到期/行权/CP，拆法见下节

### OpenD 成交记录要点（2026-10 只读实测）
- **期权代码**：格式是「市场.标的 + YYMMDD + C/P + 行权价×1000」，可用正则 `^(US|HK)\.([A-Z]+)(\d{6})([CP])(\d+)$` 拆，行权价要除以 1000。港股期权的标的是 3 个字母的期权简码，不是正股代码，要用行情快照的 `stock_owner` 映射回正股，正股和期权的 `underlying` 才能对上。
- **价格与乘数**：期权成交价是每股权利金，没乘合约乘数。美股乘数 100；港股每个标的不同，用快照的 `option_contract_size` 查。已过期的代码查不到快照，而且一批代码里有一个查不到整批都会失败，要换成同一简码、还在交易的合约去查。
- **方向四个值**：`BUY` 买入开仓、`SELL` 卖出平仓、`SELL_SHORT` 卖出开仓、`BUY_BACK` 买回平仓（对应本 schema 的 `BUY_TO_CLOSE`）。正股基本只有 `BUY` / `SELL`；`SELL` 超出已有持股的部分不要当成卖空，可能是数据起点之前的持仓、拆合股或转入，先问用户。
- **手续费不在成交记录里**：拿 `order_id` 调 `order_fee_query` 补，返回订单的费用合计和逐项明细，正股、期权、组合单都能查。有频率限制（每 30 秒最多 10 次、每次最多 400 个订单）。组合单的费用是合在一起的，要按张数分摊到各条腿。
- **没下单也会出现的成交行**：到期作废是一行价格为 0 的期权成交；被行权是一行价格为 0 的期权成交，加一行价格等于行权价、股数等于张数×乘数的正股成交；提前指派可能只有正股那一行。实测中较早期间（2025 年 9 月以前）的到期、行权没有价格为 0 的那一行，对账出现「已过到期日、计算还有余量、实际持仓为 0」的期权，按到期或被行权和用户确认，不要自动补。到期行常在到期后一两天才入账，持有天数按到期日算。
- **拆股、合股不回溯调整**：期权代码会变（行权价和张数一起变），正股的股数和价格也会变，旧成交不会调整。按代码先进先出会留下实际不存在的仓位，正股盈亏也会算错。看到价格断层或期权代码变化，先确认拆合比例再换算。
- **多腿**：组合单的各条腿共用 `order_id`，价差配对靠它。历史订单接口查不到组合单，别依赖其中的 `strategy_type`、`combo_legs`。开仓是组合单、平仓逐腿平（或反过来）的，拆回单腿再按完整合约代码配对。
- **查询口径**：`history_deal_list_query` 的起止日期按北京时间解释，返回的 `create_time` 是交易所当地时间（美股为美东），边界多拉一天再按 `deal_id` 去重。综合账户的 `filter_trdmarket` 不起作用，港美股一次全部返回，同样按 `deal_id` 去重。查成交、持仓、手续费都不需要解锁交易。

### 典型导出字段 → schema 映射（以实际列名为准）
成交时间→`trade_date`，代码/名称→`symbol`/`underlying`，方向（买入/卖出/卖空/买入平仓）→`side`，成交数量→`qty`，成交价格→`price`，手续费/佣金→`fee`

OpenD 直连时：`deal_id`→`fill_id`，`order_id`→`order_id`，`create_time`→`trade_date`，`code`→`symbol`（期权另拆出 `underlying`/`expiry`/`strike`/`cp`），`trd_side`→`side`（`BUY_BACK` 写成 `BUY_TO_CLOSE`，开平按上节四个值填 `open_close`），`qty`→`qty`，`price`→`price`，`fee` 由 `order_fee_query` 补，`multiplier` 按上节规则填。

---

## 2. 长桥 Longbridge

### 接入流程
- **手动**：App / 网页 → 我的 → 订单 / 交割单 → 导出
- **程序化**：按 `_shared/broker-connectors.md` 使用长桥官方 `longbridge` CLI（机器输出加 `--format json`）或 hosted MCP，通过 OAuth 读取历史订单/成交

### 接口
- 首选官方 CLI / MCP + OAuth；Python SDK 是高级自定义集成，不等于 CLI，也不是普通用户的默认安装路径

### 提醒用户
- OAuth 过期、撤销或权限不足时重新登录/授权；不要让用户把 token 粘进对话
- 方向字段可能是英文 Buy/Sell + 开平标识，**注意区分开仓/平仓**，否则 FIFO 配错
- 同样：导出删账户号/资金额

### 字段映射
执行时间→`trade_date`，标的代码→`symbol`/`underlying`，方向+开平→`side`，数量→`qty`，价格→`price`，费用→`fee`

---

## 3. IBKR（盈透）

### 接入流程
- **Flex Query（推荐，最省事）**：Client Portal（旧称 Account Management）→ Performance & Reports → **Flex Queries** → 新建一个 **Trades** flex query（勾选要的字段）→ 运行生成 CSV/XML。可手动下，也可用 **Flex Web Service**（拿一个 token 程序化拉），不用开着 TWS
- **官方 MCP（普通用户首选）**：按 `_shared/broker-connectors.md` 通过 IBKR OAuth 读取历史交易、持仓、期权链和风险；不需要为这条路径常驻 TWS/IB Gateway
- **高级 API**：需要实时流式或自定义批处理时才考虑官方 Web API / TWS API；另做工程评估，不把社区封装当默认依赖

### 接口
- 对话式账户读取首选官方 MCP；批量、确定性的历史报表首选 **Flex Query**（不用挂 TWS）

### 提醒用户
- Flex Query 第一次要配置好"要哪些字段"（日期/symbol/买卖/数量/价格/佣金/conid）
- IBKR 字段最全也最杂；期权 symbol 用 OCC 格式，注意解析
- 多币种/多账户先让用户选账户，展示时默认使用别名/尾号；订单与成交必须分开

### 字段映射
TradeDate/DateTime→`trade_date`，Symbol/UnderlyingSymbol→`symbol`/`underlying`，Buy/Sell + Open/Close→`side`，Quantity→`qty`，TradePrice→`price`，IBCommission→`fee`，Expiry/Strike/Put-Call→期权三件

---

## 4. 其它券商（老虎/雪盈/Robinhood 等）

几乎都能网页端导出"成交明细 / 交割单 CSV"。只要能凑齐标准 schema 那几列就行；凑不齐的字段标"缺"，影响哪步分析就跟用户说清。
