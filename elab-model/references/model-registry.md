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
| `--config` | 文件路径，可选 | — | 阈值 JSON，缺省同目录 `thresholds.json`；`min_sample_size` 由此供给 |

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

这里 avg_win/avg_loss 是条件平均值；两类结果穷尽、口径一致时，EV 与盈亏平衡公式对连续损益同样成立。含零盈亏样本时先明确分母；不要把 Kelly 的二元近似限制误加给此均值公式。

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
| `--config` | 文件路径，可选 | — | 阈值 JSON，缺省同目录 `thresholds.json`；`min_sample_size` 由此供给 |

### 公式口径（明文）

```
Kelly f* = (b × p − q) / b    # b=payoff_ratio，p=win_rate，q=1−win_rate
kelly_quarter    = f* / 4                # 固定四分之一，不受 fraction 参数影响
kelly_fractional = f* × fraction        # fraction 缺省 0.25
```

若 `f* ≤ 0`（负 EV 或 Kelly 为负），输出 `kelly_full=0`（不建议开仓），warnings 追加"Kelly 为负（EV 在当前假设下为负），此值无实操意义，已归零"。
`f* > 0` 时，warnings 强制追加"Kelly 基于二元胜负分布假设，实盘肥尾下可能高估合理仓位，请结合 quarter Kelly 与极端情景使用"。

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
  "kelly_quarter": 0.0208,
  "kelly_fractional": 0.0208,
  "units": {
    "kelly_full": "fraction_of_capital",
    "kelly_quarter": "fraction_of_capital",
    "kelly_fractional": "fraction_of_capital"
  },
  "warnings": [
    "win_rate 来源为假设值，非交割单统计",
    "Kelly 基于二元胜负分布假设，实盘肥尾下可能高估合理仓位，请结合 quarter Kelly 与极端情景使用"
  ],
  "as_of": "2026-07-19"
}
```

### 适用边界 + 已知失效场景

- Kelly 假设结果只有"赢 avg_win / 输 avg_loss"两种（二元），实盘期权有多点 P&L 分布，此时 Kelly 仅为近似。
- 肥尾失效同 §一。建议 quarter Kelly 作为默认，full Kelly 仅做参考上界。
- `kelly_full` 返回分数（如 0.0833 = 资本的 8.33%），**不是张数/手数**，换算由用户自行做。

### warnings 文案模板

| 触发条件 | 文案 |
|---|---|
| `sample_size` 缺省或 None | `"win_rate 来源为假设值，非交割单统计"` |
| `sample_size < 20` | `"win_rate 样本仅 {N} 笔，低于 20 笔阈值，结果仅供参考"` |
| 回测来源且 OOS=否 | `"win_rate 来源为回测（{N} 笔，无 OOS），存在过拟合风险"` |
| `kelly_full <= 0` | `"Kelly 为负（EV 在当前假设下为负），此值无实操意义，已归零"` |
| `kelly_full > 0`（强制，无论样本） | `"Kelly 基于二元胜负分布假设，实盘肥尾下可能高估合理仓位，请结合 quarter Kelly 与极端情景使用"` |

---

## 三、option-credit EV（ev_model.py · 子命令 `option-credit`）

### 输入协议

| 参数 | 类型 | 单位 | 来源要求 |
|---|---|---|---|
| `--credit` | float > 0 | per-share 美元 | 期权链或交易确认单 |
| `--max-loss` | float > 0 | per-share 美元，扣权利金前的价差宽度 | 沿用旧参数名；填 spread 宽度，不能填扣除 credit 后的净最大亏损 |
| `--pop` | float 0–1 | — | 只接受两种来源：`--pop-source delta`（期权链 delta 近似）/ `--pop-source manual`（用户自填） |
| `--pop-source` | `delta` \| `manual` | — | 缺省 `manual`；使用 delta 近似时必须显式标明 |

### 内部数学映射（明文，口径不分叉）

```
avg_win  = credit                         # 每张到期无价值获利上限（per-share）
avg_loss = −(max_loss − credit)           # 每张最大亏损（per-share，负数）
win_rate = pop
```

映射后走与 `ev` 子命令完全相同的 EV 核心公式（§一）。这里假设结果只有收到全部 credit 或亏损全部净最大亏损两个极端，`pop` 是该二元假设中的正收益概率。真实价差存在中间盈亏，不能把此处盈亏平衡概率当作实际连续盈亏分布的获利概率门槛。

**比例提示与概率限制**：当 `pop-source=delta` 且 `credit / max_loss < otm_deep_ratio`（默认 0.30，来自 `thresholds.json`）时，warnings 强制追加：`"credit/max-loss 比例低于配置阈值；该比例不能确定价内外程度，也不能确定 delta 近似概率的误差方向"`。

### 输出 JSON 骨架

```json
{
  "model": "option-credit",
  "inputs": {
    "credit": 0.85,
    "max_loss": 5.0,
    "pop": {
      "value": 0.72,
      "source": "[工具输出/delta近似]"
    },
    "pop_source": "delta",
    "mapped": {
      "avg_win": 0.85,
      "avg_loss": -4.15,
      "win_rate": 0.72
    }
  },
  "ev_per_share": -0.55,
  "ev_per_contract": -55.0,
  "payoff_ratio": 0.2048,
  "breakeven_win_rate": 0.83,
  "kelly_full": 0.0,
  "kelly_quarter": 0.0,
  "units": {
    "ev_per_share": "per_share_dollar",
    "ev_per_contract": "per_contract_dollar"
  },
  "warnings": [
    "Kelly 为负（EV 在当前假设下为负），此值无实操意义，已归零",
    "delta是局部价格敏感度，不能直接当真实获利概率；到期价内概率近似与扣除权利金后的获利概率不同，近似误差方向未验证",
    "credit/max-loss 比例低于配置阈值；该比例不能确定价内外程度，也不能确定 delta 近似概率的误差方向",
    "本次EV把收益简化为credit与负的(max_loss-credit)两个结果；真实连续损益需完整分布，不能只凭获利概率确定EV"
  ],
  "as_of": "2026-09-21"
}
```

### 适用边界 + 已知失效场景

- **delta 不是真实获利概率**：它是局部价格敏感度；到期价内概率的常见近似也不等于扣除权利金后的获利概率，风险中性与实际概率还可能不同。没有对应样本不能断言误差固定偏高或偏低。`pop-source=delta` 始终输出该限制，低比例提示仅为兼容已有配置。
- 用户自填 pop（`manual`）时整个 EV 是假设函数，warnings 注明"假设值，非统计"。
- `max_loss` 必须大于 `credit`，否则 exit 1（参数逻辑错误）。

### warnings 文案模板

| 触发条件 | 文案 |
|---|---|
| `pop-source=delta` 且 credit/max-loss 比例低 | `"credit/max-loss 比例低于配置阈值；该比例不能确定价内外程度，也不能确定 delta 近似概率的误差方向"` |
| `pop-source=manual` | `"pop 来源为用户假设值，非统计或工具输出"` |

---

## 四、策略模板（strategy_models.py）

> 共用约定：
> - `--config` 缺省自动指向同目录 `thresholds.json`；JSON 解析失败 → fallback 代码内常量 + warnings 追加 `"使用内置默认阈值"`。
> - 单位纪律：`max_profit` / `max_loss` 输出 per-contract 美元（per-share × 100）；`breakeven` 与宽度保持 per-share；`units` 字段必含。
> - `greeks_exposure` 在 DTE > 0 时标 `[定性]`，不算精确希腊值；DTE 缺失或为 0 时为 `null`，只交付到期损益。
> - `assignment_risk` 只含距 short 腿 % 和到期周提示，不含"需要操作"类描述。

### 4a. bull-put-spread

**术语方向性**（代码注释与输出写死）：收 credit、偏多；**不能保护已有正股多头的下跌风险**。

#### 输入协议

| 参数 | 单位 | 说明 |
|---|---|---|
| `--short-strike` | per-share | short put 行权价 |
| `--long-strike` | per-share | long put 行权价（< short-strike） |
| `--credit` | per-share | 净收入 |
| `--dte` | 非负天数，可省略 | 缺失/0仅算到期损益，不输出希腊值 |
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
  "strategy_note": "收 credit、偏多；不能保护已有正股多头的下跌风险",
  "inputs": {
    "short_strike": 95.0,
    "long_strike": 90.0,
    "credit": 1.35,
    "dte": 30,
    "spot": 102.0
  },
  "width": 5.0,
  "max_profit": 135.0,
  "max_loss": 365.0,
  "breakeven": 93.65,
  "risk_reward": 0.3699,
  "ev_breakeven_pop": 0.73,
  "greeks_exposure": {
    "delta": "正（净多 delta，看多偏多）",
    "theta": "不固定；取决于标的相对两腿的位置和定价参数，须逐腿计算后相加",
    "vega": "不固定；两腿 Vega 抵消后的符号取决于位置、期限及各腿 IV",
    "note": "[定性]"
  },
  "assignment_risk": {
    "spot_distance_pct": 7.37,
    "dte_weeks": 4.2857
  },
  "units": {
    "max_profit": "per_contract_dollar",
    "max_loss": "per_contract_dollar",
    "breakeven": "per_share",
    "width": "per_share"
  },
  "warnings": [
    "ev_breakeven_pop仅适用于每次只发生最大盈利或最大亏损的二元假设；真实到期损益有中间状态，不能把它当通用获利概率或盈利概率门槛。"
  ],
  "as_of": "2026-09-21",
  "payoff_scope": "at_expiration_before_fees",
  "ev_breakeven_pop_assumption": "binary_extreme_outcomes_only"
}
```

