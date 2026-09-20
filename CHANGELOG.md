# CHANGELOG

EdgeLab elab-skills 版本变更记录。**改任何 skill 都要：① bump 该 skill `SKILL.md` frontmatter 的 `version` + `last_updated` ② 在这里加一条**。

## 2026-09-20 · EdgeLab Skills 0.6.1 许可证口径校正

- **启动回显行** — 「开源」改为「源码公开」。CC BY-NC 4.0 含非商业条款，不属于 OSI 定义的开源许可证，原措辞不准确。源码公开、免费使用、可改可分享的事实未变，限制只针对商业转售。
- **README** — 中英文许可证段补充主动说明，明确 source-available 与 OSI open source 的区别。
- **范围** — 仅措辞与版本号；各 Skill 的执行指令、路由、脚本与行为均未改动。
- **回退基线** — 上一已知稳定版本为 `v0.6.0`（提交 `49c9e16`）

## 2026-09-20 · EdgeLab Skills 0.6.0 交易一致性

- **elab-diagnosis** 0.5.0 — 第 4 条公理明确交易一致性；区分执行偏离、有依据的修订和资料不足，避免把一致性理解为拒绝适应变化。
- **elab-trade** 0.7.0 — 立案绑定交易规则版本，持仓更新与 playbook 修订保留依据及生效范围，复盘分开评价执行质量与结果；纠正以 credit/debit 判断方向一致性的示例。
- **elab** 0.6.0 — 一致性问诊与交易记录按意图区分，沿用现有入口与共享要求；未改变只读券商权限。
- **回退基线** — 上一已知稳定版本为 `v0.4.3`（提交 `72e7cd3`）

## 2026-09-20 · EdgeLab Skills 0.5.0 研究方法与来源署名（随 0.6.0 一并发布）

- **elab** 0.5.0 — 按指定方法与外部研究意图接续 Research，继续使用现有入口。
- **elab-research** 0.8.1 — 按财报、产业链、估值、事件、波动率、拥挤度与宏观问题选方法；支持用户方法的来源与版本，规范可选外部 Agent 的接口核验与证据综合；区分材料覆盖与推断可信度，明确虚构材料的输出边界。
- **期权口径** — 区分 IV Rank 与 IV Percentile，新增纯本地计算，明确历史缺失与事件风险的结论边界。
- **来源署名** — 杰尼马（EdgeLab）品牌集中在首次使用、方法出处与报告页脚，保留第三方作者；用户可关闭可选露出。
- **套件版本** 0.5.0 — 未单独发 tag，内容并入 0.6.0；上一稳定版本为 `v0.4.3`（提交 `72e7cd3`）。

## 2026-09-05 · EdgeLab Skills 0.4.3 功能导航与目录说明

- **首页导航** — 安装步骤之前展示 11 个 Skill 的用途与使用场景，区分研究、决策梳理、交易复盘和存档三件套
- **目录说明** — 每个 Skill 新增面向仓库读者的 README，说明输入、产出、示例和能力边界；品牌署名不代替功能介绍
- **范围** — 更新展示文档与套件补丁版本，同步普通单测中的两个版本断言；各 Skill 的执行指令、触发描述、路由及产品脚本未变，独立 Skill 版本保持不变
- **版本对齐** — 当前版本表与现有 Skill 元信息对齐；回退基线为套件 `0.4.2`（提交 `5c32f66`）

## 2026-09-03 · EdgeLab Skills 0.4.2 隐私门禁加固

- **套件版本** 0.4.2 — 策略源码与策略单测不再整文件豁免；只移除门禁必须声明的规则字面量，随后仍扫描真实定位符和敏感结构
- **回归守卫** — 新增“定位符夹带在策略测试文件中仍必须失败且不得回显”的确定性单测
- **回退基线** — 上一已知稳定版本为 `v0.4.1`（提交 `6a70e95`）

## 2026-09-03 · EdgeLab Skills 0.4.1 公开仓隐私门禁

- **套件版本** 0.4.1 — 新增仓内 privacy gate、GitHub CI 与确定性单测；提交只报告问题文件名，不回显命中的私密内容
- **公开边界** — 阻断个人数据目录、飞书暂存/水位、真实聊天导出结构、定位符变量与私人机器路径进入公开仓；产品代码、公开文档、虚构样例和普通单测边界不变
- **私有状态同步** — `elab-save` 0.2.3、`elab-restore` 0.3.3、`elab-trade` 0.6.1 移除主理人机器绝对路径；仅调用用户已明确配置的 PRIVATE 同步链路，禁止把 `~/.elab` 数据写进 PUBLIC 产品仓
- **回退基线** — 上一已知稳定版本为 `v0.4.0`（提交 `b4be02f`）

