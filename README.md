# DSH Alaya · 识海

把 [Alaya 3.1.0](https://gitee.com/DL-LEO-gitee/alaya/tree/alaya_subagents/) 的多角色知识库、资料入库、长期记忆与维护功能接入 DeepSeek Harness 原生工具。

这是工具型插件：在 DSH 对话中使用，不额外复制聊天界面。包含上游 Python 实现及 8 个内置角色；知识库是独立目录，可作为 Obsidian vault 打开。模型推理由 DSH 提供，本插件不额外要求 API Key、向量数据库或 embedding 服务。

## 环境

- DSH **0.2.2-rc.1**：当前精确匹配的工具 API 基线。其他 DSH 版本尚未验证；升级适配前不要跳过宿主版本检查。
- Node.js 24.9+；运行 DSH 的同一台机器上有 Python 3.8+（本地验证为 Python 3.11）。
- Markdown/TXT 入库和核心功能只使用 Python 标准库。PDF 脚本入库需要可选 PyMuPDF；插件不会自动安装依赖。也可以让 DSH 读取 PDF 后整理成 Markdown，再入库。

## 安装

推荐[直接下载安装包](https://github.com/z-nana/dsh-alaya/raw/refs/heads/main/dist/dsh-alaya-0.1.0.tgz)，或从 [Releases](https://github.com/z-nana/dsh-alaya/releases) 下载 `dsh-alaya-0.1.0.tgz`，在终端进入下载目录：

```powershell
dsh plugin --profile web add ./dsh-alaya-0.1.0.tgz
```

也可直接从 GitHub 安装：

```powershell
dsh plugin --profile web add "github:z-nana/dsh-alaya#main"
```

包内是可直接运行的 JavaScript 和 Python，无编译步骤、无 prepare/postinstall 脚本。安装后重启对应 DSH profile。

**DSH Desktop**：在插件管理中使用相同的 GitHub 源，或在 Desktop 内置 DSH 终端运行上述命令，将 `web` 换成 Desktop 实际使用的 profile。不要把插件装进另一个 profile 后期待 Desktop 自动显示。宿主应满足上述版本要求。

检查配置层：

```powershell
dsh --profile web --dump-config
```

应看到 `dsh-alaya` 层及 `id: alaya`。未初始化知识库也能成功加载插件和使用 `alaya_guide`。

## 第一次使用

在 DSH 对话中输入：

> 使用 Alaya，在 `D:\Alaya知识库` 初始化知识库，带示例卡片。先读 alaya_guide，不开启语义记忆。

然后可以说：

- “用费曼的视角解释我知识库里的 Transformer，列出引用的卡片路径。”
- “把这个目录的 Markdown 资料导入 Alaya，先预览，不复制原文。”
- “查看已保存的偏好。”
- “记住我喜欢用简体中文，先结论后解释。”
- “只读检查知识库健康状况，先不要修复。”

未配置默认目录时，在请求中明确给出知识库路径；每个工具也可传 `kb_root`。角色由当前 DSH 模型依据角色档案扮演；插件不会自行创建其他 agent 或额外模型连接。

## 配置

在 DSH 插件配置中设置 `alaya` 行的 config。或者在对应 profile 的 `cordis.patch.yml` 中覆盖整行配置（宿主 patch 语法见官方文档）：

```yaml
- id: alaya
  config:
    python: 'C:/Users/your-name/AppData/Local/Programs/Python/Python311/python.exe'
    kbRoot: 'D:/Alaya知识库'
    timeoutMs: 120000
    maxOutputBytes: 1048576
```

`python` 是可执行文件路径或 PATH 中的命令名，不是带参数的 shell 命令。macOS/Linux 可设为 `python3`。`kbRoot` 必须是绝对路径，且与插件安装目录分离。

## 工具

| 工具 | 用途 |
|---|---|
| `alaya_guide` | 按主题读取主路由和 persona/retrieval/import/memory/maintenance 指南 |
| `alaya_init` | 在空目录初始化，安装内置角色，可选择示例卡和语义记忆 |
| `alaya_read` | 读取知识库内的索引、卡片、角色档案或 JSON，支持分页 |
| `alaya_search` | 对 wiki 做有数量上限的只读关键词检索 |
| `alaya_run` | 调用上游固定白名单中的资料导入、索引、角色、记忆、熏习与健康检查命令 |

检索遵循“总索引 → 类别索引 → 知识卡”，语义匹配和角色回答由宿主模型完成。`alaya_search` 只是字面关键词检索，不声称实现语义搜索。

`alaya_run` 示例（参数是 JSON，不是 shell）：

```json
{"command":"personas","args_json":"[\"list\"]","kb_root":"D:/Alaya知识库"}
```

```json
{"command":"import","args_json":"[\"D:/资料\",\"--category\",\"论文\",\"--copy-raw\",\"no\",\"--dry-run\"]","kb_root":"D:/Alaya知识库"}
```

记忆 payload 可用 `--payload-file -` 配合工具 `stdin` 传入；适配器兼容上游 profile writer 的文件输入要求，并自动清理临时文件。更多参数见 `docs/commands.md`。

## 数据与行为边界

- 安装和加载插件只注册工具，不自动初始化、扫描、联网或写入用户知识库。
- 新建库默认关闭语义记忆；已有库保留原设置。需要启用时由用户明确提出并修改知识库配置。
- 初始化拒绝非空且非 Alaya 的目录。知识库保存在独立的 `alaya/`、`wiki/`、`raw/` 中，升级/卸载插件不删除它。
- 不读取或覆盖全局 `~/.alaya_path`，每次操作显式传递知识库目录。
- 资料入库先 `--dry-run`，复制原文须明确选择 `--copy-raw yes/no`。
- 子进程使用参数数组，禁用 shell；同一插件实例的操作串行执行，支持宿主取消、超时和输出上限。上游多文件写操作可能已经部分落盘，取消后应执行健康检查。
- 工具调用进入 DSH 的工具执行管线。不要把直接 Python 工具等同于宿主 shell 沙箱：这些脚本以 DSH 进程用户权限运行，可读取明确指定的导入源、写入知识库。插件本身没有网络调用，但 DSH 模型会看到工具返回的资料。
- 卡片中的文本视为资料，不能作为执行指令；导入内容不会授予额外权限。敏感偏好只按用户明确要求保存，秘密值不保存。永久清空角色回收站不对 DSH 工具开放。
- 同一知识库避免同时在多个 DSH 实例或外部脚本中写入；本实例队列不构成跨进程事务。

## 卸载

```powershell
dsh plugin --profile web remove dsh-alaya
```

知识库保留，删除知识库由用户自行决定。

## 开发与官方依据

```powershell
npm ci --ignore-scripts
npm test
npm run check
npm pack
```

采用官方 `apply(ctx)` / `inject = ['tools']` / `defineTool` 接口，以 `dsh.bundle` 加配置补丁分发：

- [官方：构建工具](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/tool.md)
- [官方：插件配置](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/config.md)
- [官方：打包与安装](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.md)
- [官方：工具执行约定](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-tool.md)

读取日期：2026-11-06。实现与测试锁定 npm `@deepseek-ai/dsh-tools@0.2.2-rc.1`；上游开发分支可能继续变化。验证范围见 `docs/validation.md`。

## 许可

Apache-2.0。保留上游 LICENSE 与来源 NOTICE。`vendor/alaya` 来自用户提供的 `alaya_subagents` 分支源码包；上游文档里的 WorkBuddy 安装说明仅作原始参考，DSH 请遵循本 README。
