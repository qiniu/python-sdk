# Qiniu Python SDK Sandbox 与 E2B Python SDK 差异说明

本文用于对照当前 `qiniu-python-sdk` sandbox 模块与 E2B Python SDK 的能力边界，帮助评估 API 设计、测试覆盖、示例配置和后端依赖差异。

## 对比基准

| 项目 | 版本或位置 | 说明 |
| --- | --- | --- |
| Qiniu Python SDK | 当前分支 `sandbox` 的工作区实现 | 以 `qiniu.services.sandbox` 和顶层 `qiniu.Sandbox` 导出为基准 |
| E2B Python SDK | 本地 E2B Python SDK 源码 | 以 `e2b.Sandbox`, `e2b.AsyncSandbox`, `e2b.Template`, `e2b.Volume` 等导出为基准 |
| Qiniu Sandbox 后端 | sandbox OpenAPI spec、envd proto 与当前 `.env` 实测环境 | Qiniu 控制面、envd、Kodo resource 和 injection rules 是 Qiniu 特有产品能力 |

## 总体定位

Qiniu sandbox 模块目前是 `qiniu-python-sdk` 中新增的一组同步 API，面向 Qiniu Sandbox 控制面和 envd，覆盖 sandbox 生命周期、命令、文件、Git、模板、资源挂载、注入规则、配置加载和 examples。

E2B Python SDK 是独立的现代 Python SDK，提供 sync/async 双栈、丰富类型导出、Template/Volume/Snapshot/MCP/PTY/watch 等完整产品面。两者使用场景接近，但鉴权模型、后端控制面、运行时依赖、类型系统和部分产品能力并不相同。

## 对齐原则

本轮 Qiniu Python sandbox API 的目标是尽量贴近 E2B Python SDK 的常用函数签名和对象组织，同时保留 `qiniu-python-sdk` 的兼容约束和 Qiniu 产品语义。

- E2B Python SDK 的常用入口尽量保留同名或近似签名，例如 `Sandbox.create(...)`, `Sandbox.connect(...)`, `Sandbox.list(...)`, `sandbox.files`, `sandbox.commands`, `sandbox.pty`, `sandbox.git`, `Template.from_image(...)`。
- Python 侧同时提供 snake_case 与 camelCase 别名，便于对齐 Python 习惯和已有 Qiniu/JS SDK 使用方式。
- Qiniu 后端已支持的能力，在 SDK 层实现真实请求，例如 lifecycle、commands、filesystem、Git、template API、Kodo resources、injection rules。
- Qiniu 特有能力继续显式保留，例如 Qiniu AK/SK 签名、Kodo resource、Git repository resource 和 injection rules。
- 后端或当前实现没有等价能力的部分不伪装为可用，例如 AsyncSandbox、Volume、snapshot wrapper、template build helper 的完整 E2B 形态。

## 主要差异概览

| 领域 | Qiniu Python SDK sandbox | E2B Python SDK | 差异影响 |
| --- | --- | --- | --- |
| 包定位 | `qiniu` 包内新增 `qiniu.services.sandbox` 模块 | 独立 `e2b` 包 | Qiniu 需要兼容现有 SDK 导出和依赖策略 |
| Python 兼容 | `setup.py` 仍声明 Python 2.7/3.4-3.7 兼容 | 现代 Python, 使用 `typing`, `typing_extensions`, `httpx` 等 | Qiniu sandbox 实现避免 dataclass、async/await 入口和较新的语法依赖 |
| HTTP 依赖 | 复用 `requests` / `requests.Session` | 使用 `httpx` sync/async client 和 generated API client | 请求封装、超时、异常类型和 async 支持不同 |
| 同步/异步 | 仅同步 API | 同时提供 `Sandbox` 与 `AsyncSandbox`, `Template` 与 `AsyncTemplate`, `Volume` 与 `AsyncVolume` | Qiniu 暂不提供 async 等价入口 |
| 鉴权 | `QINIU_SANDBOX_API_KEY`, `QINIU_SANDBOX_ACCESS_TOKEN`, Qiniu AK/SK `Mac` | `E2B_API_KEY` 与 `ConnectionConfig` | Qiniu 资源挂载和 injection rules 需要 Qiniu AK/SK 签名 |
| 控制面 endpoint | `QINIU_SANDBOX_API_URL`, `QINIU_SANDBOX_ENDPOINT`, `E2B_API_URL` 或默认 Qiniu endpoint | E2B cloud endpoint/domain config | endpoint、header、token 名称和默认值不同 |
| 顶层导出 | `Sandbox`, `SandboxClient`, `Template`, `KodoResource`, `GitRepositoryResource`, `FileType`, `FilesystemEventType`, `PtySize`, `WatchHandle` | `Sandbox`, `AsyncSandbox`, `Template`, `AsyncTemplate`, `Volume`, typed models/errors | Qiniu 当前导出更轻，类型模型更少；`Async*` 与 `Volume` 暂无等价产品面 |
| 类型系统 | 手写 Python 对象和 dict payload | 大量 typed model、paginator、exception、filesystem/git/network 类型 | Qiniu 用户更多接触原始 dict；E2B 类型提示更完整 |

