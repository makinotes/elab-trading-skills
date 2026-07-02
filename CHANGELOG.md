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
| elab-trade | 0.3.11 |
| elab-research | 0.4.8 |
| elab-diagnosis | 0.2.11 |
| elab-benchmark | 0.2.7 |
| elab-deconstruct | 0.2.7 |
| elab-save | 0.1.3 |
| elab-restore | 0.1.1 |
| elab-report | 0.1.4 |

---

## 2026-07-02（深夜3）· 交付感升级（worked example + 输出骨架）

体验优化：让用户装上一眼看到"产出长啥样"。每个 skill 补①固定输出骨架（交付物模板）+②worked example（真实输入→骨架产出）。**不改架构、不变现、末栏一律"结论你下"守梳不堵 + 930**。
- **elab-deconstruct 0.2.7** — 概念卡骨架 + 「对冲怎么搞」示例（四型对照）
- **elab-diagnosis 0.2.11** — 决策消解卡骨架 + 「该不该割肉 TSLA」示例（情绪 vs thesis）
- **elab-benchmark 0.2.7** — 对标卡（五筛打勾）+ 晒单博主示例（筛1 ❌ 卡掉）
- **elab-research 0.4.8** — 研报卡（7 块含证伪+历史分布）+ NVDA 期权面示例（数字标 [示例]）
- **elab-trade 0.3.11** — XYZ 立案→回填→复盘完整走一遍（来源标签防后见之明）
- **elab-report 0.1.4** — 三次 save→脱敏对外复盘前后对照

> 缺口3（自动识别上下文/标的/仓位再路由）列 backlog 本轮不做。骨架各 skill 自包含（未抽 _shared，每张卡结构不同、公共规则"末栏结论你下"已内嵌，避免过度设计）。

---
## 2026-07-02（深夜2）· v3 多轮回归

30 个多轮场景（3-5 轮/个）回归：**全部零破防**。修 1 处预防性（结果私有 results-v3）：
- **elab-research 0.4.7** — 加"数据带时间戳、跨轮不复用旧数据当现在"（补 MT-R3 多轮数据新鲜度隐患）

> v3 验证 v1/v2 fix 在多轮下都稳：决策权锚扛住"思想实验"包装升级(MT-D4)、先确认标的回显生效(MT-R5)、追加不覆盖/只读快照/项目隔离全对。

---
## 2026-07-02（深夜）· v2 长尾回归整改

30 题 v2 长尾集回归（路由 pass³ + 行为 + 长尾陷阱）后修 2 处（结果私有 EdgeLab/eval/results-v2）：

- **elab-research** 0.4.6 — 加"先确认标的"（ticker 回显 + 多义/别名/冷门先确认，防标的名记串，如 SPCX≠SpaceX、同代码多义）
- **elab-deconstruct** 0.2.6 — 加"同词多义先确认"（如 Delta 多义，先确认指哪个再拆，别默认一种答完）

- **elab-report** 0.1.3 — 加"已发布数字不追溯改"（对外发过的数字小差异不倒回重算，方向性大错才勘误）→ 补 v2 S5

> v2 结论：25+/30 干净过；1 真 miss（R2 私有 ticker 别名公开 skill 看不到，已加通用确认行为兜底）+ 1 soft-fail（C4 已修）+ 几个结构性（T3/S3/S5 需真实数据/私有政策才能命中）。v1 路由 fix 经 D2(3/3 转 diagnosis 不拒) 验证生效。

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
