# 回测协议（backtest_protocol.md）

> 版本：v1.0.0 · 2026-07-19
> 仅定协议，不含实现。实现归 quant-engine（Codex 领地）；elab-model 侧规定请求/结果格式，两边照协议对话。
> 设计 SSOT：`docs/plans/2026-07-19-elab-model-design.md` §4 + §5

---

## 1. 协议定位

```
elab-model ──[请求 JSON]──► quant-engine
           ◄──[结果 JSON]──
```

- elab 侧负责：组装请求、解析结果、执行三闸校验、写入 playbook
- quant-engine 侧负责：数据管道、防过拟合执行、生成结果 JSON
- 两侧只通过本文件定义的 JSON 格式通信，不透传内部结构

---

## 2. 请求 schema（elab → quant-engine）

### 2.1 字段定义

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `strategy` | string | 是 | 策略类型，取值见下方枚举表 | `"bull_put_spread"` |
| `universe` | string[] | 是 | 标的列表，1 至 10 个 ticker；超出 10 个须分批请求 | `["TSLA", "NVDA"]` |
| `entry_rule` | string | 是 | 入场规则**明文表达式**，禁止黑盒描述（见 §2.2 明文规则要求） | `"IV_rank > 60"` |
| `period` | string | 是 | 回测区间，格式 `YYYY-MM ~ YYYY-MM`（首月到末月，含首含末）；最短 6 个月，否则 quant-engine 应拒绝并返回错误 | `"2022-01 ~ 2026-06"` |
| `exit_rule` | string | 否 | 出场规则明文；缺省 = quant-engine 默认（到期或到期前 5 DTE）| `"profit >= 50% of max_profit"` |
| `position_sizing` | string | 否 | 仓位规则明文；缺省 = 均等权重 1 合约/次 | `"kelly_quarter"` |
| `notes` | string | 否 | 给 quant-engine 的补充说明，不进结果 JSON | `"仅取周三开仓信号"` |

**`strategy` 枚举（与 strategy_models.py 首批模板一一对应）**：

| 值 | 含义 | 方向性备注 |
|---|---|---|
| `bull_put_spread` | 卖 put 垂差：收 credit，看多/中性 | **非对冲**，看多方向工具 |
| `bear_put_spread` | 买 put 垂差：付 debit，看跌 | 对冲工具，非收益性开仓 |
| `covered_call` | 持股卖 call | 有 premium 的一次性止盈，非持续对冲 |
| `cash_secured_put` | 现金担保裸卖 put | 看多/愿接货 |
| `long_put` | 买保护性 put | 纯对冲 |

### 2.2 明文规则要求（entry_rule 合规性）

`entry_rule` 必须是**机器可解析的条件表达式**，禁止以下写法：

- 禁止：`"按我的判断入场"`、`"看均线方向"`、`"市场好就开"`（黑盒/主观描述）
- 允许：`"IV_rank > 60"`、`"price_above_200sma AND IV_rank > 50"`、`"delta_of_short_leg < 0.30"`

quant-engine 收到 `entry_rule` 后必须能将其编译为布尔过滤函数，否则返回 `error: entry_rule_unparseable`。

### 2.3 请求 JSON 完整示例

```json
{
  "strategy": "bull_put_spread",
  "universe": ["TSLA", "NVDA"],
  "entry_rule": "IV_rank > 60",
  "period": "2022-01 ~ 2026-06",
  "exit_rule": "profit >= 50% of max_profit OR DTE <= 5",
  "position_sizing": "1 contract per signal",
  "notes": "仅统计周三/周四开仓信号，周五不开"
}
```

---

## 3. 结果 schema（quant-engine → elab）