## Sandbox 生命周期

| 能力 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| 创建 sandbox | 支持 `Sandbox.create(template=None, timeout=None, metadata=None, envs=None, secure=True, allow_internet_access=True, mcp=None, network=None, lifecycle=None, resources=None, injections=None, **opts)` | 支持同类签名, 另有 `volume_mounts` | Qiniu 使用 `templateID`, `envVars`, `resources`, `injections` 等控制面字段 |
| 默认 template | 默认使用 Qiniu `DEFAULT_TEMPLATE` | 默认 `base`, MCP 场景可切换到 `mcp-gateway` | Qiniu 不自动改写为 MCP template |
| 连接 sandbox | 支持类方法 `Sandbox.connect(id, ...)` 和实例 `sandbox.connect(...)` | 支持类方法和实例方法 | Qiniu 连接后会刷新 envd token 信息 |
| 列表分页 | 支持 `Sandbox.list(...).next_items()` 和 `nextItems` | 支持 `SandboxPaginator` / `AsyncSandboxPaginator` | Qiniu paginator 较轻量, 返回 `Sandbox` 对象列表 |
| kill | 支持 | 支持 | Qiniu 使用控制面 DELETE |
| set_timeout | 支持 `set_timeout` / `setTimeout` | 支持 | 单位均按秒表达 |
| pause/resume | 支持 `pause`, `betaPause`, `resume` | 支持 pause, 以及 lifecycle/auto-resume 相关能力 | Qiniu `resume` 会更新当前对象信息 |
| refresh | 支持 `refresh` 调用 Qiniu `refreshes` API | E2B 无完全同名核心实例方法 | Qiniu 特有生命周期补充 |
| update_network | 支持 `update_network` / `updateNetwork` | 支持 network update | 请求结构依赖各自控制面 |
| get_info/get_metrics/get_logs | 支持 | E2B 支持 get_info/get_metrics, logs 更多出现在 template/build 等上下文 | Qiniu 暴露 sandbox logs wrapper |
| is_running | 暂无同名方法 | 支持 `is_running()` 通过 envd health 判断 | Qiniu 当前提供 `wait_for_ready()` 轮询 envd health |
| signed file URL | 支持 `download_url`, `upload_url` 和 envd token 签名 | 支持同类签名 URL helper | 签名字段与默认 user 处理保持 Qiniu 实现 |

## Snapshot 与 MCP

| 能力 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| create_snapshot/list_snapshots | 暂无 `Sandbox` 实例 wrapper | 支持 `create_snapshot()` 和 `list_snapshots()` | Qiniu Python 当前没有暴露 snapshot paginator |
| MCP create option | `Sandbox.create(..., mcp=...)` 可透传到控制面 | `mcp` 会影响 template 选择并启动 MCP gateway command | Qiniu SDK 不负责自动启动 MCP gateway |
| get_mcp_url | 支持按 50005 端口生成 URL | 支持 | 依赖 sandbox domain |
| get_mcp_token | 返回控制面下发的 `trafficAccessToken` | E2B 会维护 MCP token, 并在 MCP gateway 启动后使用 | Qiniu 当前不读取 `/etc/mcp-gateway/.token`, 也不启动 gateway |

## Commands 与 PTY

