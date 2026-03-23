"""
Alert Engine — rule-based anomaly detection.
Evaluates incoming metrics and recent history to produce alert events.
"""
import json
import os
from statistics import mean, stdev


DEFAULTS = {
    'cpu_warn': 80, 'cpu_crit': 90,
    'ram_warn': 85, 'ram_crit': 95,
    'disk_warn': 85, 'disk_crit': 95,
}


def load_thresholds():
    cfg_path = 'instance/settings.json'
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            return json.load(f)
    return DEFAULTS


class AlertEngine:
    def evaluate(self, data: dict, recent_metrics: list) -> list:
        """
        Returns list of dicts: {type, severity, message}
        """
        alerts = []
        cfg = load_thresholds()

        cpu = data['cpu_percent']
        ram = data['ram_percent']
        disk = data['disk_percent']

        # --- Threshold alerts ---
        if cpu >= cfg.get('cpu_crit', 90):
            alerts.append({
                'type': 'cpu',
                'severity': 'critical',
                'message': f'CPU usage is critically high at {cpu:.1f}% (threshold: {cfg["cpu_crit"]}%)'
            })
        elif cpu >= cfg.get('cpu_warn', 80):
            alerts.append({
                'type': 'cpu',
                'severity': 'warning',
                'message': f'CPU usage is elevated at {cpu:.1f}% (threshold: {cfg["cpu_warn"]}%)'
            })

        if ram >= cfg.get('ram_crit', 95):
            alerts.append({
                'type': 'ram',
                'severity': 'critical',
                'message': f'RAM usage is critically high at {ram:.1f}% (threshold: {cfg["ram_crit"]}%)'
            })
        elif ram >= cfg.get('ram_warn', 85):
            alerts.append({
                'type': 'ram',
                'severity': 'warning',
                'message': f'RAM usage is elevated at {ram:.1f}% (threshold: {cfg["ram_warn"]}%)'
            })

        if disk >= cfg.get('disk_crit', 95):
            alerts.append({
                'type': 'disk',
                'severity': 'critical',
                'message': f'Disk usage is critically full at {disk:.1f}% (threshold: {cfg["disk_crit"]}%)'
            })
        elif disk >= cfg.get('disk_warn', 85):
            alerts.append({
                'type': 'disk',
                'severity': 'warning',
                'message': f'Disk usage is high at {disk:.1f}% (threshold: {cfg["disk_warn"]}%)'
            })

        # --- Anomaly detection on recent metrics ---
        if len(recent_metrics) >= 10:
            cpu_vals = [m.cpu_percent for m in recent_metrics]
            ram_vals = [m.ram_percent for m in recent_metrics]

            # Rising RAM trend: RAM increasing monotonically for last 8 samples
            last_8_ram = ram_vals[:8]
            if all(last_8_ram[i] > last_8_ram[i+1] for i in range(len(last_8_ram)-1)):
                alerts.append({
                    'type': 'anomaly',
                    'severity': 'warning',
                    'message': f'RAM has been continuously rising for the last 8 samples — possible memory leak (now at {ram:.1f}%)'
                })

            # CPU spike: current CPU is 2 standard deviations above recent mean
            if len(cpu_vals) >= 15:
                baseline = cpu_vals[5:]  # exclude most recent 5
                if len(baseline) > 2:
                    avg = mean(baseline)
                    sd = stdev(baseline) if len(baseline) > 1 else 0
                    if sd > 0 and cpu > avg + 2 * sd and cpu > 50:
                        alerts.append({
                            'type': 'anomaly',
                            'severity': 'warning',
                            'message': f'CPU spike detected: {cpu:.1f}% vs baseline avg {avg:.1f}% (2σ above normal)'
                        })

            # Repeated CPU spikes: CPU has crossed warn threshold 5+ times in last 20 samples
            warn_threshold = cfg.get('cpu_warn', 80)
            spike_count = sum(1 for v in cpu_vals[:20] if v >= warn_threshold)
            if spike_count >= 5 and cpu < warn_threshold:
                alerts.append({
                    'type': 'anomaly',
                    'severity': 'warning',
                    'message': f'Repeated CPU spikes detected: {spike_count} readings above {warn_threshold}% in recent history'
                })

        return alerts