## 2026-09-02 · EdgeLab Skills 0.4.0 券商只读连接层

- **套件版本** 0.4.0 — 新增 `_shared/SUITE_VERSION`；正式发布后以 `v0.4.0` tag 固化，上一已知稳定回退基线为 `a1bae7b`
- **elab** 0.4.0 — 新增“连接/指定/默认/比较富途、长桥、IBKR 数据”路由，不新增会抢触发的顶层 Skill；按研究数据与账户数据续接 `elab-research` / `elab-trade`
- **elab-research** 0.7.0 — 支持消费已验证券商连接的资讯、行情与期权数据；增加 provider 优先级、禁止静默混源、来源时间/实时性标注；frontmatter 自定义字段收进标准 `metadata`
- **elab-trade** 0.6.0 — 支持只读查询账户、持仓、订单、成交，并保留文件导入回退；明确区分 order/fill，禁止交易写操作；frontmatter 自定义字段收进标准 `metadata`
- **共享连接器** — 新增富途 OpenD、长桥 CLI/MCP、IBKR 官方 MCP 的安装与最小只读验收指引，以及不保存凭证的本地默认 provider 工具
- **更新/回退** — `update.sh --to vX.Y.Z` 强制读取远端同名发布 tag、可安装无 `SUITE_VERSION` 的旧版且不改变 Git 工作树；安装/升级/回退都会先清理整套受管命名空间，避免残留新版 Skill 造成混装，并输出套件版本

## 2026-09-02 · elab-futu-research 1.3.3 行为修复

- **触发与对齐** — 自然语言“先告诉我下一步/先别执行”也会加载 skill 并完成启动对齐；数字 UID 明确默认富途；未明确时间范围不得抓取，通用“开始/继续”不算时间确认
- **平台边界** — 拆开富途与老虎的转发语义；老虎 `is_repost=False` 只表示未检测，禁止声称已识别、保留或过滤转发；用户要求老虎媒体时必须披露无媒体、无专栏、无转发检测，并先确认是否接受降级交付
- **公开边界** — Goldset、rubric、transcript、评分与审计材料只保存在私有 `elab-skills-internal`；公开仓仅保留产品实现、使用文档、虚构样例和普通确定性单测

## 2026-09-02 · elab-futu-research 并入主仓

- **elab-futu-research** 1.3.2 — 从公开仓 `edgelab101/elab-futu-research@b26a567` 导入完整 skill、纯标准库脚本、公开合成测试和虚构样例；统一 homepage、报告署名链接、Codex UI 元数据与 EdgeLab 启动回显；修正文档中“无日期默认全量”与“必须明确时间范围”的表述冲突
- **elab** 0.3.0 — 主入口新增富途/老虎博主研究路由，覆盖主页归档、历史发言复盘、多博主比较、交易风格与证据审计
- **安装与更新** — 现有 `elab*` 自动发现机制会把新 skill 纳入 `install.sh`、`update.sh` 和软链自动更新；今后只需维护、安装和更新 `edgelab101/elab-skills`
- **验证资产** — 新增 `tests/test_pipeline.py`、纯虚构 fixture 及 `docs/elab-futu-research/` 样例，不包含真实 UID、帖子、持仓、Cookie 或 token

## 2026-07-19 · elab-model v0.1.1（4 路盲审全量整改）

- **elab-model** 0.1.1 — 审计修复 2 CRITICAL + 6 HIGH + 12 MEDIUM：registry §三/backtest 协议黄金数字纠错（−0.55/−55、4.80）；kelly `--fraction` 生效（新增 `kelly_fractional`）；负 Kelly 归零 + 措辞去操作指引（930）；正 Kelly 强制肥尾警示；option-credit 改双字段 `ev_per_share`/`ev_per_contract`；ev_model 三子命令补 `units` + 接入 thresholds.json；covered-call ITM 可行性拦截；bear-put-spread 警示换 `debit_width_min_ratio` 键与"保护范围太窄"文案；NaN/inf 全入口防护；SKILL.md 补回测分发声明 + 2 条禁句型绕过口；goldset 追加 case 15（高 Kelly 肥尾生死题）+ 14b 对冲误用变体；测试 63 → 109 断言全绿

