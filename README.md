# quant-context

加密货币量化系统的共享上下文。人和智能体都读这里。

| 文件 | 内容 |
|---|---|
| [product.md](product.md) | 产品说明、范围、层间契约 |
| [glossary.md](glossary.md) | 术语表 |
| [decisions/](decisions/) | 决策记录，一条决策一个文件 |

代码在 [quant-engine](https://github.com/NavaFee/quant-engine) 和 [quant-web](https://github.com/NavaFee/quant-web)。

## 维护规则

- 只写规则和结论，不写过程。
- 决策记录四段：背景 / 决定 / 放弃的方案 / 影响，不超过 20 行，文件名 `YYYY-MM-DD-<主题>.md`。
- 删除或改写已有决策必须走 PR，由人合并。

## 本地校验

使用 Python 3.11+，在仓库根目录运行 `python3 scripts/verify_context.py`，离线校验 product.md 的全部 JSON、两份完整示例与 decisions/ 的格式；仅使用标准库，无需安装依赖。
运行 `python3 scripts/verify_context.py --self-test` 可额外执行非法输入及临时副本篡改/恢复测试。PR 和推送到 main 时，GitHub Actions 的 `validate-context` 检查运行这两条命令，任一失败即失败。契约或示例变化时须同步更新校验规则。
