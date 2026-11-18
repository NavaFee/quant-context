# 用三个仓库

## 背景
系统有数据层、策略层、回测与评估层和界面四块。三层 Python 代码之间调用频繁。

## 决定
三个仓库：quant-engine（三层 Python 代码，一个包里的三个子包）、quant-web（界面）、quant-context（共享上下文）。

## 放弃的方案
- 每层一个仓库：跨仓依赖会让每次改接口都要发版和对齐版本，对当前规模不划算。
- 全部放一个仓库：Python 和前端的工具链、CI、评审人都不同，放一起互相干扰。

## 影响
- 层与层的边界靠 quant-engine 里的目录和依赖方向约束（backtest → strategy → data）。
- quant-engine 和 quant-web 之间只通过回测结果 JSON 交互，格式写在 product.md。