| 能力 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| run/start | 支持 `commands.run(...)` 和 `commands.start(...)` | 支持 | Qiniu 使用 envd Connect JSON envelope 调用 `/process.Process/Start` |
| background command | `run(..., background=True)` 返回 `CommandHandle` | 支持 `CommandHandle` | Qiniu 普通 `start` 当前仍会聚合 stream 事件；`commands.connect` 和 PTY create/connect 使用流式 envelope 解析 |
| stdout/stderr | 返回聚合后的 `CommandResult.stdout/stderr`, 支持 `on_stdout`/`on_stderr` | 支持输出 handler、stream/handle 等更完整形态 | Qiniu callback 是聚合事件时同步触发 |
| stdin | 支持 `send_stdin` / `sendStdin`, `close_stdin` / `closeStdin` | 支持 | 均依赖 envd process API |
| kill | 支持按 pid 发送 SIGKILL | 支持 | Qiniu `kill` 返回 bool, 404 时返回 `False` |
| 非 0 退出 | 默认不抛错, 传 `throw_on_error=True` 才抛 `CommandExitError` | E2B command handle 默认错误语义更细 | 迁移代码时要注意默认异常行为 |
| command connect | 支持 `commands.connect(pid)` | E2B 支持连接/管理运行中的 command | Qiniu 使用 envd `/process.Process/Connect` |
| PTY | 支持 `sandbox.pty.create/connect/send_stdin/resize/kill` | 支持 `sandbox.pty` | Qiniu 使用 api-spec 中的 PTY Start/Update/SendInput/Connect 能力；当前实测 envd 可创建 PTY, 但 PTY input 返回 501 |

## Filesystem

| 能力 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| read | 支持 `read(path, format="text")`, `read_text`, `format="bytes"` | 支持多种读取形态和类型提示 | Qiniu 返回 `str` 或 `bytes`, 类型模型较轻 |
| write 单文件 | 支持 string/bytes, 默认 multipart, 可选 `use_octet_stream=True` | 支持更丰富数据类型和写入信息 | Qiniu 为兼容当前 envd 默认走 multipart |
| write 多文件 | 支持 `write_files` / `writeFiles`, 内部复用单文件 write | 支持 `write_files` | Qiniu 当前是逐文件写入 |
| stat/list/exists/mkdir/remove/rename | 支持 `get_info/stat`, `list`, `exists`, `make_dir/mkdir`, `remove`, `rename` | 支持同类能力 | 返回结构均会归一化为轻量 dict |
| watch_dir | 支持非流式 watcher: `watch_dir`, `WatchHandle.get_new_events()`, `WatchHandle.stop()` | 支持 `watch_dir` 与 watch handle | Qiniu 使用 api-spec 中的 `CreateWatcher/GetWatcherEvents/RemoveWatcher` |
| FileType/EntryInfo 类型 | 导出轻量 `FileType`, `FilesystemEventType`, `FilesystemEvent`, `WatchHandle` | E2B 导出 `FileType`, `EntryInfo`, `WriteInfo` | Qiniu 目前使用字符串常量和轻量对象, 尚无完整 typed model |

## Git

| 能力 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| clone/init/status/add/commit | 支持 | 支持 | Qiniu 通过 `commands.run("git ...")` 封装 |
| configure_user | 支持 | 支持类似 config helper | Qiniu 使用 repo path + name/email 签名 |
| pull/push | 支持基础 remote/branch 参数 | 支持并处理更多 auth/upstream 错误 | Qiniu 暂无 typed git exception |
| branch/remote/reset/restore | 支持 remote_add/remote_get/branches/create_branch/checkout_branch/delete_branch/reset/restore | E2B Git 模块更完整 | Qiniu 通过 `git` 命令 wrapper 实现 |
| structured status | 返回 command stdout | E2B 导出 `GitStatus`, `GitBranches`, `GitFileStatus` | Qiniu helper 尚未解析 porcelain 输出 |
| git auth helper | 支持 `dangerously_authenticate(username, password, host="github.com", protocol="https")` 和 `dangerouslyAuthenticate` | E2B 使用 Git credential helper, 另有 auth/upstream 异常和辅助逻辑 | Qiniu 已对齐 credential helper 认证入口；暂未补 typed `GitAuthException`/`GitUpstreamException` |

## Template

| 能力 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| Template builder | 支持 `from_image`, `from_template`, `add_step`, `run_cmd/run`, `copy`, `set_env`, `set_start_cmd`, `set_ready_cmd`, `to_dict`, `to_json` | 提供更完整的 `Template` / `AsyncTemplate` builder 和 build workflow | Qiniu builder 是轻量配置生成器 |
| build API | 通过 `SandboxClient.create_template`, `create_template_v2`, `rebuild_template`, `wait_for_build` 等 client 方法调用 | `Template` 对象本身承载 build、logs、tags 等工作流 | Qiniu 的 template 生命周期更偏 client wrapper |
| Dockerfile/devcontainer/context upload | 暂无完整 helper | E2B 支持更完整模板构建上下文能力 | Qiniu 当前只表达基础 steps |
| ReadyCmd helpers | `set_ready_cmd` 接受命令值 | E2B 导出 `wait_for_file`, `wait_for_port`, `wait_for_process`, `wait_for_timeout`, `wait_for_url` | Qiniu 未提供 typed ReadyCmd helper |
| Tags/build logs/status | client wrapper 支持 tags、build status/logs | E2B Template API 更集中 | Qiniu 示例覆盖了模板 list/detail/build/status/logs/tags/delete |

