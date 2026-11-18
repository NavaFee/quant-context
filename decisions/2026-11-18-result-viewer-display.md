# 结果查看界面的加载与月度收益口径

## 背景
T-76 的结果查看界面需要统一文件加载与月收益展示；依据 [quant-web PR #1](https://github.com/NavaFee/quant-web/pull/1)（已合并），实现见 `src/pages/ReportPage.tsx`、`src/lib/monthly.ts`。

## 决定
- 默认加载 `public/samples/result.json`；本地文件仅在浏览器解析，校验成功后整体替换报告，失败保留上次成功报告，连续选择只采用最新一次。
- 指标和回撤直接展示导出值；时间显示 UTC，K 线买卖点取 `trades.ts/price`，成交价已含滑点。
- 月收益按 `equity.ts` 所属 UTC 月分组，月内最后权益 / 相邻上月末权益 − 1；首个有数据月以 `initial_cash` 为基数。
- 无数据月、缺相邻上月基数、基数为 0 或派生结果非有限时显示“—”；不跨缺月借基数。真实零收益仍显示 0。
- 报告 `[start,end)` 未覆盖完整自然月时，该月标 `*` 表示区间收益；C=100、1 月末=110、2 月末=99 对应 +10%、−10%。

## 放弃的方案
- 上传文件到后端解析；跨缺月借用更早基数；将不可计算收益当作 0；将不足整月的区间收益当作完整月收益。

## 影响
- 月收益由 quant-web 派生，不新增结果 JSON 字段；导出契约仍以 product.md 为准。
- 月收益及区间收益术语见 glossary.md；运行命令、Node 版本和浏览器检查约定见 quant-web 的 AGENTS.md、README.md。
