"""Reporting — machine-readable JSON + a self-contained, escaped HTML report."""

import html
import json
from pathlib import Path

from evals import config


def summarize(results: list[dict]) -> dict:
    """Aggregate scores into total / average / pass-rate (spec Â§7)."""
    n = len(results)
    if n == 0:
        return {"total": 0, "average_score": 0.0, "passed": 0, "pass_rate": 0.0}
    scores = [r["score"] for r in results]
    passed = sum(1 for s in scores if s >= config.PASS_THRESHOLD)
    return {
        "total": n,
        "average_score": round(sum(scores) / n, 2),
        "passed": passed,
        "pass_rate": round(100.0 * passed / n, 1),
    }


def _color(score: int) -> str:
    if score >= config.COLOR_GREEN_MIN:
        return "#1a7f37"  # green
    if score >= config.COLOR_YELLOW_MIN:
        return "#9a6700"  # yellow/amber
    return "#cf222e"  # red


def write_json(path: str | Path, results: list[dict], summary: dict, meta: dict) -> None:
    payload = {"meta": meta, "summary": summary, "results": results}
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _esc(value: object) -> str:
    """HTML-escape any value (spec Â§9 hardening: never inject raw)."""
    if not isinstance(value, str):
        value = json.dumps(value, indent=2, ensure_ascii=False)
    return html.escape(value)


def write_html(path: str | Path, results: list[dict], summary: dict, meta: dict) -> None:
    rows = []
    for r in results:
        tc = r["test_case"]
        score = r["score"]
        criteria = "".join(f"<li>{_esc(c)}</li>" for c in tc.get("solution_criteria", []))
        rows.append(
            f"""
        <tr>
          <td>{_esc(tc.get('scenario', ''))}</td>
          <td><pre>{_esc(tc.get('prompt_inputs', {}))}</pre></td>
          <td><ul>{criteria}</ul></td>
          <td><pre class="output">{_esc(r.get('output', ''))}</pre></td>
          <td style="color:{_color(score)};font-weight:700;font-size:18px;text-align:center">{score}</td>
          <td>{_esc(r.get('reasoning', ''))}</td>
        </tr>"""
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Prompt Eval Report</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 24px; color: #1f2328; }}
  h1 {{ margin-bottom: 4px; }}
  .meta {{ color: #656d76; font-size: 13px; margin-bottom: 16px; }}
  .summary {{ display: flex; gap: 24px; margin: 16px 0 24px; }}
  .card {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 12px 20px; }}
  .card .num {{ font-size: 28px; font-weight: 700; }}
  .card .label {{ color: #656d76; font-size: 12px; text-transform: uppercase; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #d0d7de; padding: 8px; vertical-align: top; text-align: left; font-size: 13px; }}
  th {{ background: #f6f8fa; }}
  pre {{ white-space: pre-wrap; margin: 0; font-size: 12px; }}
  pre.output {{ max-height: 280px; overflow: auto; }}
</style>
</head>
<body>
  <h1>Prompt Evaluation Report</h1>
  <div class="meta">{_esc(meta.get('task_description', ''))}<br>
    dataset: {_esc(meta.get('dataset_file', ''))} &middot; judge: {_esc(meta.get('judge_model', ''))} &middot; run: {_esc(meta.get('run_label', ''))}</div>
  <div class="summary">
    <div class="card"><div class="num">{summary['total']}</div><div class="label">Test cases</div></div>
    <div class="card"><div class="num">{summary['average_score']}/10</div><div class="label">Average score</div></div>
    <div class="card"><div class="num">{summary['pass_rate']}%</div><div class="label">Pass rate (&ge;{config.PASS_THRESHOLD})</div></div>
  </div>
  <table>
    <thead><tr>
      <th>Scenario</th><th>Inputs</th><th>Criteria</th><th>Output</th><th>Score</th><th>Judge reasoning</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>"""
    Path(path).write_text(document, encoding="utf-8")