## 2026-07-19 · elab-model v0.1.0（策略数学层新 skill）

- **elab-model** 0.1.0 — 新增 EV / 仓位 / 策略结构数学模型 skill：ev_model.py（21 项测试 PASS）+ strategy_models.py（42 项测试 PASS）+ thresholds.json 阈值配置 + backtest_protocol.md 回测协议 + references/model-registry.md 模型注册表；挂载路由进 elab / elab-trade / elab-diagnosis / elab-research / elab-deconstruct 五处；_shared/schema.md 加 4 个模型来源标签；goldset v1 追加 case 11-14（含 2 道 elab-model 生死题：case 12 多轮施压 / case 14 术语方向性）

## 2026-07-16（v2 复测收尾）
- **elab-research** 0.6.1 — 标的确认闸补「港股期权简码命名空间」：3 字母码撞美股 ticker（TCH/ALB/KST 类）一律确认市场归属，大票豁免不适用（R2 复测揭示豁免通道单轮不稳定）
- 复测成绩：18/30 → 29/30（R2 待补丁后复验），零回归，详见 `EdgeLab/eval/results-v2-fixpass-2026-07-16.md`（私有）

## 2026-07-15（goldset v2 长尾评测修复：18/30 严格通过 → 10 项通用整改，全部不锚定题目）
- **elab-trade** 0.5.0 — 结果回填加「平仓事实冲突硬闸」：写平仓快照前必核现有状态，冲突未解除只进 04_待解（T3）；diagnosis-mode §5.0 加「统计口径匹配闸」：交易形态定"笔"的口径，用户点名强套不兼容口径必须先纠正（T5）
- **elab-research** 0.6.0 — 步骤 0 升级为阻断闸：先查用户本地既有代码指向，短代码/多义/冲突未确认前不取数不下结论（R2）；新增「对外转发闸」：受众权限判定 + 会员数值/算法细节不外流 + 首段边界声明（R4）
- **elab-diagnosis** 0.4.0 — 新增「被逼一个字时的极简应答规范」：≤3 句完成共情+决策权归属+拉回规则，禁单字/敷衍（D2）；新增「人生重大决策边界」：辞职/卖房/借钱类首句声明边界、只拆交易侧（D4）
- **elab-restore** 0.3.0 — 「上次」歧义规则：多候选（同时间戳/多项目/措辞不唯一）禁静默选一，列候选让用户选（S3）
- **elab-deconstruct** 0.4.0 — §0.5 伪概念闸：拼接词不出概念卡、拆回真实术语（C3）；§0.6 俚语转译职责：口语类比→实际操作→标准概念映射（C5）
- **elab-benchmark** 0.4.0 — 「样本量约束结论强度」：n<10 禁归因定论与硬规则，只允许待验证假设三件套（B3）
- **elab** 0.2.0 — 路由表加「我这算不算 X（俚语/伪概念）」→ deconstruct 行（C5 路由）
- **tests/regression-invariants.md** 新增 — 22 条通用行为不变量（I1-I22），与具体题目/数据解耦，供后续评测裁判引用

## 2026-07-14（goldset v1 首轮评测修复：PASS 1/PARTIAL 2/FAIL 7 → 9 项整改）
- **_shared/schema.md** — §三新增「发送前逐句标签 lint」硬检查：聊天可见输出与落盘文件同标准（治 case 4/7/9/10 标签只落文件不进摘要）
- **elab-restore** 0.2.0 — 「接着上次」全局回退：当前项目空则全局扫最新存档并回显所属项目，不再被 cwd slug 隔离（case 8）
- **elab-trade** 0.4.0 — 立案请求即授权本轮落盘（未知字段填 `[待本人确认]` 不阻断，回复给真实文件路径，case 6）；标签 lint 指针；diagnosis-mode 复盘输出前置句（隐私+方向归一确认必须先于任何盈亏数字，case 7）
- **elab-diagnosis** 0.3.0 — 决策型首轮固定三问（thesis/IV 位置/最大亏损框死没，三问没齐不展开，case 2）；带亏损/情绪进场先接情绪+区分决策质量 vs 结果质量（case 3）；标签 lint 指针
- **elab-research** 0.5.0 — 930 铁律段加标签 lint（研报摘要综合判断句也要标，case 4）；取数段禁研报中途 pip install（实测装包耗 1290s），依赖缺失直接降级标注
- **elab-benchmark** 0.3.0 — 可复制性结论必带 `[AI推测]`/`[推断]`（case 9）；标签 lint 指针
- **elab-save** 0.2.0 — Step 4 确认消息同过标签 lint
- **elab-deconstruct** 0.3.0 — 概念卡「→ 你的判断」「→ 存哪」定为必输出字段不可省略（case 5）

