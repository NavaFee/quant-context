# 行情数据读取与本地存储

## 背景
T-72 已实现 Binance 公开现货行情和本地 Parquet，供后续策略与回测读取。

## 决定
- 数据层使用 pandas、pyarrow；`DataSource.fetch` 返回符合 `product.md` 六列契约的 DataFrame，无数据返回同类型空表。
- 下载与读取按 UTC 开盘时间取 `[start, end)`；Binance 源仅返回下载开始时已收盘的 K 线。
- 文件位于 `<root>/<exchange>/<symbol>/<interval>/bars.parquet`；重叠写入按 `ts` 更新，同时间戳以本次最后一行覆盖，读取升序且无重复。
- 质量检查先于排序和去重，报告缺口、重复和乱序；缺口只报告，不补造 K 线。
- 下载全部成功后才写入；同目录临时文件原子替换，下载或写入失败保留旧文件，空下载不覆盖旧文件。

## 放弃的方案
- 自动补齐缺口：保留真实行情缺失，避免合成数据进入研究结果。
- 同一分区并发写入：当前采用单进程写入，尚无并发协调机制。

## 影响
- 读写载入整个分区，历史量增长会增加内存与耗时；原子替换不保证断电持久性。
- 离线测试可复用 `tests/fixtures/binance_btcusdt_1h.json` 的 500 根历史样例；调用方法见 `src/quant_engine/data/README.md`。
- 依据：[T-72 已合并实现 PR #3](https://github.com/NavaFee/quant-engine/pull/3)（`42d321e`）；层间契约仍以 `product.md` 为准。
