# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Beautiful HTML report generator for MAS-TS-001 Gold Standard.

Generates a self-contained, design-friendly HTML report page with:
- Gold Standard certification badge
- Domain score cards with visual indicators
- Test execution summary
- Coverage breakdown
- Findings timeline

Usage:
    python -m mas_eval.reporting.html_report --output reports/gold-report.html
"""

import argparse
import datetime
import os
from pathlib import Path
from typing import Any

from mas_eval.reporting.gold_report import generate_report as _generate_data

REPORT_DIR = "reports"


def _grade_color(grade: str) -> str:
    colors = {
        "A+": "#1a7f37",
        "A": "#1a7f37",
        "A-": "#1a7f37",
        "B+": "#9a6700",
        "B": "#9a6700",
        "B-": "#9a6700",
        "C+": "#bf8700",
        "C": "#bf8700",
        "C-": "#bf8700",
        "D+": "#cf222e",
        "D": "#cf222e",
        "D-": "#cf222e",
    }
    return colors.get(grade, "#cf222e")


def _verdict_badge(verdict: str) -> str:
    badges = {
        "GOLD": '<span style="background:#d4af37;color:#1a1a2e;padding:4px 16px;border-radius:20px;font-weight:700;font-size:14px">★ GOLD</span>',
        "SILVER": '<span style="background:#c0c0c0;color:#1a1a2e;padding:4px 16px;border-radius:20px;font-weight:700;font-size:14px">◆ SILVER</span>',
        "BRONZE": '<span style="background:#cd7f32;color:#fff;padding:4px 16px;border-radius:20px;font-weight:700;font-size:14px">● BRONZE</span>',
    }
    return badges.get(
        verdict,
        '<span style="background:#cf222e;color:#fff;padding:4px 16px;border-radius:20px;font-weight:700;font-size:14px">✗ FAIL</span>',
    )


def _score_bar(score: float, threshold: float) -> str:
    pct = min(100, score / max(threshold, 1) * 100)
    color = (
        "#1a7f37"
        if score >= threshold
        else "#cf222e"
        if score < threshold * 0.8
        else "#9a6700"
    )
    return f"""
    <div style="background:#e8e8e8;border-radius:8px;height:8px;margin:8px 0;overflow:hidden">
      <div style="width:{pct}%;height:100%;background:{color};border-radius:8px;transition:width 1s ease"></div>
    </div>"""


def _compliance_level_stars(level: str) -> str:
    stars = {"GOLD": "⭐⭐⭐", "SILVER": "⭐⭐", "BRONZE": "⭐", "FAIL": "—"}
    return stars.get(level, "—")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MAS-TS-001 Gold Standard Report — {agent_id}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    color: #e0e0e0;
    min-height: 100vh;
    padding: 40px 20px;
  }}
  .container {{ max-width: 960px; margin: 0 auto }}
  .card {{
    background: rgba(255,255,255,0.06);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 24px;
    transition: transform 0.2s, box-shadow 0.2s;
  }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.3) }}
  .cert-header {{
    text-align: center;
    padding: 40px 32px;
    background: linear-gradient(135deg, rgba(212,175,55,0.15) 0%, rgba(255,255,255,0.05) 100%);
    border: 2px solid rgba(212,175,55,0.3);
  }}
  .cert-header h1 {{ font-size: 28px; color: #d4af37; margin-bottom: 8px; letter-spacing: 2px }}
  .cert-header .subtitle {{ color: #a0a0a0; font-size: 14px; margin-bottom: 16px }}
  .cert-meta {{ display: flex; justify-content: center; gap: 40px; flex-wrap: wrap; margin-top: 20px }}
  .cert-meta-item {{ text-align: center }}
  .cert-meta-item .label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px }}
  .cert-meta-item .value {{ font-size: 24px; font-weight: 700; margin-top: 4px }}
  .domain-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px }}
  .domain-card {{
    background: rgba(255,255,255,0.04);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    border: 1px solid rgba(255,255,255,0.06);
  }}
  .domain-card .name {{ font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 1px }}
  .domain-card .score {{ font-size: 32px; font-weight: 800; margin: 8px 0 }}
  .domain-card .threshold {{ font-size: 12px; color: #666 }}
  .findings-list {{ list-style: none }}
  .findings-list li {{
    display: flex; align-items: center; gap: 12px;
    padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.06);
  }}
  .findings-list li:last-child {{ border-bottom: none }}
  .severity-tag {{ padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; min-width: 70px; text-align: center }}
  .exec-table {{ width: 100%; border-collapse: collapse }}
  .exec-table td {{ padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.06) }}
  .exec-table td:first-child {{ color: #888; width: 140px }}
  .exec-table tr:last-child td {{ border-bottom: none }}
  .progress-ring {{ display: inline-flex; align-items: center; justify-content: center }}
  .grade-circle {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 80px; height: 80px; border-radius: 50%;
    font-size: 28px; font-weight: 800; color: #fff;
  }}
  footer {{ text-align: center; padding: 20px; color: #555; font-size: 12px }}
  @media (max-width: 600px) {{
    .domain-grid {{ grid-template-columns: repeat(2, 1fr) }}
    .cert-meta {{ gap: 20px }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="card cert-header">
    <h1>★ MAS-TS-001 GOLD</h1>
    <div class="subtitle">Multi-Agent System Test Standard — Gold Standard Certification</div>
    <div style="margin:8px 0">{verdict_badge}</div>
    <div style="font-size:32px;margin:12px 0">{compliance_stars}</div>
    <div class="cert-meta">
      <div class="cert-meta-item"><div class="label">Agent</div><div class="value" style="font-size:18px">{agent_id}</div></div>
      <div class="cert-meta-item"><div class="label">Score</div><div class="value" style="color:{grade_color}">{score:.1f}</div></div>
      <div class="cert-meta-item"><div class="label">Grade</div><div class="value" style="color:{grade_color}">{grade}</div></div>
    </div>
  </div>

  <!-- Domain Scores -->
  <div class="card">
    <h2 style="font-size:18px;margin-bottom:20px;color:#ccc">Domain Scores</h2>
    <div class="domain-grid">
      {domain_cards}
    </div>
  </div>

  <!-- Execution -->
  <div class="card">
    <h2 style="font-size:18px;margin-bottom:20px;color:#ccc">Execution Summary</h2>
    <table class="exec-table">
      <tr><td>Timestamp</td><td>{timestamp}</td></tr>
      <tr><td>Duration</td><td>{duration_ms} ms</td></tr>
      <tr><td>Tests</td><td>{tests_passed} / {tests_total} passed</td></tr>
      <tr><td>Coverage</td><td>{coverage_pct:.2f}%</td></tr>
      <tr><td>Level</td><td>{level}</td></tr>
      <tr><td>Consistency Index</td><td>{ci_str}</td></tr>
      <tr><td>Cost Efficiency</td><td>{ce_str}</td></tr>
      <tr><td>Certificate ID</td><td style="font-family:monospace;font-size:12px">{cert_id}</td></tr>
    </table>
  </div>

  <!-- Findings -->
  {findings_section}

  <footer>
    MAS-TS-001 Gold Standard · Generated {generated_at} · Valid until {valid_until}
  </footer>
</div>
</body>
</html>"""


