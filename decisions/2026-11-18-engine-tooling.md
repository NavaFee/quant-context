# quant-engine 工程约定

## 背景
三层 Python 代码需要统一的安装、检查与测试入口，供后续业务任务使用。

## 决定
- 使用 Python 3.11+、setuptools 和 `src/` 布局；发行名为 `quant-engine`，导入名为 `quant_engine`。
- `pip install -e ".[dev]"` 安装开发环境；Ruff、pytest 属于 `dev` 可选依赖。
- GitHub Actions 在 `push` 和 `pull_request` 时使用 Python 3.11，依次运行安装、`ruff check .`、`ruff format --check .`、`pytest -q`。
- 用 AST 测试检查源码的绝对与相对导入，禁止 data → strategy、data → backtest、strategy → backtest；测试离线运行。

## 放弃的方案
- 只在 PR 时运行 CI：分支推送也需要触发检查。
- 只对空子包检查依赖方向：用违规与合法导入样例验证检查器能识别边界。

## 影响
- 后续实现放入 `src/quant_engine/{data,strategy,backtest}/`，提交前运行上述三条检查命令。
- 工程骨架不定义业务接口；层间契约仍以 `product.md` 为准。
- 依据：[T-71 实现 PR](https://github.com/NavaFee/quant-engine/pull/1)。
