#!/usr/bin/env python3
"""
Spark Report - Learning Intelligence Report Generator

Generates comprehensive markdown reports analyzing Spark's learning patterns,
trends, gaps, and recommendations.

Usage:
    python spark_report.py                  # Generate report to stdout
    python spark_report.py -o report.md     # Save to file
    python spark_report.py --detailed       # Include all learnings
"""

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import Spark components
from lib.mind_client import MindClient


class SparkReportGenerator:
    """Generates intelligence reports from Spark's learnings."""

    def __init__(self):
        self.mind = MindClient()
        self.learnings: List[Dict[str, Any]] = []
        self.categories: Dict[str, List[Dict]] = defaultdict(list)
        self.stats: Dict[str, Any] = {}

    async def gather_data(self) -> None:
        """Gather all learnings from Mind."""
        print("[1/5] Querying Mind for learnings...")

        # Query for different types of learnings in parallel
        # Note: Mind uses exact case matching for pattern types
        queries = [
            ("tool_effectiveness", "TOOL_EFFECTIVENESS"),
            ("error_patterns", "ERROR_CATEGORY"),
            ("goal_strategies", "GOAL_STRATEGY"),
            ("tool_sequences", "TOOL_SEQUENCE"),
            ("all_learnings", "LEARNING"),
        ]

        results = {}
        for name, query in queries:
            try:
                data = await self.mind.retrieve(query, limit=100)
                results[name] = data or []
                print(f"    - {name}: {len(results[name])} found")
            except Exception as e:
                print(f"    - {name}: ERROR - {e}")
                results[name] = []

        self.learnings = results.get("all_learnings", [])
        self._categorize_learnings(results)

    def _categorize_learnings(self, results: Dict[str, List]) -> None:
        """Categorize learnings by type."""
        print("[2/5] Categorizing learnings...")

        # Direct assignments from queries
        self.categories["tool"] = results.get("tool_effectiveness", [])
        self.categories["error"] = results.get("error_patterns", [])
        self.categories["goal"] = results.get("goal_strategies", [])
        self.categories["sequence"] = results.get("tool_sequences", [])

        # Categorize remaining learnings
        seen_ids = set()
        for cat_list in self.categories.values():
            for item in cat_list:
                seen_ids.add(item.get("memory_id"))

        for learning in self.learnings:
            if learning.get("memory_id") not in seen_ids:
                content = learning.get("content", "").lower()
                if "tool" in content and "effectiveness" in content:
                    self.categories["tool"].append(learning)
                elif "error" in content or "recovery" in content:
                    self.categories["error"].append(learning)
                elif "goal" in content or "strategy" in content:
                    self.categories["goal"].append(learning)
                elif "sequence" in content or "parallel" in content:
                    self.categories["sequence"].append(learning)
                else:
                    self.categories["other"].append(learning)

        for cat, items in self.categories.items():
            print(f"    - {cat}: {len(items)} learnings")

    def analyze_patterns(self) -> None:
        """Analyze patterns and compute statistics."""
        print("[3/5] Analyzing patterns...")

        self.stats = {
            "total_learnings": len(self.learnings),
            "categories": {k: len(v) for k, v in self.categories.items()},
            "tools_learned": set(),
            "error_types": set(),
            "goal_types": set(),
            "confidence_distribution": {"high": 0, "medium": 0, "low": 0},
            "recent_activity": {"24h": 0, "7d": 0, "30d": 0},
        }

        now = datetime.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        for learning in self.learnings:
            content = learning.get("content", "")

            # Extract tool names
            if "tool=" in content:
                tool = content.split("tool=")[1].split()[0].strip("',\".;:")
                self.stats["tools_learned"].add(tool)

            # Extract error types
            if "error_type=" in content or "category=" in content:
                parts = content.split("=")
                for i, p in enumerate(parts):
                    if "error" in p.lower() or "category" in p.lower():
                        if i + 1 < len(parts):
                            error_type = parts[i + 1].split()[0].strip("',\"")
                            self.stats["error_types"].add(error_type)

            # Confidence distribution
            salience = learning.get("salience", 0.5)
            if salience >= 0.8:
                self.stats["confidence_distribution"]["high"] += 1
            elif salience >= 0.5:
                self.stats["confidence_distribution"]["medium"] += 1
            else:
                self.stats["confidence_distribution"]["low"] += 1

            # Recent activity
            created = learning.get("created_at", "")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created_dt = created_dt.replace(tzinfo=None)
                    if created_dt > day_ago:
                        self.stats["recent_activity"]["24h"] += 1
                    if created_dt > week_ago:
                        self.stats["recent_activity"]["7d"] += 1
                    if created_dt > month_ago:
                        self.stats["recent_activity"]["30d"] += 1
                except:
                    pass

        # Convert sets to lists for JSON serialization
        self.stats["tools_learned"] = list(self.stats["tools_learned"])
        self.stats["error_types"] = list(self.stats["error_types"])
        self.stats["goal_types"] = list(self.stats["goal_types"])

        print(f"    - Tools learned: {len(self.stats['tools_learned'])}")
        print(f"    - Error types: {len(self.stats['error_types'])}")
        print(f"    - Recent (24h): {self.stats['recent_activity']['24h']}")

    def identify_gaps(self) -> List[str]:
        """Identify learning gaps and areas for improvement."""
        print("[4/5] Identifying gaps...")

        gaps = []

        # Check for missing categories
        if len(self.categories["tool"]) == 0:
            gaps.append("No tool effectiveness patterns learned yet")
        if len(self.categories["error"]) == 0:
            gaps.append("No error patterns captured - errors may not be reaching the learner")
        if len(self.categories["goal"]) == 0:
            gaps.append("No goal strategies learned - goal tracking may need attention")
        if len(self.categories["sequence"]) == 0:
            gaps.append("No tool sequence patterns - parallel tool usage not detected")

        # Check confidence distribution
        conf = self.stats["confidence_distribution"]
        if conf["high"] == 0 and self.stats["total_learnings"] > 10:
            gaps.append("No high-confidence learnings - patterns may need more validation")

        # Check recent activity
        recent = self.stats["recent_activity"]
        if recent["24h"] == 0 and self.stats["total_learnings"] > 0:
            gaps.append("No new learnings in 24h - is the daemon running?")

        # Check tool coverage
        expected_tools = {"Read", "Edit", "Write", "Bash", "Grep", "Glob", "Task"}
        learned_tools = set(self.stats["tools_learned"])
        missing_tools = expected_tools - learned_tools
        if missing_tools:
            gaps.append(f"Missing tool patterns for: {', '.join(missing_tools)}")

        print(f"    - Found {len(gaps)} gaps")
        return gaps

    def generate_recommendations(self, gaps: List[str]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if "daemon" in str(gaps).lower():
            recommendations.append("Run `python processor.py --mode daemon` to enable continuous learning")

        if "error patterns" in str(gaps).lower():
            recommendations.append("Check hooks/observe.py error capture - errors may not be propagating")

        if "tool effectiveness" in str(gaps).lower():
            recommendations.append("Use more tools in your sessions to build up effectiveness patterns")

        if "goal" in str(gaps).lower():
            recommendations.append("Start sessions with clear goals to enable goal strategy learning")

        if "sequence" in str(gaps).lower():
            recommendations.append("Try using multiple tools together to trigger sequence pattern detection")

        if not recommendations:
            recommendations.append("System is learning well - keep using it!")

        return recommendations

    def generate_report(self, detailed: bool = False) -> str:
        """Generate the markdown report."""
        print("[5/5] Generating report...")

        gaps = self.identify_gaps()
        recommendations = self.generate_recommendations(gaps)

        lines = []

        # Header
        lines.append("# Spark Learning Intelligence Report")
        lines.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

        # Executive Summary
        lines.append("## Executive Summary\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Learnings | {self.stats['total_learnings']} |")
        lines.append(f"| Tools Learned | {len(self.stats['tools_learned'])} |")
        lines.append(f"| Error Types | {len(self.stats['error_types'])} |")
        lines.append(f"| Learning Gaps | {len(gaps)} |")
        lines.append(f"| Health Status | {'Good' if len(gaps) < 3 else 'Needs Attention'} |")

        # Learning Breakdown
        lines.append("\n## Learning Breakdown\n")
        lines.append("```")
        for cat, count in sorted(self.stats["categories"].items(), key=lambda x: x[1], reverse=True):
            bar = "#" * min(count, 50)
            lines.append(f"{cat:12} | {bar} ({count})")
        lines.append("```")

        # Confidence Distribution
        lines.append("\n## Confidence Distribution\n")
        conf = self.stats["confidence_distribution"]
        total = max(sum(conf.values()), 1)
        lines.append(f"- High (>=0.8): {conf['high']} ({conf['high']*100//total}%)")
        lines.append(f"- Medium (0.5-0.8): {conf['medium']} ({conf['medium']*100//total}%)")
        lines.append(f"- Low (<0.5): {conf['low']} ({conf['low']*100//total}%)")

        # Recent Activity
        lines.append("\n## Recent Activity\n")
        recent = self.stats["recent_activity"]
        lines.append(f"- Last 24 hours: {recent['24h']} learnings")
        lines.append(f"- Last 7 days: {recent['7d']} learnings")
        lines.append(f"- Last 30 days: {recent['30d']} learnings")

        # Tools Learned
        if self.stats["tools_learned"]:
            lines.append("\n## Tools With Effectiveness Patterns\n")
            for tool in sorted(self.stats["tools_learned"]):
                lines.append(f"- {tool}")

        # Gaps
        if gaps:
            lines.append("\n## Learning Gaps\n")
            for gap in gaps:
                lines.append(f"- {gap}")

        # Recommendations
        lines.append("\n## Recommendations\n")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")

        # Detailed Learnings
        if detailed and self.learnings:
            lines.append("\n## All Learnings (Detailed)\n")
            for i, learning in enumerate(self.learnings[:50], 1):
                content = learning.get("content", "")[:200]
                salience = learning.get("salience", 0)
                lines.append(f"\n### Learning {i}")
                lines.append(f"- **Salience**: {salience:.2f}")
                lines.append(f"- **Content**: {content}...")

        # Footer
        lines.append("\n---")
        lines.append("*Report generated by spark-report | Spark Self-Evolving Intelligence*")

        return "\n".join(lines)

    async def close(self):
        """Clean up resources."""
        await self.mind.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Spark Learning Intelligence Report"
    )
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    parser.add_argument("--detailed", action="store_true", help="Include detailed learnings")
    parser.add_argument("--json", action="store_true", help="Output stats as JSON instead")

    args = parser.parse_args()

    print("=" * 50)
    print("  Spark Learning Intelligence Report Generator")
    print("=" * 50)
    print()

    generator = SparkReportGenerator()

    try:
        # Gather and analyze
        await generator.gather_data()
        generator.analyze_patterns()

        if args.json:
            # JSON output
            output = json.dumps(generator.stats, indent=2)
        else:
            # Markdown report
            output = generator.generate_report(detailed=args.detailed)

        # Output
        if args.output:
            Path(args.output).write_text(output)
            print(f"\nReport saved to: {args.output}")
        else:
            print("\n" + "=" * 50)
            print(output)

    finally:
        await generator.close()


if __name__ == "__main__":
    asyncio.run(main())
