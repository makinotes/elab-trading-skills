# 工具登记表（elab-research 可扩展的核心）

> 编排时从这挑工具。**表是活的**——网上出新工具，按"怎么加"评估后加进来即可被编排。
> ⚠️ 包名/接口名会变，以官方文档为准；具体函数签名不确定就标 [需核对]，别编。

## 一、登记表（每个工具：装/调 + 输入输出 + 状态）

### 数据聚合
- **OpenBB**（`pip install openbb`）🟢 —— `from openbb import obb`，取行情/财报/新闻/**期权链**。输入 ticker，输出结构化数据。一站式，优先用
- **yfinance**（`pip install yfinance`）🟢 —— 轻量取行情/历史/期权链；免费但偶尔不稳，做兜底

### 券商 / 自己数据
- **futu-api**（富途，需 FutuOpenD 常驻）🟢 —— 接富途行情/会员自己持仓
- **longport**（长桥，需 API 凭据）🟢 —— 接长桥行情/持仓

### 财报 / SEC
- **edgartools**（`pip install edgartools`）🟢 —— 拉解析 10-K/10-Q/8-K。输入 ticker，输出财报文本/财务数据 → 喂 `工作流模板/用Claude分析财报关键段`

### 期权计算
- **py_vollib**（`pip install py_vollib`）🟢 —— 逐条算 IV、希腊字母、BS 定价。输入期权参数（标的价/行权/到期/无风险利率/期权价），输出 IV/Delta/Gamma/theta/Vega
- **py_vollib_vectorized**（`pip install py_vollib_vectorized`，**独立包，接口不同**）🟢 —— 批量/向量化算 IV 希腊字母，整列数据时用。`pip install py_vollib` 不会带它
- **QuantLib-Python**（`pip install QuantLib`）🟡 —— 工业级衍生品定价，重、API 陡，复杂结构才用

### 回测
- **vectorbt**（`pip install vectorbt`）🟡 —— 向量化回测验想法；学习曲线陡，验策略假设时用

### 自研（EdgeLab 权益内 · 会员 token gated）
- **invest 雷达站 / 恐慌指数 / 回测框架** 🔵 —— 取拥挤度/恐慌/信号。**调用约定**（不是 MCP，直接调现成 API）：
  1. 读会员 token：`cat ~/.elab/token`（安装脚本写好的，自铸 token）
  2. 调数据 API：`curl -H "Authorization: Bearer <token>" <数据API端点>`（雷达/恐慌指数数据接口，端点部署时填；**token 是自铸密钥、独立一层，和任何网站登录无关**）
  3. **优雅降级**：没 `~/.elab/token` 或返回 401（非会员/退费）→ 不报错崩，告诉用户"自研数据要会员 token，进星球解锁；这部分先用公开工具（OpenBB 等）替代"，继续跑能跑的

### ❌ 别接（玩具行，警示）
- **FinGPT / FinRobot / TradingAgents 等 LLM trade agent** 🔴 —— demo/回测过拟合，实盘没用、整合不值。这正是"复合开源 trade agent"最该避的坑

## 二、怎么加一个工具 / action（扩展机制）

**Step 1 过玩具筛**（4 关，不过进 🔴 警示行）：
- □ 能本地跑/接 Python？ □ 维护活跃（近半年有更新）？ □ license 可商用集成？ □ 实盘/机构真在用 vs 只是回测曲线好看？

**Step 2 写登记条目**（按类别加到 §一）：
```
- **<名字>**（`pip install <pkg>`）🟢/🟡 —— <一句话：怎么调、吃什么输入、吐什么输出、衔接谁>
```

**Step 3 标接口衔接**：吃什么输入、吐什么输出、和现有工具怎么接（如"edgartools 出财报文本 → 工作流模板财报 prompt"）。

**Step 4 标合规**：输出是纯数据/指标（OK）还是带方向建议（要剥掉方向再用）。

## 三、怎么保持更新（诚实版：结构化流程，非魔法自动）

skill 是静态指令，"更新"靠流程：
- **触发**：① 遇到新工具即时评估 ② 定期（如每季）派一个调研 agent 扫"近期靠谱的开源投研/期权工具"
- **评估**：用 §二 Step 1 四关筛（上次调研已把 LLM trade agent 全筛进 🔴）
- **落地**：过筛的按 §二 Step 2-4 加进表，改主 SKILL 的 `version` + `last_updated`
- 调研 agent prompt 可复用"查开源 trade/投研工具 + 真能用 vs 玩具分级"那套
