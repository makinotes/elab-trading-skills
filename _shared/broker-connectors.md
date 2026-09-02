# 券商连接器共享契约

> 这是 `elab`、`elab-research`、`elab-trade` 共用的数据接入层，不是独立顶层 Skill。只在用户要求连接、切换、指定或比较富途/长桥/IBKR 数据，或下游 Skill 确实需要券商账户数据时读取。

## 一、职责和安全边界

- EdgeLab Skill 负责确认意图、选择数据源、字段归一、证据标签和中性分析；官方 MCP、CLI、OpenD 或 SDK 只负责传输数据。
- v0.4.0 的公共连接器是**只读版本**：允许查询资讯、行情、期权、账户、持仓、订单和成交；禁止调用下单、改单、撤单、DCA、交易指令生成等写工具。
- “我要用富途/长桥/IBKR 数据”表示用户要进入连接引导，**不等于已经授权下载安装软件、写 MCP 配置或授予交易权限**。先检查现状、展示最小权限方案，得到用户确认后才执行安装或配置。
- 凭证留在券商、OAuth 客户端、OpenD 或官方 CLI 的原生存储中。禁止把密码、Token、App Secret、完整账号写入 Skill、`~/.elab/`、研报、日志或 Git。
- 本地偏好文件只保存默认 provider 和更新时间。路径为 `~/.elab/broker-connectors.json`，用本目录 `scripts/broker_profile.py` 管理。

## 二、意图解析和选择优先级

先区分四种请求：

1. **连接/检查**：“我要接长桥”“检查 IBKR 能不能用” → 走本页安装与最小只读验证。
2. **本次指定**：“这次用富途查 NVDA” → 当前任务使用该 provider，不落默认偏好。
3. **以后默认**：“以后默认用长桥” → 连接验证成功后才写默认偏好。
4. **显式比较**：“比较富途和长桥的期权链” → 各自独立取数、并列展示；禁止先合并再隐藏来源。

实际取数按以下优先级：

1. 用户本轮明确指定的 provider。
2. 已保存且本轮验证可用的默认 provider。
3. 只有一个已连接并通过最小只读查询的 provider。
4. 多个可用但用户未指定 → 列出可用项让用户选，不能静默挑一家。
5. 都不可用 → 给连接方法；不要假装已取到券商数据，也不要静默换成另一券商。

用户要求当前未支持的账户直连（例如老虎证券账户）时，必须明确回答三件事：当前不支持该账户直连；本版已支持的账户连接器是富途、长桥、IBKR；公开社区博主研究与私有账户读取是两条不同路径，不能互相替代。可以提供用户授权导出的 CSV/Excel 只读导入方案，但不得假装实时连接。

公开免费源（如 Yahoo、Stooq）仍可按 `elab-research` 的降级规则使用，但必须明确告诉用户“指定券商源不可用，现展示的是哪个替代源”；用户说“只用某券商”时不得降级混源。

## 三、偏好与本地检查工具

按当前安装位置找到脚本：

| Runtime | 脚本路径 |
|---|---|
| Claude Code | `~/.claude/skills/_shared/scripts/broker_profile.py` |
| Codex | `~/.codex/skills/_shared/scripts/broker_profile.py` |
| CodeBuddy | `~/.codebuddy/skills/_shared/scripts/broker_profile.py` |
| WorkBuddy | `~/.workbuddy/skills/_shared/scripts/broker_profile.py` |
| 仓库运行 | `_shared/scripts/broker_profile.py` |

常用命令：

```bash
python3 <脚本路径> show --json
python3 <脚本路径> doctor --json
python3 <脚本路径> set-default longbridge
python3 <脚本路径> clear-default
```

`doctor` 只做本地可达性/安装迹象检查，不证明 OAuth、账户权限、实时行情权限已经成功。真正“已连接”必须再跑一条最小只读查询，并把成功时间、provider、数据类型记在当前会话中；不要把瞬时认证状态持久化成永久真值。

只有用户明确说“默认/以后都用”时才运行 `set-default`。一次性指定不得落盘。

## 四、Provider 接入

以下入口于 2026-09-02 按官方资料核验。命令报错或界面变化时先看对应官方链接和本机 `--help`，不要猜参数。

### A. 富途 Futu

**官方形态**：Futu Agent Skills + 本地 OpenD + `futu-api` Python SDK；目前没有富途官方 MCP。

**适合读取**：富途资讯/公告/研报搜索、报价、K 线、期权链、IV/Greeks、资金、持仓、订单和成交。实际实时性与期权数据范围取决于账户地区、行情订阅和 OpenAPI 权限。

**连接流程**：

1. 打开官方文档：<https://openapi.futunn.com/futu-api-doc/intro/ai.html>。
2. 用户确认后，从官方地址 `https://openapi.futunn.com/skills/opend-skills.zip` 下载到临时目录，先检查来源和内容，再把 `futuapi`、`install-futu-opend` 放入当前 runtime 的 skills 目录。不要使用 README 中失效或非官方 owner 的安装地址。
3. 让用户在 OpenD 界面手动登录并完成权限流程；不要索取交易密码，不要替用户解锁真实交易。
4. 用 `doctor` 检查 OpenD（默认 `127.0.0.1:11111`）与 SDK，再通过官方 `futuapi` 执行一条报价类只读查询。
5. 即使官方 Skill 暴露交易脚本，EdgeLab v0.4.0 也不得调用。

安装目标：Claude `~/.claude/skills/`、Codex `~/.codex/skills/`、CodeBuddy `~/.codebuddy/skills/`、WorkBuddy `~/.workbuddy/skills/`。安装属于外部写操作，必须先取得用户授权。