`ev_breakeven_pop` 由 ev_model 串联填入（最大盈亏二元假设下 EV=0 的概率，不是真实连续损益的通用获利概率门槛）；若 ev_model 调用失败则输出 null + warnings 注明。

#### 适用边界 + 已知失效场景

- 适用：有明确看多偏多方向、愿意限制上行收益换取定义风险的场景。
- 不提供已有正股多头的下行保护；任何对冲都须另核对原持仓、数量、期限及保护区间。
- 回测期权策略时，数据质量和行权价填充影响大，无 OOS 结果不可信。

### 4b. bear-put-spread

**术语方向性**（代码注释与输出写死）：付 debit、偏空；可为匹配的多头持仓提供有限区间保护（非 bull put）。

#### 输入协议

| 参数 | 单位 | 说明 |
|---|---|---|
| `--long-strike` | per-share | long put 行权价（较高） |
| `--short-strike` | per-share | short put 行权价（较低） |
| `--debit` | per-share | 净付出（正数） |
| `--dte` | 非负天数，可省略 | 缺失/0仅算到期损益 |
| `--spot` | per-share，可选 | — |
| `--config` | 可选 | 同 4a |

#### 公式口径（明文）

```
width          = long_strike − short_strike    # per-share
max_profit     = (width − debit) × 100        # per-contract 美元
max_loss       = debit × 100                  # per-contract 美元（初始成本）
breakeven      = long_strike − debit          # per-share
```