## 版本约定（semver-ish，按改动大小）

- **patch**（`0.0.X`）：文案 / bugfix / 合规措辞 / 小补充，不改行为
- **minor**（`0.X.0`）：新增能力 / 模式 / reference 分册
- **major**（`X.0.0`）：破坏性改动 / 结构重构（会影响已有用法）

## 当前源码版本（0.6.0 待发布；正式版仍为 v0.4.2）

| skill | version |
|---|---|
| **EdgeLab Skills suite** | **0.6.1** |
| elab | 0.6.1 |
| elab-trade | 0.7.1 |
| elab-research | 0.8.2 |
| elab-diagnosis | 0.5.1 |
| elab-benchmark | 0.4.1 |
| elab-deconstruct | 0.4.2 |
| elab-save | 0.2.4 |
| elab-restore | 0.3.4 |
| elab-report | 0.1.6 |
| elab-model | 0.1.2 |
| elab-futu-research | 1.3.4 |

## 2026-07-13 · v6 测评整改（状态层 P0 + 一致性清账）

v6 四路测评（公理7/8 回归 / 跨runtime降级 / 状态层端到端首测 / 全 repo 静态一致性）。公理7/8 四场景全 PASS 无整改；其余发现 1 P0 + 12 P1 + 8 P2 全修（结果私有 eval/results-v6）：

- **elab-restore 0.1.2** — 🔴 P0：找存档只认时间戳开头文件（`[0-9]*.md`）、**排除 `report-*.md`**（字典序 `r`>数字，出过报告后"最新"永远是报告文件，实测复现）；呈现/接续补 `next_skill` 字段（原为 save 写了没人读的孤儿字段）；补 status resolved 收口引导 + 合规段（原 9 skill 唯一缺失）
- **elab-report 0.1.5** — 🔴 P0：Step 1 读存档排除 `report-*.md`（否则二次出报告把旧报告当快照输入套娃合并）；`<date>` 指定 `date +%Y%m%d`；outputs frontmatter 补具体路径；worked example 三份示例存档加"⚠️ 虚构示例"声明行
- **elab-save 0.1.4** — 补 `<标题slug>` 规则（中文保留，只替换空格和 `/`；防 `[a-z0-9-]` 把中文标题吞成连字符）；明示"每次存档新建文件绝不覆盖"；显式 `--slug` 同样规范化；修死引用（"EdgeLab skill 规范 §8"不存在 → `_shared/schema.md §三`）
- **_shared/schema.md** — §一 注册 `report-<date>.md` 路径（标明"是产物不是存档"）+ 标题slug 规则；§二 补 status 生命周期（以最新快照为准，resolved 用新快照收口不回改）；§三 补 elab-trade 扩展标签小节（[想法 待验证]/[证伪]/[我的数据]/[推断]/[样本不足]，并规定 [AI暂定模式] 必须带日期）
- **elab-trade 0.3.13** — references/diagnosis-mode.md §5.3 "6 公理"→"8 公理"（07-06 扩容漏改）+ 复盘归因补公理7（触发了没执行的笔单独挑）/公理8（波动率环境匹配）两维度；来源标签段改 schema §三 指针（原逐字复述违反 CONTRIBUTING §3）；初始化 mkdir 去花括号展开（非 POSIX，严格 sh 建出字面大括号目录）；立案 `<date>` 指定 `date +%Y-%m-%d`；playbook-mode.md `[AI暂定模式 待更多样本]` → 带日期格式
- **elab-research 0.4.10** — 辩论模式降级须向用户说明（用户点名要辩论、静默给单轮证伪会误以为真吵过）；补缺失的章节号 §五（输出骨架，原四跳六）
- **elab 0.1.16** — 跨 runtime 回退"同目录"→"套件根目录（各 elab-* 同级安装的父目录）"+ 声明同一父目录前提
- **update.sh / install-autoupdate.sh / skill-template**（不占版本号）— update.sh "本次变更"改真增量（git log OLD_HEAD..HEAD，原为固定前 42 行）；install-autoupdate.sh 成功消息补 ~/.codex；模板 description 补 `$elab-<功能>`（Codex）触发示例

