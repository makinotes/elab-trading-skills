# 券商数据接入参考（富途 / 长桥 / IBKR）

> `elab-trade` Mode B（交割单诊断）的券商接入分册。先确认用户用哪家券商，再翻到对应小节。每家给：**接入流程 / 接口 / 提醒用户的坑 / 导出字段**。
> ⚠️ 接口名、菜单路径、字段名会随券商版本变——本册标的是"方法和该找什么"，具体名称**以券商当前界面/官方文档为准**，对不上让用户截图导出列名给你，现场映射。

---

## 通用：本 skill 最终要的标准 schema

不管哪家，归一成这张表（每行一笔成交）：

`trade_date | symbol | underlying | side(BUY/SELL/SELL_SHORT/BUY_TO_CLOSE) | qty | price | fee | [expiry | strike | cp]`

期权：`qty`=张数（1 张=100 股），多 `expiry/strike/cp`。

---

## 1. 富途 / moomoo

### 接入流程
- **手动（推荐起步）**：富途牛牛 **PC 客户端** → 交易 → 历史成交 / 交割单 → 选时间段 → 导出 Excel/CSV。移动端能查、导出用 PC 顺手
- **程序化**：装并运行 **FutuOpenD**（本地网关程序，要常驻）→ Python `pip install futu-api` → 连本地 OpenD → 拉历史成交（找"历史成交/交割单"类接口，如 `get_history_deal_list` 一类，具体名以 SDK 文档为准）

### 接口
- SDK：`futu-api`（Python）；前提：富途账户**开通 OpenAPI 权限** + OpenD 在跑 + 已登录
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
- **程序化**：长桥 **OpenAPI** → Python `pip install longbridge`（⚠️ 官方已把包从 `longport` 重命名为 `longbridge`，`longport` 已废弃；import 走 `from longbridge.openapi import TradeContext`）→ 拉历史成交（`history_executions` / `today_executions` 一类，名以官方文档为准）

### 接口
- SDK：`longbridge`（Python，也有其它语言；旧 `longport` 已废弃）；前提：开发者后台申请 **App Key / App Secret / Access Token**
- Access Token **有定期失效**，过期要重新生成

### 提醒用户
- 要先在长桥开发者后台申请 API 凭据（比富途多一步）
- 方向字段可能是英文 Buy/Sell + 开平标识，**注意区分开仓/平仓**，否则 FIFO 配错
- 同样：导出删账户号/资金额

### 字段映射
执行时间→`trade_date`，标的代码→`symbol`/`underlying`，方向+开平→`side`，数量→`qty`，价格→`price`，费用→`fee`

---

## 3. IBKR（盈透）

### 接入流程
- **Flex Query（推荐，最省事）**：Client Portal（旧称 Account Management）→ Performance & Reports → **Flex Queries** → 新建一个 **Trades** flex query（勾选要的字段）→ 运行生成 CSV/XML。可手动下，也可用 **Flex Web Service**（拿一个 token 程序化拉），不用开着 TWS
- **API**：TWS 或 IB Gateway 运行 + Python `ib_async`（`ib_insync` 原作者 2024 去世、已停维护，社区继任分叉 `ib_async`，`pip install ib_async`）或官方 `ibapi` → 拉 executions/fills

### 接口
- 首选 **Flex Query**（报告式，稳定、不用挂 TWS）
- 实时/程序化才用 TWS API + `ib_async`（ib_insync 继任），需 TWS/Gateway 常驻 + 开 API

### 提醒用户
- Flex Query 第一次要配置好"要哪些字段"（日期/symbol/买卖/数量/价格/佣金/conid）
- IBKR 字段最全也最杂；期权 symbol 用 OCC 格式，注意解析
- 多币种/多账户的话先筛账户

### 字段映射
TradeDate/DateTime→`trade_date`，Symbol/UnderlyingSymbol→`symbol`/`underlying`，Buy/Sell + Open/Close→`side`，Quantity→`qty`，TradePrice→`price`，IBCommission→`fee`，Expiry/Strike/Put-Call→期权三件

---

## 4. 其它券商（老虎/雪盈/Robinhood 等）

几乎都能网页端导出"成交明细 / 交割单 CSV"。只要能凑齐标准 schema 那几列就行；凑不齐的字段标"缺"，影响哪步分析就跟用户说清。
