# elab-model 模型登记表

> 仿 `elab-research/references/tool-registry.md` 风格。每模型一条：输入协议 / 公式口径（明文可审计）/ 输出 JSON 骨架 / 适用边界 + 已知失效场景 / warnings 文案模板。
>
> **SSOT 约定**：elab-trade / elab-research / elab-diagnosis 引用本表条目时只写"引用 elab-model registry §N 模型名"，不在各自 SKILL.md 重复公式。本表修改时，消费方同步更新引用标注。

---

## 一、EV 模型（ev_model.py · 子命令 `ev`）

### 输入协议

| 参数 | 类型 | 单位 | 来源要求 |
|---|---|---|---|
| `--win-rate` | float 0–1 | — | 必须带来源标签：`[交割单统计 N笔]` / `[本人假设]` / `[回测 N笔 OOS=是/否]` |
| `--avg-win` | float | per-trade 美元（正数） | 用户输入或 deals.xlsx FIFO 统计 |
| `--avg-loss` | float | per-trade 美元（负数，如 -200） | 同上 |
| `--sample-size` | int，可选 | 笔数 | FIFO 统计产出传入；缺省 = None（视为假设值） |

**样本量规则**：`sample_size` 缺省或 None → warnings 追加"假设值，非统计"。`sample_size < 20` → warnings 追加"样本不足（N 笔），低于 20 笔阈值，结果仅供参考"（阈值来自 `thresholds.json` `min_sample_size`）。

### 公式口径（明文）

```
EV               = win_rate × avg_win + (1 − win_rate) × avg_loss
payoff_ratio     = |avg_win / avg_loss|
breakeven_win_rate = |avg_loss| / (avg_win + |avg_loss|)
  # 满足 p × avg_win = (1−p) × |avg_loss| 时 EV=0 的 p
Kelly f*         = (b × p − q) / b
  # b = payoff_ratio，p = win_rate，q = 1 − win_rate
kelly_quarter    = Kelly f* / 4
```

**黄金 case（实现必须 ±0.01 对上）**：win_rate=0.45，avg_win=300，avg_loss=−200 →
EV=25.0，breakeven=0.40，Kelly=0.0833，quarter=0.0208。

### 输出 JSON 骨架

```json
{
  "model": "ev",
  "inputs": {
    "win_rate": {"value": 0.45, "source": "[交割单统计 15笔]"},
    "avg_win": 300,
    "avg_loss": -200,
    "sample_size": 15
  },
  "ev_per_trade": 25.0,
  "payoff_ratio": 1.5,
  "breakeven_win_rate": 0.40,
  "kelly_full": 0.0833,
  "kelly_quarter": 0.0208,
  "units": {"ev_per_trade": "per_trade_dollar"},
  "warnings": ["win_rate 样本仅 15 笔，低于 20 笔阈值，结果仅供参考"],
  "as_of": "2026-07-19"
}
```

`warnings` 不可省略——空也输出 `[]`。

### 适用边界 + 已知失效场景

- **Kelly 对肥尾失效**：收益分布有极端尾部（如裸 put、尾部大亏损）时，Kelly 建议仓位严重高估，实盘需主动折扣（quarter Kelly 为此而设）。
- **样本 <20 不可靠**：统计胜率在小样本下方差极大，20 笔以下数字参考价值有限。
- **avg_win / avg_loss 来自假设时**：整个 EV 只是假设的函数，不是统计结论——warnings 须提示。
- **回测结果无 OOS**：回测胜率进 ev_model 时，若 `oos_split=false`，来源标 `[回测 N笔 OOS=否]`，调用方解读须标"过拟合风险"。

### warnings 文案模板

| 触发条件 | 文案 |
|---|---|
| `sample_size` 缺省或 None | `"win_rate 来源为假设值，非交割单统计"` |
| `sample_size < 20` | `"win_rate 样本仅 {N} 笔，低于 20 笔阈值，结果仅供参考"` |
| 回测来源且 OOS=否 | `"win_rate 来源为回测（{N} 笔，无 OOS），存在过拟合风险"` |

---

## 二、Kelly 仓位（ev_model.py · 子命令 `kelly`）

### 输入协议

| 参数 | 类型 | 单位 | 来源要求 |
|---|---|---|---|
| `--win-rate` | float 0–1 | — | 同 §一，必须带来源标签 |
| `--payoff-ratio` | float > 0 | — | `avg_win / |avg_loss|`，用户提供 |
| `--fraction` | float，可选 | — | 缺省 0.25（quarter Kelly） |
| `--sample-size` | int，可选 | 笔数 | 同 §一 |

### 公式口径（明文）

```
Kelly f* = (b × p − q) / b    # b=payoff_ratio，p=win_rate，q=1−win_rate
fractional_kelly = f* × fraction
```

若 `f* ≤ 0`（负 EV 或 Kelly 为负），输出 `kelly_full=0`（不建议开仓），warnings 追加"Kelly ≤ 0，当前假设下 EV 为负"。

### 输出 JSON 骨架