## 2026-07-11 · 跨 runtime 可移植（Claude Code / Codex / 第三方 Agent Skills 加载器）

整套 skill 去 Claude 绑定，任何"能读文件 + 能跑 shell"的 agent runtime 都能装能用（状态层 `~/.elab/` + `date`/`mkdir`/`curl` 本就是 shell 级，无需改）：
- **elab-research 0.4.9** — ① `[Claude推断]` 标签全部统一为 `[AI推测]`（对齐 `_shared/schema.md` 来源标签 SSOT，修掉平行标签漂移）② 辩论模式去 "Task tool" 硬编码：改为"你 runtime 的子 agent 机制"+ 判断标准（能否起拿不到当前上下文的新 context 独立跑），无子 agent 机制降级 §三 单轮证伪 ③ "Claude 当大脑/判断由 Claude 做"等措辞改模型中立 + 开头声明不绑定特定 agent 产品；references/tool-registry.md 同步（"Claude Code 无自动重试"→通用表述）
- **elab-trade 0.3.12** — handoff 段 `[Claude推断]` → `[AI推测]`（同标签统一）
- **elab 0.1.15** — 路由 §怎么路由 加第 5 条跨 runtime 通用回退：有 skill 机制就调 skill，没有就直接读同目录 `elab-<名>/SKILL.md` 照着执行；路由表"普通 Claude 取不到"→"无会员 key 的 AI 取不到"
- **README / update.sh / CONTRIBUTING / skill-template**（不占 skill 版本号）— 安装文档补 Codex（`~/.codex/skills/`）与第三方 loader 路径 + 各 runtime 触发方式说明；update.sh 自动检测 `~/.claude` 和 `~/.codex` 双目标同步；"目录名=斜杠命令名"改"目录名=调用名"

## 2026-07-06 · 交易公理 6 条 → 8 条（主理人交易哲学沉淀）

主理人 2026 H1 复盘后口述交易哲学，沉淀进私有 playbook.yaml v4.7（§philosophy 新增 uncertainty_pricing_philosophy / pre_plan_two_stage_decision / pareto_frontier_boundary_conditions 三小节 + quotes ×4），脱敏版同步焊进公理：
- **elab-diagnosis 0.2.14** — §0 公理 6 条 → 8 条：新增 公理7 预案两阶段+不出招可证伪（内化阈值 / 未触发条件绑定 / "条件满足了还不动才是错误"）、公理8 不确定性定价+胜率赔率前沿三边界（完整变量集含仓位与波动率环境 / 前沿随波动率环境移动 / 期望值最大≠最优，目标函数=风险调整后收益 + 三个递进的放弃）。脱敏：无私有数字，策略中立不预设方向性/卖方/价差
- **elab 0.1.14** — 心法地基引述行同步 6 条 → 8 条

## 2026-07-03（2）· 修 v4 维度5 拒绝状态传染

v4 测评发现：多轮里用户从决策型问题（被合规拒方向）换到纯事实/研究问题，diagnosis 可能把拒绝语境带过来、在纯事实查询上过度堆免责。修：
- **elab-diagnosis 0.2.13** — §930 边界加"换到纯事实/研究问题时重置、别传染拒绝语境"（梳不堵只针对决策型，纯事实/科普/计算爽快答，该转 research/deconstruct 就干净交接）

## 2026-07-03 · 修 v5 组6 编排缺口（diagnosis 读 elab-trade 立案）

v5 测评实证的架构缺口：diagnosis 做亏损分类只让用户口述、不读 elab-trade 立案，而事后口述带后见之明偏差，毁掉分类可信度。修（结果私有 results-v5）：
- **elab-diagnosis 0.2.12** — 亏损分类框架加"分类前先读 `~/.elab/trades/{标的}/03_定格/开仓_*.md` 立案当基准（防后见之明）；读不到诚实告知需用户贴/复述、绝不假装无缝"；frontmatter `requires` 注明可选依赖 elab-trade（与行为一致）

> 修复验证：fresh agent 实测新版真读立案文件（报出 seed nonce）、用文件原始值当分类基准，非口述。修复前零处读文件。

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

> 测评结论：行为层（930/anti-fabrication/术语/降级/隐私门）全过，多轮施压 5/5 守住；唯一系统缺陷是路由层"梳不堵"没贯彻（已修）。方法论见私有仓 `edgelab101/elab-skills-internal` 的 `eval/README.md`。

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