**成本比例提示**：`debit / width < debit_width_min_ratio` 时只报告实际比例与配置阈值；不能由成本比例判断保护范围，须核对原持仓、行权价及期限。

### 4c. covered-call

付出已有多头股份，卖出 call 收 premium，限制上行收益。

#### 公式口径

```
max_profit    = (call_strike − entry_price + credit) × 100  # per-contract
max_loss      = (entry_price − credit) × 100                # per-contract（股价归零极端情况）
breakeven     = entry_price − credit                        # per-share
```

**可行性校验**：`call_strike + credit > entry_price` 必须成立（等价于 `max_profit > 0`），否则 exit 1（无效参数：卖出行权价低于持股成本加 credit，无上行获利空间）。

> Covered Call 是持股同时卖出 call：权利金提供有限缓冲并限制上行，不能提供完整下行保护。

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
| `otm_deep_ratio` | 0.30 | option-credit 子命令：`credit/max_loss` 低于此值触发比例提示；不据此判断价内外程度或误差方向 | §三 |
| `debit_width_min_ratio` | 0.20 | bear-put-spread：`debit/width` 低于此值触发成本比例提示，不判断保护范围 | §四 bear-put-spread |

`--config` 文件缺失或 JSON 解析失败时，脚本回退代码内 fallback 常量（与此表值相同），warnings 追加 `"使用内置默认阈值"`，不 crash、不静默。