```json
{
  "model": "kelly",
  "inputs": {
    "win_rate": {"value": 0.45, "source": "[本人假设]"},
    "payoff_ratio": 1.5,
    "fraction": 0.25,
    "sample_size": null
  },
  "kelly_full": 0.0833,
  "fractional_kelly": 0.0208,
  "units": {"kelly_full": "fraction_of_capital", "fractional_kelly": "fraction_of_capital"},
  "warnings": ["win_rate 来源为假设值，非交割单统计"],
  "as_of": "2026-07-19"
}
```

### 适用边界 + 已知失效场景

- Kelly 假设结果只有"赢 avg_win / 输 avg_loss"两种（二元），实盘期权有多点 P&L 分布，此时 Kelly 仅为近似。
- 肥尾失效同 §一。建议 quarter Kelly 作为默认，full Kelly 仅做参考上界。
- `kelly_full` 返回分数（如 0.0833 = 资本的 8.33%），**不是张数/手数**，换算由用户自行做。

### warnings 文案模板

同 §一。

---

## 三、option-credit EV（ev_model.py · 子命令 `option-credit`）

### 输入协议

| 参数 | 类型 | 单位 | 来源要求 |
|---|---|---|---|
| `--credit` | float > 0 | per-share 美元 | 期权链或交易确认单 |
| `--max-loss` | float > 0 | per-share 美元（含 credit） | 期权链：spread 宽度，即权利金最大亏损 |
| `--pop` | float 0–1 | — | 只接受两种来源：`--pop-source delta`（期权链 delta 近似）/ `--pop-source manual`（用户自填） |
| `--pop-source` | `delta` \| `manual` | — | 必须提供 |

### 内部数学映射（明文，口径不分叉）

```
avg_win  = credit                         # 每张到期无价值获利上限（per-share）
avg_loss = −(max_loss − credit)           # 每张最大亏损（per-share，负数）
win_rate = pop
```

映射后走与 `ev` 子命令完全相同的 EV 核心公式（§一）。

**OTM 强制警告**：当 `pop-source=delta` 且 `credit / max_loss < otm_deep_ratio`（默认 0.30，来自 `thresholds.json`）时，warnings 强制追加：`"OTM 场景 delta 近似 pop 系统性偏高，实际 pop 可能更低"`。

### 输出 JSON 骨架

```json
{
  "model": "option-credit",
  "inputs": {
    "credit": 0.85,
    "max_loss": 5.00,
    "pop": 0.72,
    "pop_source": "delta"
  },
  "avg_win_mapped": 0.85,
  "avg_loss_mapped": -4.15,
  "ev_per_share": -2.5588,
  "ev_per_contract": -255.88,
  "breakeven_win_rate": 0.83,
  "kelly_full": 0.0,
  "kelly_quarter": 0.0,
  "units": {"ev_per_share": "per_share_dollar", "ev_per_contract": "per_contract_dollar"},
  "warnings": ["OTM 场景 delta 近似 pop 系统性偏高，实际 pop 可能更低"],
  "as_of": "2026-07-19"
}
```

### 适用边界 + 已知失效场景

- **pop≈delta 是近似，且 OTM 系统性偏高**：对于深度 OTM 期权，delta 会高估真实 pop（真实 pop 受到风险中性概率 vs 实际概率的楔子影响）。`pop-source=delta` 时务必配合 OTM 警告。
- 用户自填 pop（`manual`）时整个 EV 是假设函数，warnings 注明"假设值，非统计"。
- `max_loss` 必须大于 `credit`，否则 exit 1（参数逻辑错误）。

### warnings 文案模板

| 触发条件 | 文案 |
|---|---|
| `pop-source=delta` 且 OTM 特征 | `"OTM 场景 delta 近似 pop 系统性偏高，实际 pop 可能更低"` |
| `pop-source=manual` | `"pop 来源为用户假设值，非统计或工具输出"` |

---

## 四、策略模板（strategy_models.py）

> 共用约定：
> - `--config` 缺省自动指向同目录 `thresholds.json`；JSON 解析失败 → fallback 代码内常量 + warnings 追加 `"使用内置默认阈值"`。
> - 单位纪律：`max_profit` / `max_loss` 输出 per-contract 美元（per-share × 100）；`breakeven` 与宽度保持 per-share；`units` 字段必含。
> - `greeks_exposure` 一律标 `[定性]`，不算精确希腊值。
> - `assignment_risk` 只含距 short 腿 % 和到期周提示，不含"需要操作"类描述。

### 4a. bull-put-spread

**术语方向性**（代码注释与输出写死）：收 credit 看多，**非对冲工具**。

#### 输入协议

| 参数 | 单位 | 说明 |
|---|---|---|
| `--short-strike` | per-share | short put 行权价 |
| `--long-strike` | per-share | long put 行权价（< short-strike） |
| `--credit` | per-share | 净收入 |
| `--dte` | 天数 | 到期天数 |
| `--spot` | per-share，可选 | 当前标的价格 |
| `--iv` | float 0–1，可选 | 当前 IV（定性参考） |
| `--config` | 文件路径，可选 | 阈值 JSON，缺省同目录 `thresholds.json` |

