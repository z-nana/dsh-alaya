# 验证记录

日期：2026-11-06。系统：Windows。Node.js 24.11.1，Python 3.11，DSH 0.2.2-rc.1。

## 已实际通过

- `npm test`：12 项测试通过。
- 真实 Cordis 4.1.0 + DSH ToolsService 0.2.2-rc.1 加载插件、读取指南、注册 5 个工具，卸载后 5 个工具全部注销。
- 独立临时目录中的中文和空格路径初始化，内置角色读取；再次初始化保留已有记忆开关。
- 示例知识卡读取与分页、关键词检索。
- 相对路径越界、程序目录作为知识库、CLI 知识库目录覆盖（包括 argparse 缩写）均被拒绝。
- Markdown 入库预览不创建目标类别；确认提交后能生成卡片并重建索引。
- 用户偏好通过 stdin 写入、查看、删除；临时 payload 自动清理。
- 健康检查与链接检查返回诊断；无效脚本参数返回失败状态，不执行 shell。
- 输出上限、Python 不存在、预先取消、卸载取消、串行队列失败恢复。
- `npm run check`：JavaScript 语法与所有上游 Python 脚本编译检查通过。
- 官方 CLI 在隔离的 DSH_HOME 中执行 `dsh plugin --profile alaya-test add ./dsh-alaya-0.1.0.tgz` 成功。
- `dsh --profile alaya-test --dump-config` 显示 dsh-alaya 层、alaya 行和插件配置。
- `dsh --profile alaya-test --dump-config-schema` 成功导入插件，生成配置 schema。
- `npm pack` 内容检查：仅发布运行源码、指南、示例与许可证，不包含 node_modules、测试数据或 Python 字节码。

## 范围与限制

- 未在用户的 DSH Desktop 中进行人工对话验收；模型驱动的角色回答质量依赖宿主模型。
- 未调用模型 API，没有消耗用户的模型额度。
- 未在本机测试 PyMuPDF 的可选 PDF 入库路径。
- 本机未验证 Linux/macOS；仓库附带 Linux/Windows 的 GitHub Actions 验证工作流，远端结果以 Actions 页面为准。
- 其他 DSH 版本尚未验证，当前通过 engines.dsh 和 peerDependencies 锁定 0.2.2-rc.1。
- Alaya 自身的多文件事务、记忆衰减与角色推理算法沿用上游，本次测试不等于对上游全部逻辑作形式验证。

源码来源是用户提供的 alaya_subagents ZIP，而非本机无法直接访问的 Gitee master。保留 Apache-2.0 许可证及来源说明。
