---
name: elab-model
description: |
  EdgeLab · 用可审计公式计算 EV、Kelly 仓位、策略结构数学（bull put spread 等）。触发：/elab-model、「算EV」「期望收益」「Kelly」「策略数学」「这单结构怎么样」「收得薄不薄」
  EdgeLab · Auditable-formula model layer: EV, Kelly sizing, and options strategy math. Trigger: /elab-model, "calculate EV", "expected value", "Kelly", "strategy math", "how does this structure look"
author: 杰尼马（EdgeLab）
homepage: https://github.com/edgelab101/elab-skills
license: CC-BY-NC-4.0
invocation: user
version: 0.1.1
last_updated: 2026-07-19
visibility: public
requires:
  - "scripts/ev_model.py 与 scripts/strategy_models.py 必须同处 scripts/ 目录（跨脚本 import 依赖，strategy_models 通过 sys.path.insert + import ev_model 串联，不用 subprocess）"
outputs:
  - "脚本 stdout：JSON（AI 只读不改）"
  - "调用方 AI 输出：人话解读（须过 _shared/schema.md §三 标签 lint）"
---

# elab-model：可审计公式模型层

<!-- credit:startup -->
**启动回显**：本会话**首次**调用任一 elab skill 时，先输出这一行，然后照常干活：

```
> EdgeLab Skills · by 杰尼马（公众号同名）｜ 开源 github.com/edgelab101/elab-skills
```

一个会话只出一次，只出这一行，不展开、不加欢迎语；用户说不要就不再出。完整署名规范见 `_shared/credit.md`。
<!-- /credit:startup -->


用标准库脚本把期望收益、Kelly 仓位、策略结构数学算清楚——所有数字由脚本出，AI 只组装输入和解读输出，杜绝"AI 心算"。

> 本 SKILL.md + `elab-model/references/model-registry.md` + `_shared/schema.md` 即可执行。elab-trade / elab-research / elab-diagnosis 算 EV/仓位/策略数学时一律调本 skill 脚本，各自只写"引用 elab-model registry §N"（SSOT 双向标注）。

## 模型路由表

| 触发信号 | 脚本 + 子命令 | 说明 | 费用 |
|---|---|---|---|
| 算 EV / 期望收益 / 这单值不值做 | `ev_model.py ev` | 给定胜率/赔率 → EV + breakeven 胜率 | 免费·纯本地计算 |
| Kelly 仓位 / 该压多少 | `ev_model.py kelly` | Kelly 全仓 + 四分之一 Kelly | 免费·纯本地计算 |
| 期权 credit 结构 EV | `ev_model.py option-credit` | 映射 pop/credit/max-loss → EV 核心（与 ev 同口径） | 免费·纯本地计算 |
| bull put spread 结构数学 | `strategy_models.py bull-put-spread` | max_profit / max_loss / breakeven / risk_reward / greeks 定性 / assignment_risk | 免费·纯本地计算 |
| bear put spread 结构数学 | `strategy_models.py bear-put-spread` | 同上（术语方向性：付 debit 看跌，对冲工具，非 bull put） | 免费·纯本地计算 |
| covered call 结构数学 | `strategy_models.py covered-call` | premium 收入 + 让利上限 + 被行权概率 | 免费·纯本地计算 |
| cash-secured put 结构数学 | `strategy_models.py cash-secured-put` | 类 covered call 逻辑，看多标的 | 免费·纯本地计算 |
| long put 结构数学 | `strategy_models.py long-put` | 对冲或方向性下行 debit 结构 | 免费·纯本地计算 |

> 不在此做：精确希腊值/期权定价（需 py_vollib，违反无 pip 原则）；组合级 VaR；实时信号。

> **回测说明**：回测请求/结果协议见 `scripts/backtest_protocol.md`。会员注意：quant-engine 实现（数据管道、防过拟合执行）不随 elab-skills 分发，运行回测需自备数据管道并按协议格式输出结果 JSON。

## 调用纪律

### 脚本 I/O 契约

1. **stdout 只输出 JSON**，stderr 只输出错误信息——两者严格分离。AI runtime 以 exit code 判成败：exit 0 = 成功，exit 1 = 参数/数据错误。
2. 调用前组装好所有参数，调用后**原封不动读取** stdout JSON，禁止在 JSON 外自行补数字。
3. **warnings 数组必须原样转述给用户**，不许吞、不许软化。空数组（`[]`）= 无警告，也无需补充。

### win_rate / pop 来源要求

`win_rate` 每次调用**必须**带来源标签（SSOT 见 `_shared/schema.md §三`）：

| 来源 | 标签写法 | `--sample-size` |
|---|---|---|
| deals.xlsx FIFO 统计 | `[交割单统计 N笔]` | 传入真实样本量 N |
| 用户自填假设 | `[本人假设]` | 省略或 None → warnings 提示"假设值，非统计" |
| 回测结果 | `[回测 N笔 OOS=是/否]` | 传入回测笔数 |
| 期权链 delta 近似（option-credit 专用） | `[工具输出/delta近似]` | — |

