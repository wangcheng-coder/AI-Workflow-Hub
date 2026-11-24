# 路线

## 远程仓库

- 仓库：https://github.com/wangcheng-coder/AI-Workflow-Hub
- `main` 已推送初始提交 `bf87e74`。
- CI 工作流是 `.github/workflows/ci.yml`，只安装项目并运行 `pytest`。
- 首次推送的运行已成功：https://github.com/wangcheng-coder/AI-Workflow-Hub/actions/runs/44689668267
- Milestone「0.2 下一步」跟踪下面三个 Issue：
  - #1 用 PostgreSQL 保存运行状态
  - #2 增加不绑定厂商的模型提供方接口
  - #3 提供可导入的工作流模板
## 已完成：0.1.0

YAML 校验、条件、受限 script、HTTP 防护、重试、超时、审批暂停和按已成功节点恢复。

## 下一步

0.1.1 已完成的部分写在变更记录里。仍未完成的是需要真实数据库或仍未替换存储的部分。

1. 把运行状态放到 PostgreSQL，进程重启后仍能恢复。
2. 增加模型提供方接口。引擎不保存某一家的密钥格式。
3. 提供可导入的 CI 失败分析和发布说明模板。

## 暂不做

可视化编辑器、并行节点和分布式执行。

## 0.1.2

借鉴 [FlowRun](https://github.com/runboktu/FlowRun) 的空跑计划，以及 Windmill 把拒绝和等待区分开的做法。空跑不访问网络；明确拒绝会使本次运行失败。

## 0.1.3

必填输入、空跑接口和结果脱敏。空跑不访问网络。

## 0.1.4

空跑展示节点类型。等待时间不能为负，Shell 不执行。

## 0.1.5

接口可以把运行记录保存到 SQLite。PostgreSQL 仍未接入。

## 0.1.6

Spring AI 通过 MCP 做空跑。空跑不访问网络。

## 0.1.7

配置从 Nacos 读取。镜像由 GitHub Actions 发布到 GHCR。

## 0.1.8

提供统一控制台 `/`。页面只调用本服务接口。
