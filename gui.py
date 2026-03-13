#!/usr/bin/env python3
"""Domain Seller — Web GUI with real-time progress."""

import csv
import io
import json
import os
import queue
import re
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, date
from pathlib import Path

_tasks_lock = threading.Lock()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from flask import Flask, render_template, request, Response, jsonify
except ImportError:
    print("\n  Flask is required for the GUI. Install it:\n    pip install flask\n")
    sys.exit(1)

from core.config import Config
from core.analyzer import DomainAnalyzer
from core.researcher_v2 import BuyerResearcher
from core.lead_scorer import LeadScorer
from core.outreach import generate_outreach_email, generate_all_templates
from core.html_report import generate_html_report
from core.history import check_domain_history
from core.social_checker import check_social_handles
from core.market_comp import find_comparable_sales
from core.validators import validate_domain, ValidationError

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())
tasks = {}
_MAX_TASK_AGE = 1800  # 30 minutes
_MAX_CONCURRENT_TASKS = 10  # prevent resource exhaustion


def _cleanup_old_tasks():
    """Remove completed tasks older than _MAX_TASK_AGE seconds."""
    now = datetime.now()
    with _tasks_lock:
        to_remove = [
            tid for tid, t in tasks.items()
            if t.get("status") == "done"
            and (now - t.get("created", now)).total_seconds() > _MAX_TASK_AGE
        ]
        for tid in to_remove:
            del tasks[tid]


