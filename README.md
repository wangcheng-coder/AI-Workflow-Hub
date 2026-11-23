# AI Workflow Hub

工作流负责顺序、分支、重试和审批。节点只做一件受限的事。当前版本不绑定模型厂商，也没有可视化编辑器。

## 0.1.0 能做什么

- 解析并校验 version 1 的 YAML：唯一的 start、至少一个 end、无环、节点不超过 100 个。
- 运行 start、end、condition、script、http、delay、approval 和 shell。
- condition 使用自写表达式，只支持比较、与或非和括号，不调用 `eval`。
- script 只允许 `action: set`。
- http 拒绝本机、内网和链路本地地址。库函数默认没有传输器，因此不会自己发请求。
- shell 节点只记录“未执行”，不会启动进程。
- 重试最多 5 次。delay 超过 `timeout_seconds` 会失败。
- approval 会暂停。带上已成功节点的输出和审批结果后可以继续。

## 限制

- 恢复会跳过已成功节点，但没有独立的数据库持久化。
- 没有并行节点，也没有图形编辑器。
- API 进程重启后，内存里的运行记录会消失。

工作流字段见 `docs/architecture/workflow-spec.md`。

## 本地运行

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn workflow_hub.api:app --reload
```

## 许可证

Apache-2.0。

## 语言和 Spring AI

默认语言是中文。请求带 `Accept-Language: en` 或 `?lang=en` 时，错误信息和工具说明返回英文。源码、SQL、日志原文不翻译。

Spring AI 不内嵌在本服务里。把 `spring-ai/pom-snippet.xml` 的 `spring-ai-starter-mcp-client` 加到 Spring AI 应用，连接配置由 `spring-ai/application-mcp.yml` 指向 Nacos，地址写在 `nacos/spring-mcp.yaml`。端点默认是 `/mcp`。本仓库的测试覆盖 MCP 的 initialize、tools/list 和 tools/call，不编译 Java。

## 配置

服务地址不写进镜像。设置 `NACOS_SERVER` 后，进程启动时读取 Nacos 中的服务配置，默认 dataId 见 `nacos/service.properties`。没有 Nacos 时使用 `APP_HOST`、`APP_PORT`、`APP_DATABASE` 和 `APP_LOCALE`。

Spring AI 的 MCP 地址放在 Nacos 的 `nacos/spring-mcp.yaml`。`spring-ai/application-mcp.yml` 只指向 Nacos，不写服务地址。

## 镜像

```bash
docker build -t ai-workflow-hub:local .
```

`main` 分支的 `.github/workflows/image.yml` 会把镜像推到 `ghcr.io/1455224865w-cmd/ai-workflow-hub`。

## 页面

打开服务根路径 `/`。五个项目使用同一套版式：顶栏、左右两栏、中英文切换。页面只调用本服务已有的接口。
