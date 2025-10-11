#!/usr/bin/env python3
"""
Metrics Dashboard - Weekly Performance Report
PRIORITY: P2 - Observability for production monitoring.

Task 11: Observability Dashboard
Generates comprehensive weekly reports for pipeline health.

Usage:
    python scripts/metrics_dashboard.py --period weekly
    python scripts/metrics_dashboard.py --period daily --output report.md
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.metrics import MetricsCollector
from src.utils.cache import get_cache


def generate_markdown_report(data: Dict[str, Any], period: str) -> str:
    """
    Generate Markdown report from metrics data.

    Args:
        data: Metrics data dictionary
        period: Report period (daily, weekly, monthly)

    Returns:
        Markdown-formatted report string
    """
    report = []

    # Header
    report.append(f"# Lead Generation Pipeline - {period.capitalize()} Report")
    report.append(f"**Generated**: {data['generated_at']}")
    report.append(f"**Period**: {data['period_hours']} hours")
    report.append("")

    # Overall Pipeline Metrics
    report.append("## 📊 Overall Pipeline Metrics")
    report.append("")
    if data.get('pipeline_metrics'):
        pm = data['pipeline_metrics']
        report.append(f"- **Leads Processed**: {pm.get('leads_processed', 0):.0f}")
        report.append(f"- **Qualified Leads**: {pm.get('qualified_leads', 0):.0f}")
        report.append(f"- **Disqualified Leads**: {pm.get('disqualified_leads', 0):.0f}")
        report.append(f"- **Leads in Review**: {pm.get('review_required', 0):.0f}")
        if pm.get('leads_processed', 0) > 0:
            qual_rate = pm.get('qualified_leads', 0) / pm.get('leads_processed', 1) * 100
            report.append(f"- **Qualification Rate**: {qual_rate:.1f}%")
    else:
        report.append("*No pipeline metrics available*")
    report.append("")

    # Gate Performance
    report.append("## 🚪 Gate Performance")
    report.append("")
    if data.get('gate_performance'):
        report.append("| Gate | Total | Passed | Failed | Pass Rate |")
        report.append("|------|-------|--------|--------|-----------|")
        for gate_name, stats in sorted(data['gate_performance'].items()):
            pass_rate = stats['pass_rate'] * 100
            status = "✅" if pass_rate >= 70 else "⚠️" if pass_rate >= 50 else "❌"
            report.append(
                f"| {status} {gate_name.capitalize()} | "
                f"{stats['total']} | {stats['passed']} | {stats['failed']} | "
                f"{pass_rate:.1f}% |"
            )
    else:
        report.append("*No gate performance data available*")
    report.append("")

    # API Health
    report.append("## 🔌 API Health")
    report.append("")
    if data.get('api_health'):
        report.append("| API | Calls | Avg Latency | Errors | Success Rate |")
        report.append("|-----|-------|-------------|--------|--------------|")
        for api_name, stats in sorted(data['api_health'].items()):
            success_rate = stats.get('success_rate', 1.0) * 100
            errors = stats.get('errors', 0)
            status = "✅" if success_rate >= 95 else "⚠️" if success_rate >= 85 else "❌"
            report.append(
                f"| {status} {api_name.capitalize()} | "
                f"{stats['total_calls']} | {stats['avg_latency_ms']:.1f}ms | "
                f"{errors} | {success_rate:.1f}% |"
            )
    else:
        report.append("*No API health data available*")
    report.append("")

    # Cache Performance
    report.append("## 💾 Cache Performance")
    report.append("")
    if data.get('cache_stats'):
        cs = data['cache_stats']
        report.append(f"- **Total Entries**: {cs.get('total_entries', 0)}")
        report.append(f"- **Cache Hits**: {cs.get('hits', 0)}")
        report.append(f"- **Cache Misses**: {cs.get('misses', 0)}")
        if cs.get('hits', 0) + cs.get('misses', 0) > 0:
            hit_rate = cs.get('hit_rate', 0) * 100
            report.append(f"- **Hit Rate**: {hit_rate:.1f}%")
        report.append("")
        if cs.get('cost_savings'):
            report.append(f"**Estimated Cost Savings**: ${cs['cost_savings']:.2f}")
    else:
        report.append("*No cache data available*")
    report.append("")

    # Top Rejection Reasons
    report.append("## ⚠️ Top Rejection Reasons")
    report.append("")
    if data.get('top_rejections'):
        for i, (reason, count) in enumerate(data['top_rejections'][:10], 1):
            report.append(f"{i}. **{reason}**: {count} occurrences")
    else:
        report.append("*No rejection data available*")
    report.append("")

    # Recommendations
    report.append("## 💡 Recommendations")
    report.append("")
    recommendations = generate_recommendations(data)
    if recommendations:
        for rec in recommendations:
            report.append(f"- {rec}")
    else:
        report.append("*Pipeline performing within normal parameters*")
    report.append("")

    return "\n".join(report)


def generate_recommendations(data: Dict[str, Any]) -> List[str]:
    """
    Generate recommendations based on metrics data.

    Args:
        data: Metrics data dictionary

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Check gate performance
    if data.get('gate_performance'):
        for gate_name, stats in data['gate_performance'].items():
            pass_rate = stats['pass_rate']
            if pass_rate < 0.50:
                recommendations.append(
                    f"⚠️ {gate_name.capitalize()} gate has low pass rate ({pass_rate*100:.1f}%). "
                    f"Review criteria or data quality."
                )
            elif pass_rate > 0.95:
                recommendations.append(
                    f"✅ {gate_name.capitalize()} gate is performing well ({pass_rate*100:.1f}% pass rate)."
                )

    # Check API health
    if data.get('api_health'):
        for api_name, stats in data['api_health'].items():
            success_rate = stats.get('success_rate', 1.0)
            if success_rate < 0.85:
                recommendations.append(
                    f"❌ {api_name.capitalize()} API has low success rate ({success_rate*100:.1f}%). "
                    f"Check for rate limiting or service issues."
                )

            avg_latency = stats.get('avg_latency_ms', 0)
            if avg_latency > 2000:
                recommendations.append(
                    f"⚠️ {api_name.capitalize()} API latency is high ({avg_latency:.0f}ms). "
                    f"Consider caching or optimization."
                )

    # Check cache performance
    if data.get('cache_stats'):
        hit_rate = data['cache_stats'].get('hit_rate', 0)
        if hit_rate < 0.30:
            recommendations.append(
                f"💾 Cache hit rate is low ({hit_rate*100:.1f}%). "
                f"Review TTL settings or cache key generation."
            )
        elif hit_rate > 0.60:
            recommendations.append(
                f"✅ Cache performing well ({hit_rate*100:.1f}% hit rate). "
                f"Estimated savings: ${data['cache_stats'].get('cost_savings', 0):.2f}"
            )

    # Check pipeline metrics
    if data.get('pipeline_metrics'):
        pm = data['pipeline_metrics']
        leads_processed = pm.get('leads_processed', 0)
        if leads_processed == 0:
            recommendations.append(
                "⚠️ No leads processed in this period. Check data sources."
            )
        else:
            qual_rate = pm.get('qualified_leads', 0) / leads_processed
            if qual_rate < 0.10:
                recommendations.append(
                    f"⚠️ Low qualification rate ({qual_rate*100:.1f}%). "
                    f"Review gate criteria or data source quality."
                )

    return recommendations