---

## 六、组合压力与历史类比（portfolio_stress.py）

> 三个子命令共用同一份持仓输入。全部纯标准库、只读本地文件、不联网。结果是给定假设下的数学，不是交易指令。

### 输入协议

**持仓 JSON（stress / replay）**

| 字段 | 类型 | 说明 |
|---|---|---|
| `equity` | float | 账户权益（基准币种） |
| `margin_call` | float，可选 | 券商给出的追保线；给了就用于校准 `calibration_k`，不给按 Σ市值×维持比例 |
| `floor` | float，可选 | 用户自定的缓冲保底线，缺省 0 |
| `positions[]` | list | 每项：`id`（用户标签）、`qty`、`price`、`fx_to_base`（价格币种 ÷ 基准币种的汇率，缺省 1）、`maint_ratio`（0–1）、`leverage`（产品对底层的倍数，缺省 1）、`bucket`（冲击分组）、`series`（replay 用的日线文件名，不含 `.csv`） |
| `bucket_betas` | dict | 板块冲击：各 bucket 相对冲击幅度的倍数，未列出的 bucket 不动 |
| `systemic_betas` | dict，可选 | 系统性冲击，缺省 `{"*": 1.0}`（所有 bucket 同跌） |
| `maint_bump` | float，可选 | 维持比例统一上调幅度，**绝对值**（0.10 = 10 个百分点，不是相对上调 10%），缺省 0.10 |
| `sell_scenarios` | list[list[id]]，可选 | 要对比的卖出组合 |

**情景配置 JSON（regime / replay）**

| 字段 | 说明 |
|---|---|
| `anchor.conditions[]` | 每项 `series` + `drawdown_le` 或 `drawdown_ge`（较 `window` 日高点的回撤），全部满足的日子为锚点 |
| `anchor.window` / `gap_days` | 回撤窗口（缺省 20）；锚点最小间隔自然日（缺省 35） |
| `candidates[]` | `label`、`series`、`leverage`、`annual_cost`（年化费用，按 252 日每日扣）、`daily_drag`、`shift_days` |
| `exit_rules` | `names`（`T<N>`、`TP_SL`、`MA_REVERT`、`TRAIL`）、`tp` / `sl`（按杠杆 "1"/"2"/"3" 给）、`max_days`（缺省 40） |
| `levels[]` | `price_now`、`touch_levels`、`buy_levels`、`fill_window`（缺省 10）、`horizon`（缺省 40）、`cost_basis` |
| `bootstrap` | `iterations`（缺省 1000）、`seed` |
| `replay` | `days`、`target_equity`、`freeze`（不随历史移动的 id）、`liquidation_order`、`series_leverage`、`annual_cost`、`shift_days`、`plans[]`（`label` + `exits`：每个 id 一组 `{price, fraction}`，`fraction` 为原持仓比例，合计不超过 1） |

**日线 CSV**：`date,close[,high]`，日期 `YYYY-MM-DD`，至少 60 行；缺 `high` 时用 `close`。

### 公式口径（明文）