#### 公式口径（明文）

```
width          = short_strike − long_strike           # per-share，不乘 100
max_profit     = credit × 100                         # per-contract 美元
max_loss       = (width − credit) × 100               # per-contract 美元
breakeven      = short_strike − credit                # per-share
risk_reward    = max_profit / max_loss                # 比值（无单位）
```

**宽度计算写死**：`width = |short_strike − long_strike|`，单位 per-share，不乘合约乘数 100。registry 明文登记，防止两种算法差 100 倍。

**"收得太薄"警告**：`credit / width < credit_width_min_ratio`（默认 0.20，来自 `thresholds.json`）→ warnings 追加 `"credit 仅占宽度 {pct:.0%}，低于 20% 阈值，风险收益比较差"`。

**黄金 case**：short=95，long=90，credit=1.35 → width=5，max_loss=(5−1.35)×100=**365/张**，breakeven=95−1.35=**93.65**。

#### 输出 JSON 骨架

```json
{
  "model": "bull-put-spread",
  "inputs": {
    "short_strike": 95, "long_strike": 90, "credit": 1.35,
    "dte": 30, "spot": 102, "iv": 0.42
  },
  "width": 5.0,
  "max_profit": 135.0,
  "max_loss": 365.0,
  "breakeven": 93.65,
  "risk_reward": 0.3699,
  "ev_breakeven_pop": null,
  "greeks_exposure": {
    "delta": "正（看多）",
    "theta": "正（收时间价值）",
    "vega": "负（IV 上升不利）",
    "note": "[定性]"
  },
  "assignment_risk": {
    "spot_distance_pct": null,
    "dte_weeks": 4.29
  },
  "units": {
    "max_profit": "per_contract_dollar",
    "max_loss": "per_contract_dollar",
    "breakeven": "per_share",
    "width": "per_share"
  },
  "warnings": [],
  "as_of": "2026-07-19"
}
```

`ev_breakeven_pop` 由 ev_model 串联填入（EV=0 时所需 pop）；若 ev_model 调用失败则输出 null + warnings 注明。

#### 适用边界 + 已知失效场景

- 适用：有明确看多偏多方向、愿意限制上行收益换取定义风险的场景。
- 不适用：对冲已有多头（此时应用 bear-put-spread）。
- 回测期权策略时，数据质量和行权价填充影响大，无 OOS 结果不可信。

### 4b. bear-put-spread

**术语方向性**（代码注释与输出写死）：付 debit 看跌，**对冲工具**（非 bull put）。

#### 输入协议

| 参数 | 单位 | 说明 |
|---|---|---|
| `--long-strike` | per-share | long put 行权价（较高） |
| `--short-strike` | per-share | short put 行权价（较低） |
| `--debit` | per-share | 净付出（正数） |
| `--dte` | 天数 | — |
| `--spot` | per-share，可选 | — |
| `--config` | 可选 | 同 4a |

#### 公式口径（明文）

```
width          = long_strike − short_strike    # per-share
max_profit     = (width − debit) × 100        # per-contract 美元
max_loss       = debit × 100                  # per-contract 美元（初始成本）
breakeven      = long_strike − debit          # per-share
```

### 4c. covered-call

付出已有多头股份，卖出 call 收 premium，限制上行收益。

#### 公式口径

```
max_profit    = (call_strike − entry_price + credit) × 100  # per-contract
max_loss      = (entry_price − credit) × 100                # per-contract（股价归零极端情况）
breakeven     = entry_price − credit                        # per-share
```

> Covered Call 是"有 premium 的一次性止盈"，不是真分层对冲。代码注释写死。

### 4d. cash-secured-put

卖出 put，现金担保，愿意以 strike 价买入标的。

#### 公式口径

```
max_profit    = credit × 100              # per-contract
max_loss      = (strike − credit) × 100  # per-contract（股价归零极端）
breakeven     = strike − credit          # per-share
```

### 4e. long-put

买入 put，对冲或方向性下行。

#### 公式口径

```
max_profit    = (strike − debit) × 100   # per-contract（股价归零）
max_loss      = debit × 100              # per-contract（权利金全损）
breakeven     = strike − debit           # per-share
```

---

## 五、thresholds.json 字段说明

> 实体文件：`scripts/thresholds.json`（扁平 key-value JSON，无注释）

| key | 默认值 | 含义 | 使用位置 |
|---|---|---|---|
| `min_sample_size` | 20 | 胜率样本量阈值，低于此值 warnings 强制提示 | §一、§二 |
| `credit_width_min_ratio` | 0.20 | credit 与 spread 宽度比值下限；低于此值警告"收得太薄" | §四 bull/bear put |
| `otm_deep_ratio` | 0.30 | option-credit 子命令：`credit/max_loss` 低于此值认定为 OTM 特征，触发 delta 近似偏高警告 | §三 |

`--config` 文件缺失或 JSON 解析失败时，脚本回退代码内 fallback 常量（与此表值相同），warnings 追加 `"使用内置默认阈值"`，不 crash、不静默。