### 3.1 字段定义

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `trades` | integer | 笔 | 回测期间实际触发的总笔数（过滤后，非信号数）；N < 20 时 quant-engine 必须在 `warnings` 注明"样本量不足 20 笔，统计不稳定" |
| `win_rate` | float | 0–1 小数 | 盈利笔数 / 总笔数；**与 ev_model 口径对齐**——此处 1 笔 = 1 份合约（per-contract） |
| `avg_win` | float | per-contract USD | 盈利笔的平均收益（含 premium，扣佣金）；正值；**必须与 ev_model `avg_win` 参数口径一致**（per-contract dollar，即已×合约乘数 100） |
| `avg_loss` | float | per-contract USD | 亏损笔的平均亏损；**负值**；绝对值即 ev_model `avg_loss` 的负数输入 |
| `max_drawdown` | float | per-contract USD | 最大回撤：回测期间连续亏损的累计最大值（基于 per-contract 口径）；负值 |
| `ev_per_trade` | float | per-contract USD | quant-engine 侧预算的 EV（`win_rate × avg_win + (1−win_rate) × avg_loss`）；elab 侧收到后可选择用 ev_model.py 交叉验算，以 ev_model 结果为准 |
| `oos_split` | boolean | — | 是否包含样本外（out-of-sample）验证；`false` 时 `warnings` 必须含 `"无 OOS 分割，存在过拟合风险"` |
| `oos_ratio` | float | 0–1 小数 | OOS 占总回测期的比例（如 0.3 = 最近 30% 为 OOS）；`oos_split=false` 时输出 `null` |
| `as_of` | string | YYYY-MM-DD | 结果生成日期（数据截止日，非运行日） |
| `data_source` | string | — | 数据来源描述；例 `"Polygon.io daily OHLCV + option chain"` |
| `warnings` | string[] | — | 警示数组；空时输出 `[]`，不可省略；elab 侧**必须原样转述**，不许吞 |
| `request_echo` | object | — | 原样回传请求 JSON（校验用），供 elab 侧对账；quant-engine 必须原封回传，不得修改 |

### 3.2 单位纪律（与 ev_model 口径对齐）

结果中所有金额字段（`avg_win`、`avg_loss`、`max_drawdown`、`ev_per_trade`）统一为 **per-contract dollar**（已乘合约乘数 100）。

对账公式（elab 侧可用 ev_model.py 交叉验算）：

```
ev_model.py ev \
  --win-rate  <win_rate> \
  --avg-win   <avg_win> \
  --avg-loss  <avg_loss> \
  --sample-size <trades>
```

两侧 `ev_per_trade` 相差 > $1 时，elab 以 ev_model.py 结果为准，并在 playbook 记录差异。

### 3.3 结果 JSON 完整示例

```json
{
  "trades": 47,
  "win_rate": 0.72,
  "avg_win": 128.0,
  "avg_loss": -312.0,
  "max_drawdown": -936.0,
  "ev_per_trade": 4.64,
  "oos_split": true,
  "oos_ratio": 0.30,
  "as_of": "2026-06-30",
  "data_source": "Polygon.io daily OHLCV + option chain",
  "warnings": [],
  "request_echo": {
    "strategy": "bull_put_spread",
    "universe": ["TSLA", "NVDA"],
    "entry_rule": "IV_rank > 60",
    "period": "2022-01 ~ 2026-06",
    "exit_rule": "profit >= 50% of max_profit OR DTE <= 5",
    "position_sizing": "1 contract per signal",
    "notes": "仅统计周三/周四开仓信号，周五不开"
  }
}
```

### 3.4 错误结果格式（quant-engine → elab）

当请求无法处理时，quant-engine 返回以下格式（HTTP 或文件均适用）：

```json
{
  "error": "entry_rule_unparseable",
  "message": "entry_rule 无法解析为布尔条件：'按我的判断入场'",
  "request_echo": { "...原始请求..." }
}
```

错误码枚举：`entry_rule_unparseable` / `period_too_short` / `universe_too_large` / `data_unavailable` / `internal_error`

---

## 4. 防玩具化三闸

**三闸为硬规则，elab 侧校验，不可跳过。**

### 闸一：样本量 + OOS 必标

收到结果后，elab 侧校验：

- `trades < 20` → 在 playbook 记录时标 `[样本不足 待验证]`，不进入策略模板
- `oos_split == false` → 在 playbook 记录时标 `[过拟合风险]`，`ev_per_trade` 不写入 ev_model 来源统计

两条均触发时叠加标注，不择一省略。

### 闸二：win_rate 进 ev_model 必带来源标签

回测 `win_rate` 喂入 `ev_model.py` 时，来源标签格式固定为：

