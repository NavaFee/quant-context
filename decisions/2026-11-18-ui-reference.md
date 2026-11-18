# 界面参考 QuantStats 的报告布局，K 线用 KLineChart

## 背景
界面只需要展示回测结果，希望参考成熟的开源项目，不从零设计。

## 决定
- 报告布局参考 QuantStats 的 HTML tearsheet：指标表、累计收益、回撤、月度收益。
- K 线和买卖点用 KLineChart。两者都是 Apache-2.0。

## 放弃的方案
- 直接改 FreqUI：它依赖 freqtrade 的后端接口，而且 freqtrade 是 GPL-3.0，复制代码会带来许可证约束。只参考它回测页的交互思路。

## 影响
- quant-web 不复制任何 GPL 代码。
- 界面的数据来源只有结果 JSON，不需要后端服务。