```
mv_i            = qty_i × price_i / fx_i
cash            = equity − Σ mv_i
k               = margin_call / Σ (mv_i × maint_i)          # 未给 margin_call 时 k = 1
buffer          = Σ mv_i + cash − k × Σ (mv_i × maint_i)
冲击 s 后       mv_i(s) = mv_i × max(1 − lev_i × beta_bucket × s, 0)
shock_to_X      = 使 buffer(s) < X 的最小 s（步长 0.25%，上限 95%；找不到为 null）
release_i       = 10000 × maint_i × k                         # 每卖 1 万释放的缓冲
合成杠杆        V_t = V_{t-1} × max(1 + L × r_t − annual_cost / 252 − daily_drag, 1e-6)
MA_REVERT       首个 收盘 ≥ 20 日均线 的交易日退出，或第 max_days 日
TP_SL           收益 ≥ tp 或 ≤ sl，或第 max_days 日
TRAIL           ≤ sl；或峰值收益 ≥ tp/2 后自峰值回撤 ≥ tp/2；或第 max_days 日
bootstrap       有放回重抽 n 个结果，取均值与胜率的 5% / 95% 分位
replay 强平     buffer < 0 当日按 liquidation_order 以收盘价卖出，直到 buffer ≥ 0
```

**黄金 case（测试覆盖）**：权益 60000、追保线 40000，A：1000 股 × 50、维持 0.5、板块 beta 1；B：500 股 × 100、维持 0.3、不受板块冲击。则 k=1，缓冲 20000；板块冲击 `buffer = 20000 − 25000s`，到保底线 5000 输出 0.6025、到追保线 0.8025（步长 0.25%，取首个低于阈值的 s）；系统性冲击 `buffer = 20000 − 60000s`，输出 0.25 与 0.335；维持比例 +0.10 后板块冲击到保底线输出 0.2525；卖出 A 后缓冲增加 25000。

### 输出 JSON 骨架

```json
{
  "model": "portfolio_stress.stress",
  "calibration_k": 1.0,
  "floor": 5000,
  "base": {"equity": 60000, "market_value": 100000, "cash": -40000, "gross_ratio": 1.6667,
           "look_through_ratio": 1.6667, "buffer": 20000,
           "targeted_shock_to_floor": 0.6025, "targeted_shock_to_margin_call": 0.8025,
           "targeted_shock_to_floor_maint_bump": 0.2525, "systemic_shock_to_floor": 0.25,
           "systemic_shock_to_margin_call": 0.335, "systemic_shock_to_floor_maint_bump": 0.1},
  "release_ranking": [{"id": "A", "buffer_release_per_10000": 5000, "look_through_release_per_10000": 10000}],
  "sell_scenarios": [{"sold": ["A"], "buffer": 45000, "...": "..."}],
  "warnings": ["..."],
  "units": {"money": "base_currency", "ratios": "fraction_of_equity", "shock": "underlying_fractional_decline"}
}
```

`regime` 输出 `anchors`、`n_anchors`、`effective_params`（实际生效的 tp / sl / max_days / 窗口 / bootstrap 参数）、`exit_results[]`（`label`、`rule`、`n`、`win_rate`、`payoff_ratio`、`mean`、`median`、`worst`、`mean_ci90`、`win_rate_ci90`、`split_half_mean`）、`levels[]`（`fill_window_days`、`touch[].prob`、`buy[].fill_prob` 与 `after_fill_20d`、`prob_reach_cost_basis`）。`replay` 输出 `plans[]`（`end_equity_median` / `p25` / `p10`、`prob_floor_before_first_exit`、`prob_forced_liquidation`、`prob_no_exit_filled`、`prob_touch_target`）。

### 适用边界 + 已知失效场景

- **线性保证金近似**：真实券商按组合、集中度和波动分档，压力期可能临时上调；`maint_bump` 只是一档敏感性，不是券商规则。
- **冲击是瞬时的**：stress 不含杠杆产品的路径损耗；路径效应看 regime / replay。
- **合成杠杆偏乐观**：没有溢价折价、跟踪误差、限额和停牌；`annual_cost` 要按产品实际费用与融资成本填。
- **样本小且重叠**：锚点通常几十个，前向窗口长于 `gap_days` 时互相重叠；只看方向，不看小数。
- **样本内选择**：在同一批锚点上比较多组价位，选出的最好组合天然偏乐观；用 `split_half_mean` 看稳定性，有条件就留出样本外区间。
- **强平与成交是收盘近似**：盘中触价、跳空、费用、汇率变化都未计入。

