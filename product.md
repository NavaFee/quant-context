# 加密货币量化系统 产品说明

版本 v0.1 · 2026-11-18

## 目标

一套面向加密货币的研究用量化系统：管理行情数据，用统一接口写策略，回测并评估，在网页上看结果。

## 范围

| 层 | 仓库 | v0.1 要做的 |
|---|---|---|
| 数据层 | quant-engine | K 线数据模型；本地 Parquet 存储；数据源接口和一个公开行情源适配；数据质量检查；仓库内样例数据 |
| 策略层 | quant-engine | 策略接口；常用指标（SMA、EMA、RSI、ATR）；示例策略（双均线） |
| 回测与评估层 | quant-engine | 回测引擎（手续费、滑点）；绩效指标；结果导出为 JSON |
| 界面 | quant-web | 读取结果 JSON，展示指标、资金曲线、回撤、月度收益、K 线买卖点、成交列表 |

## 不做

- 执行层：实盘下单、撤单、账户、API key
- 实时行情和推送
- 多用户、登录、权限
- 合约、杠杆、做空、资金费率（以后再说）
- 参数优化和组合管理（以后再说）

## 市场和数据

- 市场：加密货币现货，只做多。
- 数据源：Binance 公开 K 线接口，不需要密钥。数据源做成接口，以后可以加别的交易所。
- 首批交易对和周期：BTCUSDT、ETHUSDT；1h、4h、1d。
- 加密货币 7×24 小时交易，年化一律按 365 天计算。
- 测试只用仓库里的样例数据，不联网。

## 层间契约

**K 线（bars）**：表格，按 `ts` 升序、无重复。

| 列 | 类型 | 说明 |
|---|---|---|
| ts | int64 | K 线开盘时间，UTC 毫秒 |
| open, high, low, close | float64 | 价格 |
| volume | float64 | 成交量 |

**策略输出**：与 bars 等长的目标仓位序列，取值 0 到 1，表示该根 K 线收盘后希望持有的仓位比例。

**成交规则**：第 t 根 K 线收盘产生的目标仓位，在第 t+1 根 K 线开盘价成交，扣手续费和滑点。

**回测结果 JSON**：

```json
{
  "meta": {"strategy": "", "params": {}, "symbol": "", "interval": "", "start": 0, "end": 0, "fee_bps": 0, "slippage_bps": 0, "initial_cash": 0},
  "metrics": {"total_return": 0, "annual_return": 0, "annual_volatility": 0, "sharpe": 0, "max_drawdown": 0, "calmar": 0, "win_rate": 0, "profit_factor": 0, "trade_count": 0},
  "equity": [{"ts": 0, "equity": 0, "drawdown": 0}],
  "trades": [{"ts": 0, "side": "buy", "price": 0, "qty": 0, "fee": 0}],
  "bars": [{"ts": 0, "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0}]
}
```

比率类指标用小数表示（0.12 表示 12%），`max_drawdown` 为非正数。

## 界面参考

- 报告布局参考 [QuantStats](https://github.com/ranaroussi/quantstats) 的 HTML tearsheet（Apache-2.0）。
- K 线图用 [KLineChart](https://github.com/klinecharts/KLineChart)（Apache-2.0）。
- 回测页的交互可以看 [FreqUI](https://github.com/freqtrade/frequi)。freqtrade 是 GPL-3.0，只参考思路，不复制代码。

## 里程碑

1. quant-engine 工程骨架
2. 数据层
3. 策略层
4. 回测引擎
5. 绩效评估和结果导出
6. quant-web 结果查看界面