def generate_html_report(
    agent_id: str = "agent-unknown",
    domain_scores: dict[str, float] | None = None,
    level: str = "L3",
    findings: list[dict[str, Any]] | None = None,
    consistency_index: float | None = None,
    cost_efficiency: float | None = None,
    execution_metadata: dict[str, Any] | None = None,
) -> str:
    """Generate a beautiful self-contained HTML report.

    Returns:
        HTML string.
    """
    domain_scores = domain_scores or {}
    findings = findings or []
    execution_metadata = execution_metadata or {}

    data = _generate_data(
        agent_id=agent_id,
        domain_scores=domain_scores,
        level=level,
        findings=findings,
        consistency_index=consistency_index,
        cost_efficiency=cost_efficiency,
        execution_metadata=execution_metadata,
    )

    cert = data.get("certificate", {})
    dims = data.get("dimensions", {})
    exec_info = data.get("execution", {})

    score = cert.get("score", 0)
    grade = cert.get("grade", "F")
    verdict = cert.get("verdict", "FAIL")
    compliance = cert.get("compliance_level", "FAIL")

    domain_cards = ""
    for dom_key in sorted(dims.keys()):
        d = dims[dom_key]
        sc = d["score"]
        th = d["threshold"]
        color = "#1a7f37" if d["passed"] else "#cf222e"
        domain_cards += f"""
    <div class="domain-card">
      <div class="name">{dom_key.upper()}</div>
      <div class="score" style="color:{color}">{sc:.1f}</div>
      <div class="threshold">threshold: {th:.0f}</div>
      {_score_bar(sc, th)}
    </div>"""

    findings_rows = ""
    for f in findings:
        sev = f.get("severity", "INFO")
        detail = f.get("detail", "")
        colors = {
            "CRITICAL": "#cf222e",
            "HIGH": "#9a6700",
            "WARNING": "#bf8700",
            "INFO": "#555",
        }
        sc = colors.get(sev, "#555")
        findings_rows += f"""
    <li>
      <span class="severity-tag" style="background:{sc}20;color:{sc};border:1px solid {sc}40">{sev}</span>
      <span>{detail}</span>
    </li>"""

    findings_section = ""
    if findings_rows:
        findings_section = f"""
  <div class="card">
    <h2 style="font-size:18px;margin-bottom:20px;color:#ccc">Findings ({len(findings)})</h2>
    <ul class="findings-list">{findings_rows}
    </ul>
  </div>"""

    now = datetime.datetime.now()
    valid_until_str = cert.get("valid_until", "N/A")
    ci_str = f"{consistency_index:.2f}" if consistency_index is not None else "N/A"
    ce_str = f"{cost_efficiency:.2f}" if cost_efficiency is not None else "N/A"

    return HTML_TEMPLATE.format(
        agent_id=agent_id,
        grade_color=_grade_color(grade),
        verdict_badge=_verdict_badge(verdict),
        compliance_stars=_compliance_level_stars(compliance),
        score=score,
        grade=grade,
        domain_cards=domain_cards,
        timestamp=str(exec_info.get("timestamp", "N/A")),
        duration_ms=exec_info.get("duration_ms", 0),
        tests_passed=exec_info.get("tests_passed", 0),
        tests_total=exec_info.get("tests_total", 0),
        coverage_pct=exec_info.get("coverage_pct", 0.0),
        level=exec_info.get("level", level),
        ci_str=ci_str,
        ce_str=ce_str,
        cert_id=cert.get("cert_id", ""),
        findings_section=findings_section,
        generated_at=now.strftime("%Y-%m-%d %H:%M"),
        valid_until=valid_until_str,
    )


