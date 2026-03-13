"""Export module - exports leads and reports to CSV and JSON."""

import csv
import json
from pathlib import Path


def export_csv(leads, filepath, analysis=None):
    """Export leads to a CSV file."""
    filepath = Path(filepath)
    fieldnames = [
        "rank", "name", "website", "relevance_score", "buyer_type",
        "emails", "phone", "linkedin", "twitter",
        "technologies", "description", "reasons",
        "score_breakdown", "matched_queries",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, lead in enumerate(leads, 1):
            breakdown = lead.get("score_breakdown", {})
            bd_str = "; ".join(f"{k}={v}" for k, v in breakdown.items()) if breakdown else ""
            writer.writerow({
                "rank": i,
                "name": lead.get("name", ""),
                "website": lead.get("website", ""),
                "relevance_score": lead.get("relevance_score", 0),
                "buyer_type": lead.get("buyer_type", ""),
                "emails": "; ".join(lead.get("emails", [])),
                "phone": "; ".join(lead.get("phones", [])) if lead.get("phones") else "",
                "linkedin": lead.get("social", {}).get("linkedin", ""),
                "twitter": lead.get("social", {}).get("twitter", ""),
                "technologies": "; ".join(lead.get("technologies", [])),
                "description": lead.get("description", "") or lead.get("snippet", ""),
                "reasons": " | ".join(lead.get("relevance_reasons", [])),
                "score_breakdown": bd_str,
                "matched_queries": "; ".join(lead.get("matched_queries", [])),
            })

    return str(filepath)


def export_json(leads, filepath, analysis=None):
    """Export leads and analysis to a JSON file."""
    filepath = Path(filepath)
    data = {
        "domain_analysis": analysis,
        "leads": leads,
        "total_leads": len(leads),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    return str(filepath)


def export(leads, filepath, analysis=None):
    """Auto-detect format and export."""
    filepath = str(filepath)
    if filepath.endswith(".json"):
        return export_json(leads, filepath, analysis)
    else:
        return export_csv(leads, filepath, analysis)