```
[回测 N笔 OOS=是/否]
```

示例：`[回测 47笔 OOS=是]`、`[回测 12笔 OOS=否]`

此标签须写入：
1. `ev_model.py` 的 `--win-rate` 对应 `inputs.win_rate.source` 字段
2. playbook 相关条目的来源注释

**禁止**写 `[交割单统计]`（交割单与回测来源不同，不可混用标签）。

### 闸三：回测结论仅进 playbook §0 想法区

回测产出的策略结论**只能**写入 playbook 的"§0 想法区"，并标：

```
[想法 待验证]
```

升级路径：
- 积累 ≥ 10 笔**真实交割单**对应该策略 → 可升级至 §1 暂定策略（标 `[推断]`）
- 积累 ≥ 20 笔真实交割单 + 两个市场环境（牛/熊） → 可升级至 §2 策略模板（标 `[我的数据]`）

**回测结论永不直接进入 §2 策略模板**，无论样本量多大、OOS 多完整。

---

## 5. 会员边界

| 项目 | 自用 | 会员 |
|---|---|---|
| 本协议文档 | 可用 | **可分发**（方法透明，协议公开） |
| quant-engine 实现 | 完整访问 | **不分发**（数据管道 + 执行逻辑属 quant-engine 领地） |
| 回测能力 | 走 quant-engine 协议实测 | 只见协议；SKILL.md 明示"回测需自备数据管道" |
| 结果使用 | 依三闸规则进 playbook | 同左；三闸同等适用，不因场景放松 |

**SKILL.md 侧提示文案（elab-model SKILL.md 须含）**：

> 回测请求/结果协议见 `scripts/backtest_protocol.md`。会员注意：quant-engine 实现（数据管道、防过拟合执行）不随 elab-skills 分发，**运行回测需自备数据管道**并按协议格式输出结果 JSON。

---

## 6. quant-engine 侧交接说明

> 本节面向 Codex（quant-engine 维护方），描述接入本协议需要完成的工作。

### 6.1 Codex 需完成的工作

1. **读本协议**（§2 + §3 全文）：确认 `entry_rule` 解析方案、JSON 字段名/类型/单位与 elab ev_model 口径一致

2. **实现请求解析**：
   - 接收 §2.3 格式的请求 JSON
   - 解析 `entry_rule` 为布尔过滤函数；无法解析返回 `entry_rule_unparseable` 错误
   - 拒绝 `period` 不足 6 个月的请求
   - 拒绝 `universe` 超过 10 个 ticker 的请求

3. **实现结果输出**：
   - 所有金额字段统一 per-contract dollar（×100 合约乘数）
   - `oos_split=false` 时 `warnings` 必须含 `"无 OOS 分割，存在过拟合风险"`
   - `trades < 20` 时 `warnings` 必须含 `"样本量不足 20 笔，统计不稳定"`
   - `warnings` 不可省略，空时输出 `[]`
   - `request_echo` 原封回传，不修改

4. **交叉验算对账**：以 §3.2 公式验算 `ev_per_trade`，确保与 elab ev_model.py 差值 ≤ $1

5. **双方 owner 签认**（见 §6.2）

### 6.2 验收条件

**验收 = 协议双签，不绑实现跑通进度。**

elab 侧（elab 侧）和 quant-engine 侧（Codex 执行）分别在此文件末尾追加确认行：

```
elab 侧：已读协议 §1–§5，接受字段定义与三闸要求。— [日期]
quant-engine 侧：已读协议 §2–§3，接受请求/结果格式，将按此实现解析与输出。— [日期]
```

签认后，任何字段变更须两侧同时更新协议版本号（`vX.Y.Z`，语义版本）并重新签认。

### 6.3 不在 quant-engine 范围内的事项

- 三闸校验（elab 侧负责，quant-engine 只保证结果字段完整）
- playbook 写入（elab 侧负责）
- ev_model.py 交叉验算（elab 侧选择性执行）
- 会员分发控制（elab-skills repo 层面管理）

---

*本文件是 elab-model 与 quant-engine 之间的唯一接口契约。改动本文件须更新版本号并知会两侧 owner。*
