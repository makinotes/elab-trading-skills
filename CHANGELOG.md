# CHANGELOG

EdgeLab elab-skills 版本变更记录。**改任何 skill 都要：① bump 该 skill `SKILL.md` frontmatter 的 `version` + `last_updated` ② 在这里加一条**。

## 版本约定（semver-ish，按改动大小）

- **patch**（`0.0.X`）：文案 / bugfix / 合规措辞 / 小补充，不改行为
- **minor**（`0.X.0`）：新增能力 / 模式 / reference 分册
- **major**（`X.0.0`）：破坏性改动 / 结构重构（会影响已有用法）

## 当前版本

| skill | version |
|---|---|
| elab | 0.1.13 |
| elab-trade | 0.3.10 |
| elab-research | 0.4.5 |
| elab-diagnosis | 0.2.10 |
| elab-benchmark | 0.2.6 |
| elab-deconstruct | 0.2.5 |
| elab-save | 0.1.3 |
| elab-restore | 0.1.1 |
| elab-report | 0.1.2 |

---

## 2026-07-02（晚）· 测评整改

30+6 题四层测评（路由 pass³ / 行为 / 多轮施压 / 盲评）后修 2 处：

- **elab** 0.1.13 — 路由器加"红线味请求绝不拒"死规则（能不能买/该不该/稳赚 → 一律转 diagnosis 去梳，路由器绝不"边界外/拒答"）；开场白模板（前一版）
- **elab-diagnosis** 0.2.10 — 守线理由锚定"方向是你的决策权"，禁用"我预测不了"（多轮施压下会被撬）

> 测评结论：行为层（930/anti-fabrication/术语/降级/隐私门）全过，多轮施压 5/5 守住；唯一系统缺陷是路由层"梳不堵"没贯彻（已修）。方法论见 `eval/README.md`。

## 2026-07-02

CHANGELOG 建立（此前版本为基线，未逐版回溯）。本日主要变更：

- **elab** 0.1.12 — 加开场白模板（讲清价值、去 AI 味、修 save/restore/report 名粘连）；入口凸显会员自研数据；公理摘要标"策略中立"
- **elab-diagnosis** 0.2.9 — 6 交易公理**策略中立化**（公理 2/3/5 剥掉方向性/卖方特定战术）；加高风险触发词换挡（具体合约+当下方向→切纯方法层）；合规措辞脱敏
- **elab-trade** 0.3.10 — 交割单复盘加量化底座（胜率/盈亏比/EV/分布）+ 结论接 6 公理；playbook 加想法区 + 晋级进度可视化；FIFO roll 孤儿腿禁静默丢弃；研报→立案 handoff；初始化补 mkdir 守卫
- **elab-research** 0.4.5 — 加板块研究（拥挤度 5 维框架）+ 多 agent 辩论模式（真独立子 agent）；默认取数栈（Yahoo/长桥/OpenBB/finnhub/stooq）+ 凭据纪律；无 token 降级标缺口；历史分布陈述脱敏
- **elab-benchmark** 0.2.6 — 例子去策略偏向；案例引用脱敏；沉淀收口
- **elab-deconstruct** 0.2.5 — 沉淀收口；自包含声明改诚实
- **elab-save / restore / report** — 沉淀收口三档路由；elab-save 首次主动引导（第一天不空手）

> 上述均经 4 路对抗审查（第一性/合规/交易/产品）+ 复核整改后定稿。

---

## 模板（复制到最上面用）

```
## YYYY-MM-DD
- **<skill>** <新版本> — <一句话改了啥（patch/minor/major）>
```