## Volume 与资源挂载

| 能力 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| Volume API | 暂无 `Volume` / `AsyncVolume` | 支持完整 persistent Volume 产品 | Qiniu 后端当前使用不同的资源挂载模型 |
| volume_mounts | `Sandbox.create` 不接受 E2B `volume_mounts` 语义 | 支持 mount path 到 Volume/name 的映射 | Qiniu 使用 `resources` 透传资源 |
| Git repository resource | 支持 `GitRepositoryResource(url, mount_path, authorization_token=None, repository_type="github_repository")` | 不适用同名模型 | Qiniu 特有 resource 能力 |
| Kodo resource | 支持 `KodoResource(bucket, mount_path, prefix=None, read_only=None)` | 不适用 | Qiniu 特有能力, 触发 Qiniu AK/SK 签名 |
| injection rules | 支持 list/create/get/update/delete | E2B 无同类 API | Qiniu 特有能力, 使用 Qiniu AK/SK 签名 |

## 配置与示例

Qiniu Python SDK 的 sandbox 配置集中在 `.env` 和 `qiniu.services.sandbox.config`:

- `QINIU_SANDBOX_API_KEY`: sandbox 控制面 API key。
- `QINIU_SANDBOX_ENDPOINT` 或 `QINIU_SANDBOX_API_URL`: sandbox 控制面 endpoint。
- `QINIU_SANDBOX_ACCESS_TOKEN`: 部分 template rebuild 等 access token 场景使用。
- `QINIU_SANDBOX_ACCESS_KEY` / `QINIU_SANDBOX_SECRET_KEY`: Kodo resource 和 injection rules 等 Qiniu 签名 API 使用。
- `QINIU_SANDBOX_TEMPLATE`: examples 默认 template。
- Kodo/Git/injection 示例所需的 bucket、prefix、repository、token 等配置由对应 example 自行判断；缺少时示例会跳过该分支, 不要求额外手动配置测试开关。

E2B Python SDK 主要围绕 `E2B_API_KEY` 和 `ConnectionConfig` 组织连接配置；Volume、Template、Sandbox 使用各自的 connection config 和 typed options。

## 错误与后端依赖

| 项目 | Qiniu 当前状态 | E2B Python SDK 状态 | 说明 |
| --- | --- | --- | --- |
| 基础错误 | `SandboxError`, `TemplateBuildError`, `CommandExitError` | `SandboxException`, `TimeoutException`, `NotFoundException`, `FileNotFoundException`, `GitAuthException`, `GitUpstreamException`, `TemplateException`, `VolumeException` 等 | Qiniu 当前错误类型较少 |
| HTTP 错误 | 根据 response status 和 message 生成 `SandboxError` | generated client 和 `httpx` 异常映射更细 | Qiniu 目前更多保留原始 response/data |
| envd 依赖 | commands/filesystem/pty 依赖 envd Connect RPC 和 signed file URL | 同样依赖 envd, 并有更多版本检查与 fallback | Qiniu Python 当前版本门控较少；测试和示例按 404/501 等后端能力分支跳过 |
| 后端产品能力 | Kodo resource、injection rules、refresh/logs 是 Qiniu 特有 | Volume、snapshot、async、PTY、watch 是 E2B 完整产品面的一部分 | 差异来自产品边界, 不是单纯 SDK 命名差异 |

## 测试与示例覆盖

Qiniu 当前 sandbox 覆盖包括:

