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

### 回测结果 JSON

顶层字段固定为 `meta`、`metrics`、`equity`、`trades`、`bars`，字段集合和三组数组结构保持不变。

| 对象 | 字段及类型 |
|---|---|
| meta | strategy、symbol、interval 为 string；params 为策略参数 object；start、end 为整数 UTC 毫秒；fee_bps、slippage_bps、initial_cash 为 number |
| equity 每项 | ts 为整数 UTC 毫秒；equity、drawdown 为 number |
| trades 每项 | ts 为整数 UTC 毫秒；side 为 "buy" 或 "sell"；price、qty、fee 为 number |
| bars 每项 | ts 为整数 UTC 毫秒；open、high、low、close、volume 为 number |
| metrics | 下表列出的九个字段，均必填；仅其中八项允许 null |

数值字段必须为有限 number（整数也属于 number），不接受 bool；整数类型同样不接受 bool。禁止 JSON `NaN`、`Infinity`、`-Infinity`，`null` 只允许出现在八项 nullable 指标中，不能用于其他字段或 `params` 内部。比率用小数表示（0.12 表示 12%），`max_drawdown` 为非正数。`null` 表示不可计算，界面显示“—”，不能转成 0；合法的数值 0 仍显示为零值。

`meta` 来自实际策略和回测配置，`initial_cash > 0`，手续费与滑点 bps 均在 `[0,10000)`。非空报告的 `meta.start=bars[0].ts`，`meta.end=bars[-1].ts+周期毫秒`，表示实际覆盖的 `[start,end)`；1h、4h、1d 分别为 3600000、14400000、86400000 毫秒。导出拒绝空 bars，不生成无法确定时间范围的报告。

`bars` 按 ts 升序且无重复；`equity` 与 bars 等长、逐项 ts 对齐。权益在每根收盘估值，但 `equity.ts` 沿用该根开盘时间；首末收盘估值时点都加同一周期，因此其历时等于 `末 ts−首 ts`。三根连续日线的报告覆盖三天，年化历时为两天。行情缺口保留原状，不补造 bars。

### 绩效指标

设 N 个收盘权益为 E，初始资金为 C；`drawdown[i]=E[i]/max(C,E[0],…,E[i])−1`。以下公式遇到不可计算的边界按下表返回 `null`，非法输入和数值溢出则报错。

| 字段 | 类型 | 定义 |
|---|---|---|
| total_return | number 或 null | 总收益 `R=E末/C−1` |
| annual_return | number 或 null | 年化收益 `A=(1+R)^(365×86400000/(ts末−ts首))−1`，按首末收盘估值的历时计算 |
| annual_volatility | number 或 null | 年化波动 `V=std(r,ddof=1)×sqrt(P)`；`r[i]=E[i]/E[i−1]−1`，i 从 1 开始，不加入首根人为零收益；连续 1h/4h/1d 的 P 分别为 8760/2190/365 |
| sharpe | number 或 null | `A/V`，无风险利率为 0 |
| max_drawdown | number 或 null | 最大回撤 `D=min(drawdown)` |
| calmar | number 或 null | `A/abs(D)` |
| win_rate | number 或 null | 净盈利完整轮数 / 完整轮数，持平轮次计入分母 |
| profit_factor | number 或 null | PF＝盈利完整轮次净盈亏之和 / 亏损完整轮次净亏损绝对值之和 |
| trade_count | 非负整数 | 完整平仓轮数，不是成交笔数 |

完整平仓轮次以 `BacktestResult.positions.qty` 为边界：持仓从 0 变正开始一轮，回到 0 才完成；部分买入、部分卖出都归入同轮。轮次净盈亏为 `Σ(卖出 price×qty−fee)−Σ(买入 price×qty+fee)`，滑点已包含在成交价中，不重复扣除。净盈亏大于 0 才算盈利，等于 0 为持平。

末尾未完成轮次不计入 `trade_count`、胜率或 PF，包括该轮已经部分卖出的盈亏；其影响仍保留在权益中。`trades` 保留全部成交，`positions` 仅用于计算，不新增到 JSON。

### 指标边界

各条件可叠加；表中未受影响的指标仍按定义计算。非法输入或溢出优先报错，不能用 `null` 掩盖。

