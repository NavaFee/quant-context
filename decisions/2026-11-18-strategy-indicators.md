# 策略接口与指标口径

## 背景
T-73 已实现统一策略接口、四种指标和双均线示例；初始化口径需要固定，便于后续回测复现。

## 决定
- `Strategy.generate(bars)` 返回等长同索引、有限且在 `[0,1]` 的 float64 Series；参数用 dataclass，空输入返回空序列，非法输入或输出抛 `ValueError`。
- SMA 取最近 n 根收盘均值；EMA 用前 n 根均值初始化，随后以 α=2/(n+1) 递推。
- RSI 用前 n 个价格变化的涨跌均值初始化，随后按 Wilder（α=1/n）递推；仅涨、仅跌、全平分别为 100、0、50。
- ATR 首根 TR=high−low，后续 TR=max(high−low, abs(high−前收), abs(low−前收))；前 n 个 TR 均值初始化，随后按 Wilder 递推。
- SMA、EMA、ATR 前 n−1 根为 NaN，RSI 前 n 根为 NaN；窗口按实际行数计算，缺口不补数据。
- 双均线参数冻结，fast、slow 为排除 bool 的正整数且 fast < slow；快 SMA 严格大于慢 SMA 时为 1，否则为 0，慢线预热阶段为 0。

## 放弃的方案
- 直接采用第三方库默认初始化：可能产生不同指标值，统一使用上述显式口径。
- 在策略内移动信号或补齐时间缺口：信号保留当根收盘语义，缺口保留原始数据形态。

## 影响
- 自定义策略自行保证无未来数据；基类只校验输入输出。回测层按 `product.md` 在下一根开盘处理目标仓位。
- 依据：[T-73 已合并实现 PR #4](https://github.com/NavaFee/quant-engine/pull/4)（`1ba00b8`）；用法和校验细节见引擎 `src/quant_engine/strategy/README.md`。