def save_html_report(
    html: str,
    output_path: str | None = None,
    agent_id: str = "unknown",
) -> str:
    if output_path is None:
        output_path = os.path.join(REPORT_DIR, f"gold-report-{agent_id}.html")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return os.path.abspath(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate MAS-TS-001 Gold Standard HTML Report"
    )
    parser.add_argument("--agent-id", default="agent-001")
    parser.add_argument("--output", "-o", help="Output HTML file path")
    parser.add_argument("--level", default="L3")
    parser.add_argument("--ci", type=float, help="Consistency Index")
    parser.add_argument("--ce", type=float, help="Cost Efficiency")
    args = parser.parse_args()

    domain_scores = {"d1": 95.0, "d2": 88.0, "d3": 82.0, "d4": 76.0, "d5": 91.0}
    findings = [
        {
            "severity": "WARNING",
            "category": "performance",
            "detail": "Step efficiency slightly below L3 threshold",
        },
        {
            "severity": "INFO",
            "category": "coverage",
            "detail": "D4 action safety coverage needs improvement",
        },
    ]
    metadata = {
        "duration_ms": 3456,
        "tests_passed": 1569,
        "tests_total": 1569,
        "coverage_pct": 93.17,
    }

    html = generate_html_report(
        agent_id=args.agent_id,
        domain_scores=domain_scores,
        level=args.level,
        findings=findings,
        consistency_index=args.ci,
        cost_efficiency=args.ce,
        execution_metadata=metadata,
    )
    path = save_html_report(html, args.output, args.agent_id)
    print(f"Report saved to: {path}")


if __name__ == "__main__":
    main()
