"""MAS-TS-001 v5.0 — Compliance Report Formatters (Markdown / HTML)

Converts the structured federation compliance report dict into
human-readable Markdown or standalone HTML.
"""

from html import escape

from mas_eval.scoring.compliance_report import DOMAIN_NAMES

VERDICT_EMOJI = {"PASS": "✅", "NOTES": "📝", "REVIEW": "🔍", "BLOCKED": "🚫"}


def report_to_markdown(report):
    """Render a compliance report dict as GitHub-flavored Markdown."""
    lines = []
    lines.append("# Federation Compliance Report")
    lines.append("")
    lines.append(f"**Generated**: {report['generated_at']}  ")
    lines.append(f"**Report Version**: {report['report_version']}  ")
    lines.append("")

    s = report["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total Agents | {s['total_agents']} |")
    lines.append(f"| Passing | {s['agents_passing']} |")
    lines.append(f"| Blocked | {s['agents_blocked']} |")
    lines.append(f"| Needing Review | {s['agents_needing_review']} |")
    lines.append(f"| Federation Health | {s['federation_health']}/100 |")
    lines.append(f"| Total Gaps | {s['total_gaps']} |")
    lines.append(f"| Recommendations | {s['total_recommendations']} |")
    lines.append("")

    fed = report["federation"]
    lines.append("## Federation Overview")
    lines.append("")
    lines.append(f"- **Agent Count**: {fed['agent_count']}")
    lines.append(f"- **Compliance Rate**: {fed['compliance_rate']}")
    lines.append(f"- **Overall Health**: {fed['overall_health']}/100")
    lines.append("")
    lines.append("### Domain Averages")
    lines.append("")
    lines.append("| Domain | Average |")
    lines.append("|---|---|")
    for d, avg in fed["domain_averages"].items():
        name = DOMAIN_NAMES.get(d, d)
        lines.append(f"| {d} — {name} | {avg:.1f} |")
    lines.append("")

    lines.append("## Agent Details")
    lines.append("")
    for entry in report["agents"]:
        emoji = VERDICT_EMOJI.get(entry["verdict"], "❓")
        lines.append(f"### {emoji} {entry['name']}")
        lines.append("")
        lines.append(f"- **Agent ID**: `{entry['agent_id']}`")
        lines.append(f"- **Vendor**: {entry['vendor_id']}")
        lines.append(f"- **Schema Version**: {entry['schema_version']}")
        lines.append(f"- **Verdict**: {entry['verdict']}")
        lines.append("")
        fd = entry.get("federation_details", {})
        if fd:
            lines.append("#### Federation Details")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|---|---|")
            for k, v in fd.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")
        lines.append("#### Domain Scores")
        lines.append("")
        lines.append("| Domain | Score |")
        lines.append("|---|---|")
        for d, score in entry["scores"].items():
            name = DOMAIN_NAMES.get(d, d)
            bar = _score_bar(score)
            lines.append(f"| {d} — {name} | {score:.1f} {bar} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    gaps = report.get("gaps", [])
    if gaps:
        lines.append("## Gap Analysis")
        lines.append("")
        lines.append("| Severity | Description | Check | Agents |")
        lines.append("|---|---|---|---|")
        for g in gaps:
            agents = ", ".join(g.get("affected_agents", []))[:40]
            lines.append(
                f"| {g['severity']} | {g['description'][:60]} | "
                f"{g['check']} | {agents} |"
            )
        lines.append("")

    recs = report.get("recommendations", [])
    if recs:
        lines.append("## Recommendations")
        lines.append("")
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. {r}")
        lines.append("")

    return "\n".join(lines)


def report_to_html(report):
    """Render a compliance report dict as standalone HTML."""
    lines = []
    lines.append("<!DOCTYPE html>")
    lines.append('<html lang="en">')
    lines.append("<head>")
    lines.append('<meta charset="UTF-8">')
    lines.append("<title>Federation Compliance Report</title>")
    lines.append("<style>")
    lines.append("body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;")
    lines.append("max-width:960px;margin:2em auto;padding:0 1em;color:#333}")
    lines.append(
        "h1{color:#1a1a2e;border-bottom:2px solid #e0e0e0;padding-bottom:.3em}"
    )
    lines.append("h2{color:#16213e;margin-top:1.5em}")
    lines.append("h3{margin-top:1.2em}")
    lines.append("table{border-collapse:collapse;width:100%;margin:1em 0}")
    lines.append("th,td{border:1px solid #ddd;padding:8px 12px;text-align:left}")
    lines.append("th{background-color:#f5f5f5;font-weight:600}")
    lines.append("tr:nth-child(even){background-color:#fafafa}")
    lines.append(".severity-CRITICAL{color:#d32f2f;font-weight:700}")
    lines.append(".severity-HIGH{color:#f57c00;font-weight:600}")
    lines.append(".severity-WARNING{color:#fbc02d}")
    lines.append(".score-bar{display:inline-block;height:10px;")
    lines.append("border-radius:5px;margin-left:6px;vertical-align:middle}")
    lines.append(".verdict-PASS{color:#2e7d32;font-weight:700}")
    lines.append(".verdict-NOTES{color:#1565c0}")
    lines.append(".verdict-REVIEW{color:#e65100}")
    lines.append(".verdict-BLOCKED{color:#d32f2f;font-weight:700}")
    lines.append(".summary-grid{display:grid;grid-template-columns:repeat(auto-fit,")
    lines.append("minmax(200px,1fr));gap:12px;margin:1em 0}")
    lines.append(".summary-card{background:#f8f9fa;border-radius:8px;")
    lines.append("padding:16px;text-align:center}")
    lines.append(".summary-card .value{font-size:1.8em;font-weight:700;color:#1a1a2e}")
    lines.append(".summary-card .label{font-size:.85em;color:#666}")
    lines.append("hr{border:none;border-top:1px solid #e0e0e0;margin:1.5em 0}")
    lines.append("</style>")
    lines.append("</head>")
    lines.append("<body>")

    s = report["summary"]
    lines.append("<h1>Federation Compliance Report</h1>")
    lines.append(
        f"<p><strong>Generated:</strong> {report['generated_at']} | "
        f"<strong>Version:</strong> {report['report_version']}</p>"
    )
    lines.append("<div class='summary-grid'>")
    lines.append(
        f"<div class='summary-card'><div class='value'>{s['total_agents']}</div>"
        f"<div class='label'>Total Agents</div></div>"
    )
    lines.append(
        f"<div class='summary-card'><div class='value'>{s['agents_passing']}</div>"
        f"<div class='label'>Passing</div></div>"
    )
    lines.append(
        f"<div class='summary-card'><div class='value' style='color:#d32f2f'>"
        f"{s['agents_blocked']}</div><div class='label'>Blocked</div></div>"
    )
    lines.append(
        f"<div class='summary-card'><div class='value'>{s['federation_health']}"
        f"</div><div class='label'>Health</div></div>"
    )
    lines.append(
        f"<div class='summary-card'><div class='value'>{s['total_gaps']}</div>"
        f"<div class='label'>Gaps</div></div>"
    )
    lines.append(
        f"<div class='summary-card'><div class='value'>{s['total_recommendations']}"
        f"</div><div class='label'>Recommendations</div></div>"
    )
    lines.append("</div>")

    lines.append("<h2>Federation Overview</h2>")
    fed = report["federation"]
    lines.append(
        f"<p>Compliance Rate: <strong>{fed['compliance_rate']}</strong> | "
        f"Health: <strong>{fed['overall_health']}/100</strong></p>"
    )
    lines.append("<table><tr><th>Domain</th><th>Average</th></tr>")
    for d, avg in fed["domain_averages"].items():
        name = DOMAIN_NAMES.get(d, d)
        lines.append(f"<tr><td>{d} — {name}</td><td>{avg:.1f}</td></tr>")
    lines.append("</table>")

    lines.append("<h2>Agent Details</h2>")
    for entry in report["agents"]:
        emoji = VERDICT_EMOJI.get(entry["verdict"], "")
        verdict = escape(str(entry["verdict"]))
        vcls = f"verdict-{verdict}"
        lines.append(f"<h3>{emoji} {escape(str(entry['name']))}</h3>")
        lines.append(
            f"<p><strong>Verdict:</strong> "
            f"<span class='{vcls}'>{verdict}</span> | "
            f"<strong>Vendor:</strong> {escape(str(entry['vendor_id']))} | "
            f"<strong>Schema:</strong> {escape(str(entry['schema_version']))}</p>"
        )
        fd = entry.get("federation_details", {})
        if fd:
            lines.append("<table><tr><th>Metric</th><th>Value</th></tr>")
            for k, v in fd.items():
                lines.append(
                    f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>"
                )
            lines.append("</table>")
        lines.append("<table><tr><th>Domain</th><th>Score</th></tr>")
        for d, score in entry["scores"].items():
            name = DOMAIN_NAMES.get(d, d)
            bar = _score_bar(score)
            lines.append(
                f"<tr><td>{escape(str(d))} — {escape(str(name))}</td><td>{score:.1f} {bar}</td></tr>"
            )
        lines.append("</table><hr>")

    gaps = report.get("gaps", [])
    if gaps:
        lines.append("<h2>Gap Analysis</h2><table>")
        lines.append(
            "<tr><th>Severity</th><th>Description</th>"
            "<th>Check</th><th>Agents</th></tr>"
        )
        for g in gaps:
            sev = escape(str(g["severity"]))
            agents = ", ".join(str(a) for a in g.get("affected_agents", []))[:40]
            lines.append(
                f"<tr class='severity-{sev}'><td>{sev}</td>"
                f"<td>{escape(str(g['description'])[:60])}</td>"
                f"<td>{escape(str(g['check']))}</td><td>{escape(agents)}</td></tr>"
            )
        lines.append("</table>")

    recs = report.get("recommendations", [])
    if recs:
        lines.append("<h2>Recommendations</h2><ol>")
        for r in recs:
            lines.append(f"<li>{escape(str(r))}</li>")
        lines.append("</ol>")

    lines.append("</body></html>")
    return "\n".join(lines)


def _score_bar(score):
    blocks = int(score / 10)
    return "█" * blocks + "░" * (10 - blocks)


def format_report(report, fmt="markdown"):
    if fmt == "markdown":
        return report_to_markdown(report)
    elif fmt == "html":
        return report_to_html(report)
    msg = f"Unknown format: {fmt!r} (use 'markdown' or 'html')"
    raise ValueError(msg)