def _jsonable(obj):
    """Recursively convert to JSON-safe types."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if not isinstance(obj, (str, int, float, bool, type(None))):
        return str(obj)
    return obj


# ── Routes ──────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def api_start():
    raw_domain = (request.json or {}).get("domain", "").strip()
    if not raw_domain:
        return jsonify(error="No domain provided"), 400

    try:
        domain = validate_domain(raw_domain)
    except ValidationError as e:
        return jsonify(error=str(e)), 400

    _cleanup_old_tasks()

    # Prevent resource exhaustion
    with _tasks_lock:
        running = sum(1 for t in tasks.values() if t.get("status") == "running")
        if running >= _MAX_CONCURRENT_TASKS:
            return jsonify(error="Too many concurrent tasks. Please wait."), 429

    tid = uuid.uuid4().hex[:8]
    with _tasks_lock:
        tasks[tid] = {
            "q": queue.Queue(),
            "results": {},
            "status": "running",
            "domain": domain,
            "created": datetime.now(),
        }
    threading.Thread(target=_run_pipeline, args=(tid, domain), daemon=True).start()
    return jsonify(task_id=tid)


@app.route("/api/stream/<tid>")
def api_stream(tid):
    if tid not in tasks:
        return jsonify(error="Not found"), 404

    def gen():
        q = tasks[tid]["q"]
        while True:
            try:
                msg = q.get(timeout=60)
            except queue.Empty:
                yield 'data: {"type":"ping"}\n\n'
                continue
            yield f"data: {json.dumps(msg, default=str)}\n\n"
            if msg.get("type") in ("done", "error"):
                break

    return Response(
        gen(), mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/results/<tid>")
def api_results(tid):
    if tid not in tasks:
        return jsonify(error="Not found"), 404
    return jsonify(_jsonable(tasks[tid]["results"]))


@app.route("/api/email/<tid>/<int:idx>")
def api_email(tid, idx):
    t = tasks.get(tid)
    if not t or "leads" not in t["results"]:
        return jsonify(error="Not found"), 404
    leads, analysis = t["results"]["leads"], t["results"]["analysis"]
    if not 0 <= idx < len(leads):
        return jsonify(error="Bad index"), 400
    return jsonify(generate_outreach_email(leads[idx], analysis))


@app.route("/api/all-emails/<tid>/<int:idx>")
def api_all_emails(tid, idx):
    t = tasks.get(tid)
    if not t or "leads" not in t["results"]:
        return jsonify(error="Not found"), 404
    leads, analysis = t["results"]["leads"], t["results"]["analysis"]
    if not 0 <= idx < len(leads):
        return jsonify(error="Bad index"), 400
    return jsonify(generate_all_templates(leads[idx], analysis))


@app.route("/api/export/<tid>/<fmt>")
def api_export(tid, fmt):
    if fmt not in ("html", "json", "csv"):
        return jsonify(error="Invalid format. Use: html, json, csv"), 400
    t = tasks.get(tid)
    if not t or "leads" not in t["results"]:
        return jsonify(error="Not found"), 404
    leads, analysis = t["results"]["leads"], t["results"]["analysis"]
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", t["domain"])

    if fmt == "html":
        content = generate_html_report(leads, analysis)
        return Response(content, mimetype="text/html",
                        headers={"Content-Disposition": f"attachment; filename=report_{safe}.html"})

    if fmt == "json":
        data = json.dumps({"analysis": _jsonable(analysis), "leads": _jsonable(leads)},
                          indent=2, default=str)
        return Response(data, mimetype="application/json",
                        headers={"Content-Disposition": f"attachment; filename=leads_{safe}.json"})

    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["rank", "name", "website", "score", "buyer_type", "emails", "phone",
                     "linkedin", "twitter", "description", "reasons",
                     "location", "technologies", "score_breakdown"])
        for i, l in enumerate(leads, 1):
            bd = l.get("score_breakdown", {})
            bd_str = "; ".join(f"{k}={v}" for k, v in bd.items()) if bd else ""
            w.writerow([
                i, l.get("name", ""), l.get("website", ""),
                l.get("relevance_score", 0), l.get("buyer_type", ""),
                "; ".join(l.get("emails", [])), l.get("phone", ""),
                l.get("social", {}).get("linkedin", ""),
                l.get("social", {}).get("twitter", ""),
                l.get("description", ""),
                " | ".join(l.get("relevance_reasons", [])),
                l.get("location", ""),
                ", ".join(l.get("technologies", [])),
                bd_str,
            ])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=leads_{safe}.csv"})

    return jsonify(error="Invalid format"), 400


# ── Pipeline ────────────────────────────────────────────────────────────


def _run_pipeline(tid, domain):
    q = tasks[tid]["q"]
    res = tasks[tid]["results"]

    try:
        q.put({"type": "step", "step": "analysis", "msg": f"Analyzing {domain}..."})
        analysis = DomainAnalyzer(domain).analyze()
        ca = _jsonable(analysis)
        res["analysis"] = ca
        q.put({"type": "analysis_done", "data": ca})

        # Wayback Machine history check
        q.put({"type": "progress", "step": "analysis", "msg": "Checking domain history (Wayback Machine)..."})
        history = check_domain_history(domain)
        ca["history"] = _jsonable(history)
        analysis["history"] = history
        q.put({"type": "progress", "step": "analysis", "msg": f"History: {history.get('total_snapshots', 0)} snapshots found"})

        # Social handle availability
        q.put({"type": "progress", "step": "analysis", "msg": "Checking social media handles..."})
        social = check_social_handles(analysis["name"])
        ca["social_handles"] = _jsonable(social)
        analysis["social_handles"] = social
        q.put({"type": "progress", "step": "analysis", "msg": social.get("summary", "")})

        # Marketplace price comparison
        q.put({"type": "progress", "step": "analysis", "msg": "Searching marketplace comparables..."})
        market = find_comparable_sales(analysis["name"], analysis["tld"], analysis["keywords"])
        ca["market_comp"] = _jsonable(market)
        analysis["market_comp"] = market
        q.put({"type": "progress", "step": "analysis", "msg": market.get("market_summary", "")})

        # Push updated analysis with all enrichments
        res["analysis"] = ca
        q.put({"type": "analysis_enriched", "data": ca})

        cfg = Config()

        def pcb(msg, **kw):
            q.put({"type": "progress", "step": kw.get("step", ""),
                    "msg": msg, "cur": kw.get("current"), "tot": kw.get("total")})

        q.put({"type": "step", "step": "search", "msg": "Searching for potential buyers..."})
        raw = BuyerResearcher(cfg, analysis, progress_callback=pcb).research()

        q.put({"type": "step", "step": "scoring", "msg": f"Scoring {len(raw)} leads..."})
        scored = LeadScorer(analysis).score_and_rank(raw)
        scored = [l for l in scored if l.get("relevance_score", 0) >= 20][:30]
        res["leads"] = _jsonable(scored)

        q.put({
            "type": "done",
            "count": len(scored),
            "hot": sum(1 for l in scored if l.get("relevance_score", 0) >= 70),
            "warm": sum(1 for l in scored if 50 <= l.get("relevance_score", 0) < 70),
            "cold": sum(1 for l in scored if l.get("relevance_score", 0) < 50),
            "emails": sum(1 for l in scored if l.get("emails")),
            "phones": sum(1 for l in scored if l.get("phone")),
            "buyer_types": _count_buyer_types(scored),
        })
    except Exception as exc:
        import traceback
        traceback.print_exc()
        q.put({"type": "error", "msg": str(exc)})
    tasks[tid]["status"] = "done"


def _count_buyer_types(leads):
    counts = {}
    for l in leads:
        bt = l.get("buyer_type", "general")
        counts[bt] = counts.get(bt, 0) + 1
    return counts


# ── Main ────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    url = f"http://localhost:{port}"
    print(f"\n  Domain Seller GUI  ➜  {url}\n")
    threading.Thread(
        target=lambda: (__import__("time").sleep(1.5), webbrowser.open(url)),
        daemon=True,
    ).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