官方参考：<https://github.com/FutunnOpen/futu-agent-hub>、<https://openapi.futunn.com/futu-api-doc/intro/authority.html>。

### B. 长桥 Longbridge

**官方形态**：优先使用官方 `longbridge` CLI；也可使用 hosted MCP。不要再把 `pip install longbridge` 的 Python SDK 叫作 CLI。

**适合读取**：资讯、行情、基本面、期权、账户、持仓、订单和成交。CLI 的机器消费输出统一加 `--format json`。

CLI（所有能运行 shell 的 runtime）：

```bash
brew install --cask longbridge/tap/longbridge-terminal
longbridge auth login
longbridge quote AAPL.US --format json
```

macOS/Linux 的其它官方安装方式见 <https://open.longbridge.com/skill/install>。不要在一笔研究执行到一半时临时安装；连接应作为独立 setup 流程完成。

MCP：

```bash
# Codex
codex mcp add longbridge --url https://mcp.longbridge.com
codex mcp login longbridge

# Claude Code
claude mcp add --transport http --scope user longbridge https://mcp.longbridge.com
claude mcp login longbridge
```

CodeBuddy / WorkBuddy 使用各自的 `~/.codebuddy/mcp.json` 或 `~/.workbuddy/mcp.json`：

```json
{
  "mcpServers": {
    "longbridge": {
      "url": "https://mcp.longbridge.com"
    }
  }
}
```

配置后由 runtime 打开官方 OAuth 页面。中国大陆可按官方说明改用 `https://mcp.longbridge.cn`。只申请完成任务所需的读取权限；不得申请或调用 `trade.write`。

官方参考：<https://open.longbridge.com/docs/cli>、<https://open.longbridge.com/skill/install>。

### C. IBKR

**官方形态**：优先使用 IBKR 官方远程 MCP；普通用户无需为该路径常驻 TWS/IB Gateway，也无需把 API key 或密码交给 AI。

若宿主提供官方/受信的 IBKR 连接器或插件，可以优先使用该入口完成 OAuth；它是宿主的连接包装，不改变下游字段与只读边界。用户明确问“MCP 怎么接”时，即使宿主已有插件，也要同时说明官方远程 MCP 地址 `https://api.ibkr.com/v1/api/mcp-public`；Claude Code、CodeBuddy、WorkBuddy 等没有同一插件入口的宿主按下方 MCP 配置。

**适合读取**：现金、持仓、保证金、已实现/未实现盈亏、历史交易、期权链、风险暴露和投资组合结构。公开资料没有明确列出通用原始新闻工具，新闻维度不要假设 IBKR 一定可用。

```bash
# Codex
codex mcp add ibkr --url https://api.ibkr.com/v1/api/mcp-public
codex mcp login ibkr

# Claude Code
claude mcp add --transport http --scope user ibkr https://api.ibkr.com/v1/api/mcp-public
claude mcp login ibkr
```

CodeBuddy / WorkBuddy：

```json
{
  "mcpServers": {
    "ibkr": {
      "url": "https://api.ibkr.com/v1/api/mcp-public"
    }
  }
}
```

IBKR 官方 MCP 的交易流程是生成待用户在 IBKR 平台检查的 Instructions，不会自动变成订单；但 EdgeLab v0.4.0 仍只读取，不生成交易指令。需要批量历史报表时，可按 `elab-trade/references/broker-ingest.md` 使用 Flex Query 文件导入。

官方参考：<https://www.interactivebrokers.com/en/trading/ai-integrations.php>。

## 五、最小只读验收

连接配置完成后，按用户实际目标选择**一条**最小查询：

- 研究数据：一个已确认市场的常见标的报价，并检查 provider、时间戳、币种、实时/延迟状态。
- 期权数据：一个到期日的期权链，检查合约乘数、到期日、行权价、Call/Put、bid/ask、IV/Greeks 的缺失情况。
- 账户数据：账户列表或资金摘要；展示时使用用户可辨认的别名/尾号，默认隐藏完整账号。
- 交易记录：最近少量订单或成交；必须区分 order 与 fill，不把挂单当成交。

验收失败时给出失败层级：未安装、MCP 未配置、OAuth 未完成、OpenD 未运行、账户权限不足、行情订阅不足、限流/服务故障或字段不支持。修复后重跑同一条最小查询。

## 六、下游字段与输出契约

每条券商数据至少保留：

`provider | account_alias | symbol | market | asset_type | currency | as_of | realtime_status | source_tool`

期权补：

`underlying | expiry | strike | call_put | multiplier | bid | ask | last | iv | delta | gamma | theta | vega | open_interest | volume`

订单补：

`order_id | status | side | open_close | qty | filled_qty | order_type | limit_price | tif | created_at | updated_at`

成交补：

`fill_id | order_id | side | open_close | qty | price | fee | executed_at`

规则：

- provider 原始字段可保留，但标准字段不得凭空补值；缺失写 `null`/`[缺失]` 并说明影响。
- `as_of` 必须带时区；不能把上轮数据当当前实时数据。
- 多 provider 比较先分别标准化，再按相同合约/市场/时点对齐；时间、权限或延迟不同就标不可直接比较。
- 对外报告默认移除完整账户号、内部 order/fill ID 和绝对资金规模；用户明确需要个人核对时才展示必要字段。

## 七、路由边界

- 公开富途/老虎博主主页、发言和媒体归档 → `elab-futu-research`，不需要也不得借机登录券商账户。
- 标的/板块的资讯、行情和期权研究 → `elab-research`，按本页选择 provider。
- 用户自己的账户、持仓、订单、成交和交割单复盘 → `elab-trade`。
- “该不该买卖/下什么单” → `elab-diagnosis` 梳理决策；连接器不得把它改写成交易执行授权。