def collect_metrics_data(period_hours: int) -> Dict[str, Any]:
    """
    Collect all metrics data for report.

    Args:
        period_hours: Hours of history to include

    Returns:
        Dictionary of metrics data
    """
    metrics = MetricsCollector.get_instance()

    # Gate performance
    gate_performance = metrics.get_gate_performance(hours=period_hours)

    # API health
    api_health = metrics.get_api_health(hours=period_hours)

    # Pipeline metrics
    pipeline_metrics = {}
    for metric_name in ['leads_processed', 'qualified_leads', 'disqualified_leads', 'review_required']:
        stats = metrics.get_metric_stats(f'pipeline.{metric_name}', hours=period_hours)
        if stats.get('latest') is not None:
            pipeline_metrics[metric_name] = stats['latest']

    # Cache stats
    try:
        cache = get_cache()
        cache_stats = cache.get_stats()

        # Estimate cost savings
        # Assume: Places API = $0.017/call, OpenAI = $0.001/call
        hits = cache_stats.get('hits', 0)
        cost_savings = hits * 0.009  # Average cost per cached call
        cache_stats['cost_savings'] = cost_savings
    except Exception as e:
        cache_stats = {"error": str(e)}

    # Top rejection reasons (would need to track these separately)
    top_rejections = []

    return {
        'generated_at': datetime.utcnow().isoformat(),
        'period_hours': period_hours,
        'gate_performance': gate_performance,
        'api_health': api_health,
        'pipeline_metrics': pipeline_metrics,
        'cache_stats': cache_stats,
        'top_rejections': top_rejections
    }


def main():
    """Main entry point for metrics dashboard."""
    parser = argparse.ArgumentParser(
        description="Generate metrics dashboard report",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--period',
        choices=['daily', 'weekly', 'monthly'],
        default='weekly',
        help='Report period (default: weekly)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file path (default: print to stdout)'
    )

    parser.add_argument(
        '--format',
        choices=['markdown', 'json'],
        default='markdown',
        help='Output format (default: markdown)'
    )

    args = parser.parse_args()

    # Determine period in hours
    period_map = {
        'daily': 24,
        'weekly': 168,
        'monthly': 720
    }
    period_hours = period_map[args.period]

    # Collect metrics
    print(f"Collecting {args.period} metrics...", file=sys.stderr)
    data = collect_metrics_data(period_hours)

    # Generate report
    if args.format == 'markdown':
        report = generate_markdown_report(data, args.period)
    else:
        report = json.dumps(data, indent=2)

    # Output report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        print(f"✅ Report written to {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == '__main__':
    main()