### warnings 文案模板

| 触发条件 | 文案 |
|---|---|
| 追保线与比例和相差 >15% | `"Broker margin line differs from the sum of position ratios (k=…)…"` |
| 未给 `margin_call` | `"margin_call not supplied; using the sum of position ratios without calibration."` |
| 锚点 < 30 | `"Only N anchors: treat rates as direction, not precision."` |
| 任一候选规则或买档成交后样本 < 30 | `"Sub-samples below 30: …. Read these rates as direction only."` |
| replay 路径 10–29 条 | `"Only N replay paths: read probabilities as direction, not precision."` |
| 含合成杠杆 | `"…synthetic Nx daily reset; real products add fees, financing and premium/discount gaps."` |
| replay 覆盖锚点 < 10 | `"Only N anchors cover every non-frozen series…"` |
| 起点缓冲已低于 `floor` | `"Buffer is already below the floor (…); shock_to_floor values are 0 by construction."`（replay：`prob_floor_before_first_exit` 恒为 1，无信息量） |
| 固定提示 | 维持比例上调假设、样本内选择、强平与成交为收盘近似 |

---

## 七、估值：情景 DCF、反向 DCF 与锚点对照（valuation.py）

> 三个子命令都是纯标准库、只读用户给的本地 JSON、不联网。**反向 DCF 是首选入口**：把一个价格翻译成它隐含的增长、年数或利润率（Rappaport / Mauboussin 的预期投资法），不出公允价。正向 DCF 只出用户定义的条件情景；锚点对照把共识、具名机构目标价与自建模型逐行并列，不取平均。

