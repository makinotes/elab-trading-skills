# 本地存档工具输入

从当前加载的 `elab-save/SKILL.md` 定位同目录的 `scripts/session_store.py`。工具需 Python 3.9+ 及 POSIX 的目录描述符、no-follow 文件操作；其他系统缺少这些能力时不会降级成不安全写入。只传已经脱敏、已经按共享契约核对来源的内容；不要把原始凭证写进临时 JSON 再指望工具删除。

```bash
python3 "<Skill目录>/scripts/session_store.py" save \
  --state-root "<状态根>" --slug "research-notes" \
  --status resolved --input "<已脱敏JSON文件>"
```

`--input -` 从标准输入读取同一 JSON，适合不保留中间文件的宿主。不要把用户文字直接拼成 shell 代码；使用宿主的结构化文件工具或安全引用的 stdin。回执给出新档路径、状态与读回校验结果；回执不代表同步、发布或真实性验证。

状态根先按共享契约解析为绝对路径，其父目录须已存在；工具只新建该根及其 `sessions/<项目>`，不替用户创建范围外的祖先目录。`--slug` 使用规范化后的项目名：小写字母、数字及单个分隔连字符。中文标题保留在存档文件名中。

输入字段：

| 字段 | 内容 |
|---|---|
| `title` | 非空中文或其他语言标题；工具处理文件名，不作为命令执行 |
| `source_skill` | 本次信息来自的 Skill 或“对话” |
| `next_skill` | 可省略、空或实际 Skill 标识，如 `elab-research`；具体下一步说明放正文，不自动执行 |
| `data_classification` | `public` / `member` / `private` / `unknown`；不代替逐项来源 |
| `sources` | 非空来源列表，每项仅含唯一 `id`、合法 `classification`、非凭证 `reference` |
| `body` | 含现有四个章节的 Markdown；逐项保留来源标签与 `[来源 id]` 关联 |
| `previous_snapshot` | 可选；同一项目下已有存档的文件名，用于记录接续关系，不改旧档 |
| `status` | 通常省略，以命令参数为准；若提供，必须与 `--status` 一致 |

仅演示输入结构的虚构材料：

```json
{
  "title": "阶段观察记录",
  "source_skill": "对话",
  "next_skill": "",
  "data_classification": "public",
  "sources": [
    {"id": "demo", "classification": "public", "reference": "虚构流程演示"}
  ],
  "body": "## 关键判断\n- [本人判断] [来源 demo] 本次观察先结束，尚不足以确认原假设。\n\n## 已排除的方向\n- 无。\n\n## 待回填假设\n- [AI推测] [来源 demo] 原假设仍未经验证，结项不代表成立。\n\n## 下一步\n- 本次不继续推进。\n"
}
```

工具拒绝未知字段、冲突状态、无效来源引用、路径越界和可识别的明显凭证内容；不会自动更改来源权限、把 AI 判断改成用户判断或把未知事实改为已验证。错误消息不复述疑似凭证。普通文字仍需由调用方核对，规则扫描不能识别所有隐匿秘密。
