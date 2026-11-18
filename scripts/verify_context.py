"""Offline documentation checks, adapted from T-78's verify_t78_contract.py."""

import argparse
import copy
from datetime import date
from decimal import Decimal, getcontext
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

getcontext().prec = 50
NULLABLE = set("total_return annual_return annual_volatility sharpe max_drawdown calmar win_rate profit_factor".split())
METRICS = NULLABLE | {"trade_count"}
PERIODS = {"1h": 3600000, "4h": 14400000, "1d": 86400000}
SCHEMA = {
    "meta": set("strategy params symbol interval start end fee_bps slippage_bps initial_cash".split()),
    "bars": set("ts open high low close volume".split()),
    "equity": set("ts equity drawdown".split()),
    "trades": set("ts side price qty fee".split()),
}


def require(condition, location, message):
    if not condition:
        raise ValueError(f"{location}: {message}")


def number(value, location):
    require(type(value) in (int, Decimal), location, "expected a number, excluding bool")
    require(math.isfinite(float(value)), location, "expected a finite number")


def walk(value, path=(), restrict_null=False):
    if isinstance(value, dict):
        for key, item in value.items():
            walk(item, path + (key,), restrict_null)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk(item, path + (index,), restrict_null)
    elif value is None and restrict_null:
        require(len(path) == 2 and path[0] == "metrics" and path[1] in NULLABLE,
                path, "null is only allowed in the eight nullable metrics")
    elif type(value) in (int, Decimal):
        number(value, path)