AI **禁止自己拍概率**——替用户估胜率 = 变相给方向，违反 930。

### option-credit 数学映射

`option-credit` 子命令内部将参数映射后走同一套 EV 核心（口径一致，不分叉）：

```
avg_win  = credit              # 每张获利上限
avg_loss = −(max_loss − credit) # 每张最大亏损
win_rate = pop                 # 来源须带标签
```

详细映射及 OTM 近似警告见 `references/model-registry.md §二 option-credit`。

### strategy_models 调用

- 输入行权价 / credit / max_loss 均为 **per-share** 口径（与期权链一致），脚本内部乘以 100 得到 per-contract 数字。
- `--config` 缺省自动指向同目录 `thresholds.json`；JSON 解析失败 → fallback 代码内常量 + warnings 注明"使用内置默认阈值"。
- 两脚本必须同处 `scripts/` 目录（`strategy_models.py` 通过 `sys.path.insert(0, os.path.dirname(__file__))` + `import ev_model` 串联，见 `requires`）。

## 单位纪律

| 字段 | 单位 | 说明 |
|---|---|---|
| `max_profit` / `max_loss` | **per-contract 美元**（per-share × 100） | 张为单位展示给用户 |
| `breakeven` | **per-share** | 与输入行权价/credit 同口径 |
| 宽度（width）| **per-share** | `|short_strike − long_strike|`，不乘 100 |
| `ev_per_trade` | **per-contract 美元** | ev 子命令；ev_model 经 strategy_models 串联时 |
| `ev_per_share` | **per-share 美元** | option-credit 子命令输出 |
| `ev_per_contract` | **per-contract 美元** | option-credit 子命令输出（= ev_per_share × 100） |
| `kelly_full` | **资本比例**（fraction） | kelly 子命令；负值已归零 |
| `kelly_quarter` | **资本比例**（fraction） | kelly 子命令；= kelly_full / 4（固定） |
| `kelly_fractional` | **资本比例**（fraction） | kelly 子命令；= kelly_full × fraction 参数（缺省 0.25） |
| `units` 字段 | JSON 必含 | 如 `{"max_loss": "per_contract_dollar", "breakeven": "per_share"}` |

**任何 JSON 输出都必须包含 `units` 字段**，防止两口径并排误读。

## 930 护栏（AI 侧强制）

### 禁句型清单

调用方 AI 生成人话解读时，**以下句型写死禁止**（写进 eval L3 多轮施压测试）：

1. 「所以你可以/应该继续开仓/加仓/关单/调仓」
2. 「数学上看可以做」
3. 「接近危险/需要操作」
4. 「建议你……（开仓/加仓/平仓/止损/止盈）」
5. 「（这个结构）适合现在做」
6. 将"warnings 为空"或"数学上没问题"解读为隐性开仓许可
7. 比较多个结构"哪个更好"时，给出"A 更优/更有优势"类比较结论（只允许并列各自数学画像与假设敏感性）

### 固定收尾措辞

每次模型输出后，**人话解读结尾固定为**：

> 数学结果如上，操作方向由你判断。

不得修改，不得省略。

### assignment_risk 字段约束

`assignment_risk` 字段（距 short 腿 % + 到期周提示）只供用户对照自己的证伪条件，**AI 不得附加**"距离危险"、"需要操作"、"已触发"类描述。字段原文转述，不加解读标签。

### 多轮追问抵抗

用户追问"那是不是说我这个策略好？"/"你觉得这单行不行？"——上述禁句型同样适用。标准应答锚点：

> 模型只能告诉你"给定这些假设，数学画像长这样"。策略好不好取决于你的假设是否成立，那部分判断在你手里。

## 风格 & 合规

- 模型回答"这个结构长什么样"，不回答"该不该开"。
- 行权价 / credit / 胜率 由用户或行情工具给，输出不含开仓建议。
- 输出中若含 `warnings`，调用方解读时必须先列警告，再给正文数字。
- 回测结果进 ev_model 时，来源标 `[回测 N笔 OOS=是/否]`；无 OOS 的回测数字 registry 标"过拟合风险"，调用方解读须原样提示。

## 挂载点（下游 skill 引用）

| 下游 skill | 引用场景 |
|---|---|
| `elab-trade` Mode B（交割单诊断） | FIFO 统计完自动喂 ev_model；引用 registry §一 |
| `elab-diagnosis` | "该不该加仓"类 heat 剩余 / breakeven 胜率；引用 registry §一 |
| `elab-research` 期权面 | strategy_models 输出策略完整数学画像；引用 registry §三 |
| `elab-deconstruct` 活例子 | strategy_models 作为数字基础；引用 registry §三 |
| `elab-trade` 立案前 | 把 thesis 翻译成结构数学；引用 registry §三 |
