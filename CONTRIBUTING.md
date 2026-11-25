# 贡献代码指南

我们非常欢迎大家来贡献代码，我们会向贡献者致以最诚挚的敬意。

一般可以通过在Github上提交[Pull Request](https://github.com/qiniu/python-sdk)来贡献代码。

## Pull Request要求

- **代码规范** 遵从pep8，pythonic。

- **代码格式** 提交前 请按 pep8 进行格式化。

- **必须添加测试！** - 如果没有测试（单元测试、集成测试都可以），那么提交的补丁是不会通过的。

- **记得更新文档** - 保证`README.md`以及其他相关文档及时更新，和代码的变更保持一致性。

- **考虑我们的发布周期** - 我们的版本号会服从[SemVer v2.0.0](http://semver.org/)，我们绝对不会随意变更对外的API。

- **创建feature分支** - 最好不要从你的master分支提交 pull request。

- **一个feature提交一个pull请求** - 如果你的代码变更了多个操作，那就提交多个pull请求吧。

- **清晰的commit历史** - 保证你的pull请求的每次commit操作都是有意义的。如果你开发中需要执行多次的即时commit操作，那么请把它们放到一起再提交pull请求。

## 运行测试

``` bash
py.test

```

## 发布到 PyPI

直接发布正式 GitHub Release，或将使用正式版本标签的预发布转为正式版，都会触发 `.github/workflows/pypi-publish.yml`。工作流从对应标签构建并检查 wheel 和源码包，通过后由 `pypi` 环境中的独立 job 上传。

### 为什么采用 OIDC

使用 PyPI API token 发布时，维护者需要生成发布凭据、保存到 GitHub Secrets，并负责权限和轮换。Trusted Publishing 将授权绑定到 GitHub 仓库、工作流文件和发布环境，省去保存和轮换长期发布 token 的工作。

上传 job 运行时，GitHub 通过 OIDC 签发带签名的身份凭据。PyPI 核对它来自获准的仓库、工作流和环境，再签发范围限于该 PyPI 项目的短期上传凭据。工作流只给上传 job 配置请求 OIDC 身份凭据的权限。[PyPI Trusted Publishing 说明](https://docs.pypi.org/trusted-publishers/using-a-publisher/)

### 配置与补发

首次发布前，由 `qiniu` 的 PyPI 管理员在 **Manage → Publishing → GitHub** 中配置 Trusted Publisher：

| 字段 | 值 |
| --- | --- |
| Owner | `qiniu` |
| Repository | `python-sdk` |
| Workflow filename | `pypi-publish.yml` |
| Environment | `pypi` |

在 GitHub 仓库的 **Settings → Environments → pypi** 配置部署保护：

- 在 **Deployment branches and tags** 选择指定分支和标签。允许分支 `master` 用于手动补发，允许标签 `v*` 用于正式 Release。自动发布需要允许版本标签。
- 为环境配置可信发布审核人，使用仓库规则集限制 `v*` 标签的创建、修改及删除。发布前核对标签指向已合入的提交。

工作流要求标签符合 `vX.Y.Z`，并与 `qiniu/__init__.py` 中的 `__version__` 一致。手动补发会在检出源码前确认标签对应已发布的正式 GitHub Release。补发使用标签对应的代码，适用于尚未上传到 PyPI 的版本。

发布工作流把 Actions 固定到官方发行提交，并固定 build、twine、setuptools 和 wheel 的版本。构建使用预装的后端，工具的传递依赖仍由 pip 解析。更新这些工具时，重新验证 wheel、源码包和安装后的导入。

合入 `master` 并完成授权后，如需补发现有标签，从 `master` 手动启动工作流：

```bash
gh workflow run pypi-publish.yml --repo qiniu/python-sdk --ref master -f tag=v7.20.0
```

如果 PyPI 已接收部分文件但上传 job 失败，从原运行重跑失败的 job，复用同一次构建产物。工作流会按文件名和 SHA-256 核对 PyPI 上已有的文件，只上传缺失项。同名文件的摘要不一致时，任务会失败。
