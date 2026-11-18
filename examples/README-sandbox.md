# Sandbox 示例

SDK 已对齐 [qiniu/api-specs](https://github.com/qiniu/api-specs/tree/6cb3b18a89584b0cd05f94c2d0a85aa7926c9f05/sandbox) 的公共 API。
从项目根目录复制 `.env.example` 为 `.env`，填写 `QINIU_SANDBOX_API_KEY`，按需设置区域端点和模板，然后运行：

```bash
python examples/sandbox_create.py
python examples/sandbox_lifecycle.py
python examples/sandbox_snapshots.py
python examples/sandbox_template_lifecycle.py
python examples/sandbox_runtime_configuration.py
python examples/sandbox_injection_rules.py
```

示例会创建资源并在结束时清理。保存的注入规则还需要 AK/SK；直接设置运行时 HTTP 注入可使用 API key。

## 沙箱列表分页

`client.list_sandboxes(limit=100, nextToken=cursor)` 返回
`{'items': [...], 'nextToken': ...}`，游标来自 `X-Next-Token` 响应头，
`nextToken` 为空表示没有下一页。完整遍历也可以让 `Sandbox.list()` 分页器自动传递游标：

```python
from qiniu.services.sandbox import Sandbox

pages = Sandbox.list(client=client, limit=100, metadata={'app': 'example'})
while pages.has_next:
    for sandbox in pages.next_items():
        print(sandbox.sandbox_id)
```

元数据字典会按服务端过滤协议编码，`+`、`&`、`=`、`%` 和中文均保留原值。
直接传入 `metadata` 字符串时，调用方应先分别编码每个键和值，再将这些项编码为查询字符串。

Envd 文件和进程请求不自动跟随 HTTP 重定向；收到 30x 时抛出 `SandboxError`，
避免把访问 token 或签名 URL 带给跳转目标。

## PTY 实时输出与断连

`sandbox.pty.create(on_data=callback)` 和
`sandbox.pty.connect(pid, on_data=callback)` 返回进程句柄。回调接收原始 `bytes`。
首帧含有 PTY 输出时，`create()` 或 `connect()` 会在调用线程执行回调，回调抛错时
会关闭流并直接抛出异常。后续输出由后台读流线程调用回调，无需先调用 `wait()`。
回调应快速返回，可把数据放入队列交给应用处理。

`handle.wait()` 等待进程结束，返回带字符串 `stdout` 的 `CommandResult`，
并抛出后台读流或回调异常。未提供 `on_data` 时，首次调用 `wait()` 会启动后台读流，
传给该次 `wait()` 的 `on_stdout` 和 `on_stderr` 仍在调用线程执行。

`handle.disconnect()` 只关闭本地连接，不终止远端 PTY，可重复调用。
断连后的 `wait()` 返回已收到的结果；未收到退出事件时 `exit_code` 保持 `-1`。
断连会冻结已处理的输出并释放等待者，包括另一个线程正在同步 `wait()` 的情况；
后台任务负责清理连接，之后重复 `wait()` 返回同一份冻结结果。
部分操作系统的读操作或关闭操作会延迟到既有读取时限才退出；`timeout=None`
的语义不变，不保证读线程立即结束。输出回调在状态锁中确认调度后，在锁外执行。
断连不会等待已经调度的回调，它们可能在 `disconnect()` 返回后才开始或结束；
断连后不再调度后续回调，晚到的输出或异常也不再修改冻结结果。
之后可用 `sandbox.pty.connect(handle.pid, on_data=callback)` 重新连接。
需要终止进程时显式调用 `handle.kill()`；任务结束时清理沙箱。

## 私有 Git 克隆

`clone()` 支持 `username` 和 `password`，与 `pull()` / `push()` 一样使用临时
askpass 文件和进程环境，不把凭据写入远程 URL 或持久 credential store：

```python
import os

result = sandbox.git.clone(
    'https://github.com/owner/private.git', '/home/user/private',
    username=os.environ['GIT_USERNAME'], password=os.environ['GIT_PASSWORD'])
```

两项凭据必须同时提供，且只适用于 HTTP(S) URL。前台执行完成后删除临时文件；
使用 `background=True` 时，在句柄 `wait()` 结束后删除。该方式会把凭据交给
沙箱中的 Git 进程，应仅用于允许沙箱访问这些凭据的任务。

显式用户名在本次 Git 调用中优先于 `credential.username`，已配置的 credential helper
不会保存本次凭据。每次调用使用独立的私有临时目录，准备、上传、
执行及清理均使用本次 `user` 指定的身份；结束后同时删除 askpass 和临时目录。

## 暂停与恢复

`Sandbox.connect()`、实例 `connect()` 和 `SandboxClient.connect_sandbox()` 使用 Connect v2。省略 `timeout` 使用服务端默认的 300 秒；显式值必须至少为 1 秒。连接只延长 TTL，不会缩短已有 TTL；需要主动调整过期时间时使用 `set_timeout()`。

创建时可传入 `auto_pause=True`、`auto_pause_memory=False` 和 `auto_resume={'enabled': False}`（也可使用布尔值）。不传这些选项时保留服务端默认值；显式 `False` 会发送到服务端。`lifecycle` 的 `keep_memory` / `auto_resume` 也映射到对应选项。

`pause(memory=False)` 只保存文件系统，恢复会冷启动并丢失运行中的进程和内存状态，需要显式调用 `connect()` 或 `resume()`，不能靠流量自动恢复。`auto_pause_memory=False` 不能和启用的 `auto_resume` 同时使用。

## 持久快照

`sandbox.create_snapshot(idempotency_key, memory=None, name=None)` 或 `client.create_sandbox_snapshot(sandbox_id, idempotency_key, ...)` 返回原始字典，包含 `snapshotID` 和 `names`。可用 `Sandbox.create(snapshot['snapshotID'])` 创建沙箱，用 `client.delete_template(snapshot_id)` 删除快照模板。

每次新捕获必须使用新的幂等键（1–128 字节），包括同名快照的新版本。调用前应持久保存键与请求体；等待超时或网络中断后用原键、原沙箱 ID 和原请求体重试。取消客户端等待不会取消已接受的捕获，服务端会重放终态结果，包括失败。幂等记录在完成后保留 35 分钟；结果未知时先按来源或名称查询核对，不能直接换键或在记录过期后假定重试仍然安全。

快照自动重试网络错误（包括响应体传输中断）、408、502、504 和 `error_code=api_shutdown` 的 503，遵循有效的 ASCII 非负整数 `Retry-After`；无效或超出支持范围的值回退到指数退避，500 和其他 503 直接返回。自动重试从首次请求开始最多持续 35 分钟，包含请求耗时和等待；若下次重试将超出窗口，则抛出结果可能未知的 `SandboxError`，保留原始错误供排查。该限制不会中断正在进行的请求；重试窗口耗尽后应先查询快照核对结果。`SandboxError.error_code` 可读取语义错误码，完整响应保留在 `data` / `response`。`SANDBOX_RETRY_MAX` 控制重试次数（默认 5，0 禁用）。

`client.list_snapshots(sandbox_id=None, name=None, limit=None, next_token=None)` 返回 `{'items': [...], 'nextToken': ...}`，游标来自响应的 `X-Next-Token`。持续传入 `next_token` 直到返回值为空，避免遗漏快照。`name` 可带命名空间和标签，创建快照时的 `name` 只能是别名和可选标签，不能带 `/`。

## 模板磁盘与标签

`create_template(min_disk_mb=10240, min_free_disk_mb=1024)` 分别指定构建后的最小总磁盘和最小剩余空间（MiB），同时设置时满足两者要求。总磁盘省略或为 0 表示不设置最小值；剩余空间省略时使用团队默认值，为 0 表示不为剩余空间扩容。已有文件系统不会缩小，剩余空间增长是尽力而为，实际值可能略小于目标。

旧的 `disk_size_mb` / `diskSizeMB` 已从 v3 创建模板规范移除，SDK 会提示改用上述选项，避免将总大小误解为剩余空间。API 原始字段 `minDiskMb` / `minFreeDiskMb` 也可使用。

`client.list_template_tags(template_id)` 返回每个标签最近一次分配的 `tag`、`buildID` 和 `createdAt`。

## HTTP JSON 注入

HTTP 规则支持 `if_body`（兼容 `ifBody`）按顶层 JSON 字符串字段精确匹配，以及 `body` 写入秘密字符串字段。匹配条件只是请求筛选条件，沙箱进程也能构造匹配请求，应通过精确的 `base_url` 限制目标。仅支持未压缩、最大 1 MiB 的 `application/json` 请求；需要处理 body 时，非法或不支持的 body 会报错。目标字段已有非字符串值也会报错。`body` 的秘密值不会出现在 API 响应中。

## 测试

```bash
python -m pytest tests/cases/test_services/test_sandbox -q
```

单元测试使用记录请求的 Session 验证 HTTP 契约。集成测试在配置 API key 后访问实际服务并清理创建的资源；无凭据时跳过。仅运行本次新增契约的实际服务检查：

```bash
python -m pytest tests/cases/test_services/test_sandbox/test_integration.py -k 'snapshot or template_disk or http_body' -q
```