- `tests/cases/test_services/test_sandbox/`: 覆盖 client、config、envd、example config、sandbox integration 分支；新增覆盖 commands callbacks/connect、PTY、filesystem `write_files`/watcher、Git helper。
- `examples/sandbox_create.py`: 创建 sandbox 并执行基本命令。
- `examples/sandbox_lifecycle.py`: lifecycle、timeout、pause/resume 等生命周期能力。
- `examples/sandbox_connect.py`: list/connect/metrics/logs 等连接和观测能力。
- `examples/sandbox_git.py`: sandbox 内 Git 操作；配置 `GIT_REPO_URL` 和 Git 凭据时自动执行远端 clone/commit/push, 缺少配置时跳过远端分支。
- `examples/sandbox_runtime.py`: commands callbacks、filesystem `write_files`/watcher、PTY runtime 交互。
- `examples/sandbox_templates.py`: template list/detail/build/status/logs/tags/delete。
- `examples/sandbox_injection_rules.py`: injection rules CRUD, 缺少 Qiniu AK/SK 或测试配置时自动跳过。
- `examples/sandbox_resources.py`: Git repository resource 与 Kodo resource, 缺少对应配置时自动跳过相关分支。

当前实测结果:

- `python -m pytest tests/cases/test_services/test_sandbox -q`: `26 passed, 1 skipped`。唯一 skipped 是 PTY input, 原因是当前 envd 对 PTY `SendInput` 返回 501。
- 新增远端 Git push 集成测试 `test_git_remote_push_when_credentials_are_configured`, 在 `.env` 包含 `GIT_REPO_URL` 和 Git 凭据时自动运行；实测已向 `miclle/sandbox-git-demo.git` push `python-sdk-it-*` 分支。
- `python -m flake8 --show-source --max-line-length=160 ./qiniu`: 通过。
- `python3 -m compileall -q qiniu tests examples`: 通过。使用系统 Python 3.11 执行, 因为旧 mock server 代码使用 Python 3.10+ `match` 语法。
- `git diff --check`: 通过。
- 所有 sandbox 示例均已逐个运行并退出 0: `sandbox_create.py`, `sandbox_lifecycle.py`, `sandbox_connect.py`, `sandbox_git.py`, `sandbox_templates.py`, `sandbox_injection_rules.py`, `sandbox_resources.py`, `sandbox_runtime.py`。
- `examples/sandbox_git.py` 已在 `GIT_REPO_URL=https://github.com/miclle/sandbox-git-demo.git` 配置下实际 push `python-sdk-example-*` 分支；远端验证可见 `python-sdk-it-*` 和 `python-sdk-example-*` 分支。
- `sandbox_runtime.py` 实测 commands callbacks、filesystem `write_files`、watcher 成功；PTY create 成功但 PTY input 因 envd 501 被示例跳过。
- `sandbox_resources.py` 实测 Git repository resource 与 Kodo resource 均成功创建、访问并清理 sandbox；示例中仍保留 404/408/409/429/5xx 的可选资源跳过逻辑, 避免远端资源服务临时不可用时阻塞其他分支。

全仓库测试也已尝试按 CI 方式执行。启动 `tests/mock_server/main.py --port 9000` 并设置 `MOCK_SERVER_ADDRESS=http://127.0.0.1:9000` 后, mock-server 相关 HTTP 测试可运行；但当前本地 `.env` 的普通 Kodo/CDN 测试配置不完整或不匹配, 例如 `QINIU_TEST_BUCKET` 与临时映射的 AK/SK 返回 `no such bucket`, 因此 `python -m pytest ./test_qiniu.py tests -q` 仍有大量非 sandbox 旧测试失败。这些失败不来自 sandbox 模块改动。

E2B Python SDK 本身有更大范围的 sync/async、Volume、Template、filesystem watch、PTY 等测试和示例。本文仅基于本地源码接口对照, 没有运行 E2B Python SDK 的测试套件。

## 后续建议

1. 如果 Qiniu Python SDK 需要更贴近 E2B Python SDK, 优先评估是否新增 `AsyncSandbox`。这是 Python 用户迁移时最明显的接口差异。
2. Commands 后续可继续补普通 command `start` 的真正长连接 streaming handle 和更完整的 output handler 行为。
3. Filesystem 后续可继续补完整 typed `EntryInfo/WriteInfo`、流式 `WatchDir` 和更高效的批量上传。
4. Git 后续可把 `status`/`branches` 解析为结构化 `GitStatus`/`GitBranches`/`GitFileStatus`, 并补 typed auth/upstream exception。
5. Snapshot、MCP gateway、Volume 是否对齐 E2B, 应以 Qiniu 后端产品是否正式开放为准；没有后端能力时继续保持显式缺省。
6. Template 如需继续追齐 E2B, 可优先补 ReadyCmd helpers、Dockerfile/devcontainer/context upload 和对象化 build workflow。
