"""
AI Analyzer — uses Claude API to generate human-readable health summaries,
possible causes, and troubleshooting recommendations.
"""
import os
import json
import requests


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-20250514"


class AIAnalyzer:
    def analyze(self, hostname: str, current: dict, recent_metrics: list) -> dict | None:
        """
        Sends system metrics to Claude and returns a structured health analysis.
        Returns dict with keys: summary, cause, recommendation
        """
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            # Fall back to rule-based summary if no API key
            return self._rule_based_summary(current)

        prompt = f"""You are a system health analyst. Analyze the following metrics for the computer "{hostname}" and return ONLY a JSON object (no markdown, no explanation, just raw JSON).

Current snapshot:
- CPU: {current['cpu_percent']:.1f}%
- RAM: {current['ram_percent']:.1f}%
- Disk: {current['disk_percent']:.1f}%
- Uptime: {current['uptime_seconds']} seconds
- OS: {current.get('os_name', 'unknown')}

Recent history (last {len(recent_metrics)} samples):
{json.dumps(recent_metrics, indent=2)}

Return exactly this JSON structure:
{{
  "summary": "One or two sentences describing the current system health state.",
  "cause": "One sentence explaining the likely cause if anything is abnormal, or 'System appears healthy' if all is well.",
  "recommendation": "One actionable recommendation, or 'No action required' if healthy."
}}"""

        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=15
            )
            if response.status_code == 200:
                text = response.json()['content'][0]['text'].strip()
                # Strip any accidental markdown fences
                text = text.replace('```json', '').replace('```', '').strip()
                return json.loads(text)
        except Exception as e:
            print(f"[AI Analyzer] Error: {e}")

        return self._rule_based_summary(current)

    def _rule_based_summary(self, current: dict) -> dict:
        """Fallback rule-based summary when no API key is set."""
        cpu = current['cpu_percent']
        ram = current['ram_percent']
        disk = current['disk_percent']

        issues = []
        causes = []
        recs = []

        if cpu >= 90:
            issues.append(f"critically high CPU ({cpu:.0f}%)")
            causes.append("a heavy workload or runaway process")
            recs.append("open Task Manager / htop and identify the top CPU-consuming process")
        elif cpu >= 80:
            issues.append(f"elevated CPU ({cpu:.0f}%)")
            causes.append("sustained application load")
            recs.append("monitor for continued high CPU and consider closing unused applications")

        if ram >= 95:
            issues.append(f"critically high RAM ({ram:.0f}%)")
            causes.append("too many active processes or a memory leak")
            recs.append("close unused applications or restart memory-intensive services")
        elif ram >= 85:
            issues.append(f"elevated RAM ({ram:.0f}%)")

        if disk >= 95:
            issues.append(f"disk nearly full ({disk:.0f}%)")
            causes.append("insufficient disk space")
            recs.append("free up disk space by removing unused files or temporary data")
        elif disk >= 85:
            issues.append(f"high disk usage ({disk:.0f}%)")

        if issues:
            summary = f"System is experiencing {' and '.join(issues)}."
            cause = f"Likely caused by {' and '.join(causes)}." if causes else "Cause under investigation."
            rec = recs[0] if recs else "Monitor the situation closely."
        else:
            summary = f"System appears healthy. CPU at {cpu:.0f}%, RAM at {ram:.0f}%, Disk at {disk:.0f}%."
            cause = "No anomalies detected."
            rec = "No action required. Continue monitoring."

        return {"summary": summary, "cause": cause, "recommendation": rec}