| 条件 | 结果 |
|---|---|
| 空输入（指标层） | 八项数值指标均为 null，trade_count=0；结果导出仍拒绝空 bars |
| 单根权益 | 可计算 total_return、max_drawdown；annual_return=null，annual_volatility、sharpe、calmar 也为 null |
| 少于两个有效相邻收益率 | annual_volatility、sharpe 为 null；std 使用样本标准差 ddof=1 |
| 任一前一期权益为 0 | annual_volatility、sharpe 为 null；不跳过该项去计算剩余收益率 |
| 任意相邻时间间隔不等于声明周期 | annual_volatility、sharpe 为 null，不补造行情；有效的 R、A、D 和依赖 A/D 的 Calmar 仍计算 |
| V=0，或 A、V 任一为 null | sharpe=null |
| D=0，或 A 为 null | calmar=null；空输入 D 为 null 时同样不可计算 |
| 无完整轮次 | win_rate、profit_factor 为 null，trade_count=0 |
| 有完整轮次但无亏损轮次（含全持平） | profit_factor=null；win_rate 仍按完整轮数计算 |
| 仅有亏损轮次 | win_rate=0、profit_factor=0 |
| 至少三根连续、无成交且权益恒等于 C | total_return、annual_return、annual_volatility、max_drawdown 均为 0；sharpe、calmar、win_rate、profit_factor 均为 null；trade_count=0 |
| 非有限输入或数值溢出 | 报错，不伪装成 null，不输出 NaN/Infinity |

### 合法 JSON 示例

有成交：C=100，三根日线的目标仓位为 `[1,0,0]`，第二根开盘以 100 买入 1 单位，第三根以 99 全卖出；手续费、滑点为 0。收盘权益为 `[100,110,99]`，形成一轮净亏损 −1，故胜率和 PF 都为 0。

```json
{
  "meta": {"strategy": "example_round_trip", "params": {}, "symbol": "BTCUSDT", "interval": "1d", "start": 1704067200000, "end": 1704326400000, "fee_bps": 0, "slippage_bps": 0, "initial_cash": 100},
  "metrics": {
    "total_return": -0.01,
    "annual_return": -0.840256566794465,
    "annual_volatility": 2.701851217221259,
    "sharpe": -0.310992907913943,
    "max_drawdown": -0.1,
    "calmar": -8.402565667944650,
    "win_rate": 0,
    "profit_factor": 0,
    "trade_count": 1
  },
  "equity": [
    {"ts": 1704067200000, "equity": 100, "drawdown": 0},
    {"ts": 1704153600000, "equity": 110, "drawdown": 0},
    {"ts": 1704240000000, "equity": 99, "drawdown": -0.1}
  ],
  "trades": [
    {"ts": 1704153600000, "side": "buy", "price": 100, "qty": 1, "fee": 0},
    {"ts": 1704240000000, "side": "sell", "price": 99, "qty": 1, "fee": 0}
  ],
  "bars": [
    {"ts": 1704067200000, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1},
    {"ts": 1704153600000, "open": 100, "high": 110, "low": 100, "close": 110, "volume": 1},
    {"ts": 1704240000000, "open": 99, "high": 99, "low": 99, "close": 99, "volume": 1}
  ]
}
```

无成交：三根连续日线，目标仓位全为 0，权益恒等于初始资金。四个不可计算的比率以 `null` 导出，界面显示“—”。

```json
{
  "meta": {"strategy": "example_no_trades", "params": {}, "symbol": "BTCUSDT", "interval": "1d", "start": 1704067200000, "end": 1704326400000, "fee_bps": 0, "slippage_bps": 0, "initial_cash": 100},
  "metrics": {
    "total_return": 0,
    "annual_return": 0,
    "annual_volatility": 0,
    "sharpe": null,
    "max_drawdown": 0,
    "calmar": null,
    "win_rate": null,
    "profit_factor": null,
    "trade_count": 0
  },
  "equity": [
    {"ts": 1704067200000, "equity": 100, "drawdown": 0},
    {"ts": 1704153600000, "equity": 100, "drawdown": 0},
    {"ts": 1704240000000, "equity": 100, "drawdown": 0}
  ],
  "trades": [],
  "bars": [
    {"ts": 1704067200000, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1},
    {"ts": 1704153600000, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1},
    {"ts": 1704240000000, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1}
  ]
}
```

另一个独立的平仓手算用例：完整轮次净盈亏 `[10,−5,0]` 对应 `win_rate=1/3`、`profit_factor=2`、`trade_count=3`，不与上述权益示例混用。示例数值与手算参考值的绝对误差应小于 `1e-9`。

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