def strict_loads(raw):
    def reject_constant(value):
        raise ValueError(f"non-JSON constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, key, "duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(raw, parse_float=Decimal, parse_constant=reject_constant,
                       object_pairs_hook=unique_object)
    walk(value)
    return value


def fields(value, keys, location):
    require(type(value) is dict and set(value) == keys, location,
            f"expected object with fields {', '.join(sorted(keys))}")


def integer(value, location):
    require(type(value) is int, location, "expected an integer, excluding bool")


def validate(report):
    fields(report, set(SCHEMA) | {"metrics"}, "report")
    walk(report, restrict_null=True)
    meta = report["meta"]
    fields(meta, SCHEMA["meta"], "meta")
    for key in ("strategy", "symbol", "interval"):
        require(type(meta[key]) is str and meta[key], f"meta.{key}", "expected nonempty string")
    require(type(meta["params"]) is dict, "meta.params", "expected object")
    for key in ("start", "end"):
        integer(meta[key], f"meta.{key}")
    for key in ("fee_bps", "slippage_bps", "initial_cash"):
        number(meta[key], f"meta.{key}")
    require(meta["initial_cash"] > 0, "meta.initial_cash", "must be positive")
    for key in ("fee_bps", "slippage_bps"):
        require(0 <= meta[key] < 10000, f"meta.{key}", "must be in [0,10000)")
    require(meta["interval"] in PERIODS, "meta.interval", "expected 1h, 4h or 1d")
    for group in ("bars", "equity", "trades"):
        require(type(report[group]) is list, group, "expected array")
        for index, item in enumerate(report[group]):
            location = f"{group}[{index}]"
            fields(item, SCHEMA[group], location)
            integer(item["ts"], f"{location}.ts")
            for key in sorted(SCHEMA[group] - {"ts", "side"}):
                number(item[key], f"{location}.{key}")
            if group == "trades":
                require(item["side"] in ("buy", "sell"), location, "side must be buy or sell")
    timestamps = [bar["ts"] for bar in report["bars"]]
    require(timestamps and timestamps == sorted(set(timestamps)), "bars.ts", "must be nonempty, ascending and unique")
    require([point["ts"] for point in report["equity"]] == timestamps, "equity.ts", "must align with bars")
    require(meta["start"] == timestamps[0] and meta["end"] == timestamps[-1] + PERIODS[meta["interval"]],
            "meta.start/end", "must cover [first bar, last bar + interval)")
    require(all(t["ts"] in timestamps for t in report["trades"]), "trades.ts", "must match bars")
    metrics = report["metrics"]
    fields(metrics, METRICS, "metrics")
    integer(metrics["trade_count"], "metrics.trade_count")
    require(metrics["trade_count"] >= 0, "metrics.trade_count", "must be nonnegative")
    for key in sorted(NULLABLE):
        if metrics[key] is not None:
            number(metrics[key], f"metrics.{key}")
    require(metrics["max_drawdown"] is None or metrics["max_drawdown"] <= 0,
            "metrics.max_drawdown", "must be nonpositive")


def near(actual, expected, location):
    valid = actual is None if expected is None else actual is not None and abs(Decimal(actual) - expected) < Decimal("1e-9")
    require(valid, location, f"expected {expected}, got {actual}")


def verify_example(report):
    """Replay the two documented continuous samples and independently recompute metrics."""
    validate(report)
    meta = report["meta"]
    cash = peak = Decimal(meta["initial_cash"])
    quantity = round_pnl = Decimal(0)
    pnls, equities, drawdowns = [], [], []
    for index, (bar, point) in enumerate(zip(report["bars"], report["equity"])):
        for trade in (t for t in report["trades"] if t["ts"] == bar["ts"]):
            signed_qty = Decimal(trade["qty"]) * (1 if trade["side"] == "buy" else -1)
            movement = -signed_qty * Decimal(trade["price"]) - Decimal(trade["fee"])
            quantity += signed_qty
            require(quantity >= 0, "trades.qty", "sample cannot hold a short position")
            cash += movement
            round_pnl += movement
            if quantity == 0:
                pnls.append(round_pnl)
                round_pnl = Decimal(0)
        equity = cash + quantity * Decimal(bar["close"])
        peak = max(peak, equity)
        drawdown = equity / peak - 1
        near(point["equity"], equity, f"equity[{index}].equity")
        near(point["drawdown"], drawdown, f"equity[{index}].drawdown")
        equities.append(equity)
        drawdowns.append(drawdown)
    timestamps = [b["ts"] for b in report["bars"]]
    require(len(timestamps) >= 3 and all(b - a == PERIODS[meta["interval"]] for a, b in zip(timestamps, timestamps[1:])),
            "bars.ts", "reference examples require at least three continuous bars")
    returns = [current / previous - 1 for previous, current in zip(equities, equities[1:])]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    total = equities[-1] / Decimal(meta["initial_cash"]) - 1
    annual = (1 + total) ** (Decimal(365 * 86400000) / (timestamps[-1] - timestamps[0])) - 1
    volatility = variance.sqrt() * (Decimal(365 * 86400000) / PERIODS[meta["interval"]]).sqrt()
    drawdown = min(drawdowns)
    profits = sum((p for p in pnls if p > 0), Decimal(0))
    losses = -sum((p for p in pnls if p < 0), Decimal(0))
    expected = {
        "total_return": total, "annual_return": annual, "annual_volatility": volatility,
        "sharpe": annual / volatility if volatility else None,
        "max_drawdown": drawdown, "calmar": annual / abs(drawdown) if drawdown else None,
        "win_rate": Decimal(sum(p > 0 for p in pnls)) / len(pnls) if pnls else None,
        "profit_factor": profits / losses if losses else None, "trade_count": Decimal(len(pnls)),
    }
    for key, value in expected.items():
        near(report["metrics"][key], value, f"metrics.{key}")


def check_product(text):
    fence = None
    section = ""
    example_kind = None
    count, examples = 0, []
    lines = text.splitlines()
    for line_no, line in enumerate(lines, 1):
        if fence:
            marker, language, start, kind = fence
            if re.fullmatch(r" {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*", line):
                if language.lower() == "json":
                    count += 1
                    location = f"product.md:{start} JSON block #{count}"
                    try:
                        report = strict_loads("\n".join(lines[start:line_no - 1]))
                        if kind is not None:
                            verify_example(report)
                            require(bool(report["trades"]) == kind, "trades", "does not match the example label")
                            examples.append((report, start, line_no))
                        example_kind = None
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"{location}: line {start + exc.lineno}, column {exc.colno}: {exc.msg}") from exc
                    except (ValueError, ArithmeticError) as exc:
                        raise ValueError(f"{location}: {exc}") from exc
                fence = None
        else:
            heading = re.match(r"^ {0,3}(#{1,3})[ \t]+(.*?)[ \t]*#*[ \t]*$", line)
            if heading:
                section = heading[2]
                example_kind = None
            if section == "合法 JSON 示例" and line.startswith(("有成交：", "无成交：")):
                example_kind = line.startswith("有成交：")
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})([^`]*?)\s*$", line)
            if opening:
                fence = (opening[1], opening[2].strip(), line_no, example_kind)
    require(fence is None, f"product.md:{fence[2] if fence else 1}", "unclosed code fence")
    require(sorted(bool(report["trades"]) for report, _, _ in examples) == [False, True],
            "product.md 合法 JSON 示例", "expected one traded and one no-trades complete example")
    return count, examples


def check_decision(path, text):
    match = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2})-(\S(?:.*\S)?)\.md", path.name)
    require(match is not None, path, "expected YYYY-MM-DD-<topic>.md")
    try:
        date.fromisoformat(match[1])
    except ValueError as exc:
        raise ValueError(f"{path}: invalid calendar date") from exc
    lines = text.splitlines()
    require(len(lines) <= 20, path, f"{len(lines)} lines exceeds limit 20 (including blanks)")
    headings = [(i, re.sub(r"[ \t]+#+[ \t]*$", "", line.strip()[3:]).strip())
                for i, line in enumerate(lines) if re.match(r"^ {0,3}##[ \t]+", line)]
    require([title for _, title in headings] == ["背景", "决定", "放弃的方案", "影响"],
            path, "expected exactly four H2 sections: 背景 / 决定 / 放弃的方案 / 影响")
    for index, (start, title) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        require(any(line.strip() and not line.lstrip().startswith("#") for line in lines[start + 1:end]),
                f"{path}:{start + 1}", f"empty section: {title}")


def verify(repo):
    count, _ = check_product((repo / "product.md").read_text(encoding="utf-8"))
    decisions = sorted(path for path in (repo / "decisions").rglob("*") if path.is_file())
    require(decisions, "decisions/", "expected decision files")
    for path in decisions:
        check_decision(path.relative_to(repo), path.read_text(encoding="utf-8"))
    print(f"PASS: {count} strict JSON blocks; 2 complete examples, all 9 metrics within 1e-9; {len(decisions)} decisions")


def self_test(repo):
    product = (repo / "product.md").read_text(encoding="utf-8")
    _, examples = check_product(product)
    traded = next(report for report, _, _ in examples if report["trades"])
    lines = product.splitlines(keepends=True)
    spans = [(len("".join(lines[:start - 1])), len("".join(lines[:end - 1])), len("".join(lines[:end])))
             for _, start, end in examples]
    cases = 0

    def probe(label, function, *args, fails=True):
        nonlocal cases
        try:
            function(*args)
        except ValueError:
            require(fails, label, "unexpected rejection")
        else:
            require(not fails, label, "invalid input was accepted")
        cases += 1

    for raw in ("NaN", "Infinity", "-Infinity", '{"x": 1, "x": 2}', "1e999", '{"nested": {"x": 1, "x": 2}}'):
        probe(raw, strict_loads, raw)
    for path, bad in [
        (("metrics", "total_return"), True), (("metrics", "annual_return"), Decimal("1e999")),
        (("metrics", "trade_count"), True), (("metrics", "trade_count"), None),
        (("metrics", "trade_count"), Decimal("1.5")), (("metrics", "trade_count"), -1),
        (("meta", "start"), True), (("meta", "end"), traded["meta"]["end"] - 86400000),
        (("meta", "initial_cash"), None), (("meta", "params"), {"nested": [None]}),
        (("bars", 0, "close"), False), (("equity", 0, "ts"), 0),
        (("equity", 0, "equity"), None), (("trades", 0, "qty"), True), (("bars",), []),
        (("meta",), []), (("metrics",), []), (("bars", 0), None),
        (("meta", "interval"), "1m"), (("meta", "initial_cash"), 0),
        (("meta", "fee_bps"), -1), (("meta", "slippage_bps"), 10000),
        (("bars", 1, "ts"), traded["bars"][0]["ts"]), (("trades", 0, "side"), "hold"),
        (("metrics", "max_drawdown"), 1),
    ]:
        mutated = copy.deepcopy(traded)
        target = mutated
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = bad
        probe(str(path), validate, mutated)
    probe("missing field", validate, {key: value for key, value in traded.items() if key != "meta"})
    probe("extra field", validate, dict(traded, extra=1))
    decision = "\n".join(f"## {title}\ntext" for title in ("背景", "决定", "放弃的方案", "影响"))
    name = Path("decisions/2024-02-29-topic.md")
    for label, body, fails in [
        ("20 lines", decision + "\n" * 13, False), ("21 lines", decision + "\n" * 14, True),
        ("missing", decision.replace("## 影响", "影响"), True),
        ("empty", decision.replace("## 决定\ntext", "## 决定\n"), True),
        ("order", decision.replace("## 背景\ntext\n## 决定", "## 决定\ntext\n## 背景"), True),
        ("duplicate", decision.replace("## 背景", "## 决定"), True),
        ("extra", decision + "\n## extra\ntext", True),
    ]:
        probe(label, check_decision, name, body, fails=fails)
    for filename in ("2023-02-29-topic.md", "2026-13-01-topic.md", "2026-1-01-topic.md", "2026-01-01-.md", "2026-01-01- .md", "topic.txt"):
        probe(filename, check_decision, Path(filename), decision)
    for start, _, end in spans:
        probe("missing example", check_product, product[:start] + product[end:])
    for label, changed, fails in [
        ("unclosed fence", product[:spans[-1][1]], True),
        ("valid extra JSON", product + '\n```json\n{"extra": null}\n```\n', False),
        ("invalid extra JSON", product + '\n```json\n{"extra": NaN}\n```\n', True),
        ("earlier JSON", '```json\n{"extra": 1}\n```\n' + product, False),
        ("extra JSON in example section", product.replace("无成交：", '```json\n{"extra": 1}\n```\n\n无成交：'), False),
        ("syntax", product.replace('"trade_count": 1', '"trade_count": }', 1), True),
        ("wrong metric", product.replace('"total_return": -0.01', '"total_return": -0.02', 1), True),
        ("missing section", product.replace("### 合法 JSON 示例", "### other"), True),
        ("short closing fence", product[:spans[-1][1]] + "``\n", True),
        ("tilde fences", product.replace("```", "~~~~"), False),
        ("longer fences", product.replace("```", "````"), False),
    ]:
        probe(label, check_product, changed, fails=fails)
    # Copy and invoke the real CLI: a broken metric must fail even with -O.
    with tempfile.TemporaryDirectory(prefix="verify-context-") as temporary:
        root = Path(temporary)
        shutil.copytree(repo / "decisions", root / "decisions")
        (root / "scripts").mkdir()
        shutil.copy2(__file__, root / "scripts/verify_context.py")
        command = [sys.executable, "-O", "scripts/verify_context.py"]
        for broken in (True, False):
            body = product.replace('"trade_count": 1', '"trade_count": true', 1) if broken else product
            require(not broken or body != product, "AC5", "mutation target missing")
            (root / "product.md").write_text(body, encoding="utf-8")
            result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
            require(result.returncode == (1 if broken else 0), "CLI", result.stdout + result.stderr)
            if broken:
                require("product.md:" in result.stderr and "JSON block #1" in result.stderr and "metrics.trade_count" in result.stderr,
                        "CLI", "missing file/block/field diagnostic")
            print(f"AC5 {'broken' if broken else 'restored'}: exit {result.returncode}\n{(result.stderr or result.stdout).strip()}")
            cases += 1
    print(f"PASS: {cases} self-tests, including the original 19 rejection probes and optimized CLI failure/recovery")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="also run offline regression probes")
    args = parser.parse_args()
    try:
        require(sys.version_info >= (3, 11), "Python", "requires Python 3.11+")
        repo = Path(__file__).resolve().parents[1]
        verify(repo)
        if args.self_test:
            self_test(repo)
    except (ValueError, OSError, ArithmeticError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
