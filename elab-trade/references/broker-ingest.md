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
- 期权代码格式（富途的期权 symbol）注意拆出 underlying/到期/行权/CP

### 典型导出字段 → schema 映射（以实际列名为准）
成交时间→`trade_date`，代码/名称→`symbol`/`underlying`，方向（买入/卖出/卖空/买入平仓）→`side`，成交数量→`qty`，成交价格→`price`，手续费/佣金→`fee`

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