### 输入协议（公司 JSON，dcf / reverse 共用）

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` / `currency` / `as_of` | str | 仅回显；`currency` 决定 per-share 单位 |
| `archetype` | str，可选 | 缺省 `operating`；`bank` / `insurance` 直接拒绝（FCFF 对资产负债表型业务口径错误） |
| `revenue` | float > 0 | 最近 12 个月或上一财年收入，金额单位由用户定（如百万） |
| `operating_margin` | float | 当前经营利润率（EBIT / 收入） |
| `tax_rate` | float 0–0.99 | 有效税率 |
| `cash` / `debt` / `other_claims` | float ≥ 0 | 现金及短投、有息负债（含租赁按用户口径）、少数股东权益等其他索取权 |
| `shares` | float > 0 | 摊薄股数，与金额同一量级（金额 ÷ 股数 = 每股） |
| `discount_rate` | float | 折现率（WACC），由用户给出 |
| `terminal_growth` | float | 永续增长率，缺省 0.025，必须 < 折现率 |
| `terminal_roic` | float，可选 | 终值期新增资本回报率；缺省 = 折现率（价值中性） |
| `roic` | float | 显性期增量资本回报率，决定再投资 = NOPAT × g ÷ ROIC；情景内可覆盖 |
| `risk_free` | float，可选 | 给了就检查永续增长率是否超过它 |
| `mid_year` | bool，可选 | 年中折现惯例，缺省 false |
| `tam` | float，可选 | 用户给的市场规模；末年收入占比 > 50% 时报警 |
| `trailing_growth` | float，可选 | 过去增速，仅回显，并作为 reverse 求年数 / 利润率时的默认持有增速 |
| `reference_price` | `{value, label, as_of}` | 现价、发行价等参考价；reverse 必填 |
| `sources` | dict | 字段 → 来源说明；`revenue`、`operating_margin`、`tax_rate`、`cash`、`debt`、`shares` 缺来源时报警 |
| `scenarios` | dict（dcf 必填） | 每项：`years`（1–60，缺省 10）、`growth_start`（或 `growth`）、`growth_end`（缺省 = start，线性渐变）、`margin_target`（缺省 = 当前，线性渐变到第 N 年）、可选覆盖 `roic` / `discount_rate` / `terminal_growth` / `terminal_roic` |
| `reverse` | dict，可选 | reverse 的持有假设：`years`、`margin`、`growth`、`roic`；命令行 `--years --margin --growth --roic` 优先 |

**锚点 JSON（anchors）**：`as_of`（必填）、`currency`、`reference_price{value,label}`、`consensus{source, as_of, mean, median, high, low, n_analysts, ratings}`（可为空对象，表示查询无覆盖）、`brokers[]{name, target, rating, date, horizon_months, evidence: primary|secondary|unknown, source, currency}`、`own_model{label, values{情景: 每股}, warnings[]}`；或用 `--dcf-result` 直接接 dcf 的输出 JSON（连同它的 warnings）。

### 公式口径（明文）

```
g_t   = growth_start + (growth_end − growth_start) × (t−1)/(N−1)        # N=1 时取 growth_start
m_t   = m_0 + (margin_target − m_0) × t/N
Rev_t = Rev_{t−1} × (1 + g_t)
NOPAT_t        = Rev_t × m_t × (1 − tax)
Reinvestment_t = NOPAT_t × g_t / ROIC
FCFF_t         = NOPAT_t − Reinvestment_t
PV_t  = FCFF_t / (1 + r)^(t − s)              # s = 0.5（mid_year）否则 0
TV_N  = Rev_N × (1 + g_T) × m_N × (1 − tax) × (1 − g_T / RONIC) / (r − g_T)
PV_TV = TV_N / (1 + r)^(N − s)
EV    = Σ PV_t + PV_TV
Equity = EV + cash − debt − other_claims ;  per_share = Equity / shares
```

RONIC 缺省等于 r 时 `TV_N = NOPAT_{N+1} / r`，永续增长不改变价值，终值不夹带第二段增长故事。

**reverse**：利润率在显性期内保持不变，三种求解：
- `growth`：持有年数与利润率，在 −30%～100% 年增速内扫描后二分求解；
- `years`：持有增速与利润率，找价值首次不低于参考价的最短年数（1–60）；
- `margin`：持有增速与年数，在 0～90% 内求解。

无解时报 `reachable=false` 并给出扫描范围内的价值区间，不外推、不编数。另输出参考价对应的 EV、EV/收入、EV/NOPAT，以及隐含增速在 5/10/15 年 × 折现率 ±2 个百分点下的网格。

**黄金 case（实现必须 ±0.01 对上）**：revenue=1000，margin=0.2，tax=0.25，cash=100，debt=50，shares=100，r=0.10，g_T=0，ROIC=0.2：
- 零增长任意年数 → EV=1500，Equity=1550，每股 15.5；
- 1 年、g=10% → FCFF₁=82.5，PV=75，PV_TV=1500，EV=1575，终值占比 0.9524。

### 输出 JSON 骨架

```json
{
  "model": "valuation.dcf",
  "scenarios": {
    "base": {
      "assumptions": {"years": 10, "growth_start": 0.08, "...": "..."},
      "bridge": {"pv_explicit_fcff": 0, "pv_terminal_value": 0, "enterprise_value": 0,
                 "plus_cash": 0, "minus_debt": 0, "minus_other_claims": 0, "equity_value": 0, "shares": 0},
      "per_share": 0, "terminal_value_share": 0.62, "per_share_vs_reference": 0.05, "rows": ["..."]
    }
  },
  "sensitivity": {"scenario": "base", "discount_rates": ["..."], "terminal_growths": ["..."], "per_share": [["..."]]},
  "limits": ["情景是给定假设下的条件推演，不是概率分布、目标价或预测", "..."],
  "warnings": ["..."],
  "units": {"money": "input_money_unit", "per_share": "USD_per_share", "rates": "fraction"}
}
```

三个子命令都输出 `display`：`warnings_md`（warnings 逐条，空为「- 无」）、`input_md`（项目 / 数值 / 来源；数据类字段缺来源写「未标来源」，折现率等假设类字段缺来源写「用户假设」）、`result_md`（固定表头，见 SKILL「valuation 输出格式」）、`notes_md`（按条件选出的标准说明句）、`lines`（每个结果一句带计算条件的人话，追问引用数字时原样使用）。展示字符串由脚本从未取整的数值格式化：比例为 1 位小数百分比，差距带正负号，每股 2 位小数，金额带千分位。

`reverse` 输出 `held`、`implied_at_price`、`implied_growth{growth, reachable, final_year_revenue, final_revenue_share_of_tam}`、`implied_growth_grid`、`implied_years`、`implied_margin`。`anchors` 输出 `consensus`、`brokers[]`（含 `vs_reference`、`age_days`、`evidence`）、`broker_span{n, low, high}`（只给区间，不给均值）、`own_model{values, model_warnings}`。

### 适用边界 + 已知失效场景

- **折现率是单一常数**：不随期限、资本结构变化；WACC 怎么来由用户负责，网格只看敏感度。
- **亏损公司**：当前利润率不为正时不反推增长，须用 `--margin` 给出假设的稳态利润率。
- **金融业**：银行、保险直接拒绝。
- **周期股**：用单一年份的利润率会高估或低估，先由用户给出周期中位的利润率。
- **ROIC 是最敏感的隐藏假设**：ROIC 低于折现率时增长毁灭价值，反推结论随之翻转。
- **卖方目标价与 DCF 时间口径不同**：前者通常是 12 个月后的价格，后者是当下的情景价值；锚点只并列，不互相校准。
- **共识为空 ≠ 无人覆盖**：只说明该数据源当时没有返回数据。
- **`reachable` 的含义**：扫描范围内存在数学解，不表示业务上能做到。

### warnings 文案模板

| 触发条件 | 文案 |
|---|---|
| 必需字段缺来源 | `"{收入、经营利润率…}没标来源，按你给的数直接用"` |
| 多个情景同一条警告 | 合并为一条：`"base、bull：…"` |
| 显性期 FCFF 现值为负 | `"{情景}：前 N 年再投入比赚的多，现金流是负的，价值全靠终值撑着"`（此时不再报终值占比） |
| 终值占 EV > 75% | `"{情景}：企业价值有 X% 来自终值，结果主要看终值那部分的假设"` |
| g_T > 无风险利率 / 未给时 > 4% | `"永续增长率 X 比无风险利率 Y 还高"` / `"…高于 4%，长期看整体经济一般长不了这么快"` |
| ROIC < 折现率且增长 > 0 | `"新投入的回报 X 低于折现率 Y，这种情况下增长越快反而越不值钱"` |
| RONIC ≠ 折现率 | `"终值期新投入的回报设成了 X，不等于折现率，终值里多算了一块增长价值"` |
| 末年收入 / TAM > 50% | `"到第 N 年，收入要占到你给的市场规模的 X%"` |
| reverse 无解 | `"年增速从 … 试到 …，N 年内都算不到参考价，这组假设解释不了这个价格"` / `"…一直涨 60 年也算不到参考价"` |
| reverse 未指定持有年数 | `"你没给年数，按默认 10 年算"` |
| 共识为空 | `"共识是空的：只说明 {source} 在 {as_of} 没返回数据，不等于没人覆盖；不当成 0，也不拿参考价补"` |
| 共识人数 < 5 / 缺人数 | `"共识只有 N 位分析师，样本很小"` / `"共识没给分析师人数"` |
| 目标价非原文 / 超 90 天 / 缺日期 | `"{机构}的目标价来自二手报道，没核对研报原文"` / `"…是 N 天前的，之后的信息可能没算进去"` / `"{机构}没有发布日期"` |
| 具名目标价 < 3 家 | `"具名目标价只有 N 家，只是样本，代表不了全市场"` |
| 含自建模型 | `"自建模型的数完全取决于你的假设；券商目标价一般指 12 个月后，DCF 算的是现在，两者不是一个时间口径"` |
