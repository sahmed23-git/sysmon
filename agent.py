#!/usr/bin/env python3
"""
SysMon Agent — runs on the monitored computer.
Collects system metrics and sends them to the central Flask server.

Usage:
    python agent.py --server http://localhost:5000 --interval 10

Environment variables (alternative to flags):
    SYSMON_SERVER   = http://your-server:5000
    SYSMON_INTERVAL = 10
    SYSMON_DEVICE_ID = optional-custom-id
"""
import argparse
import os
import platform
import socket
import time
import uuid
import requests
import psutil


def get_device_id() -> str:
    """Generate or load a persistent unique device ID."""
    id_file = os.path.expanduser('~/.sysmon_device_id')
    custom = os.environ.get('SYSMON_DEVICE_ID')
    if custom:
        return custom
    if os.path.exists(id_file):
        with open(id_file) as f:
            return f.read().strip()
    device_id = str(uuid.uuid4())
    with open(id_file, 'w') as f:
        f.write(device_id)
    return device_id


def get_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def collect_metrics(device_id: str) -> dict:
    return {
        'device_id': device_id,
        'hostname': socket.gethostname(),
        'ip_address': get_ip(),
        'os_name': f'{platform.system()} {platform.release()}',
        'cpu_percent': psutil.cpu_percent(interval=1),
        'ram_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'uptime_seconds': int(time.time() - psutil.boot_time()),
    }


def send_metrics(server_url: str, metrics: dict) -> bool:
    try:
        resp = requests.post(
            f'{server_url.rstrip("/")}/api/metrics',
            json=metrics,
            timeout=10
        )
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        print(f'[Agent] Cannot reach server at {server_url}. Retrying...')
        return False
    except Exception as e:
        print(f'[Agent] Error sending metrics: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='SysMon Monitoring Agent')
    parser.add_argument('--server', default=os.environ.get('SYSMON_SERVER', 'http://localhost:5000'),
                        help='Central server URL')
    parser.add_argument('--interval', type=int,
                        default=int(os.environ.get('SYSMON_INTERVAL', '10')),
                        help='Collection interval in seconds')
    args = parser.parse_args()

    device_id = get_device_id()
    hostname = socket.gethostname()

    print(f'[SysMon Agent] Starting')
    print(f'  Device ID : {device_id}')
    print(f'  Hostname  : {hostname}')
    print(f'  Server    : {args.server}')
    print(f'  Interval  : {args.interval}s')
    print(f'  OS        : {platform.system()} {platform.release()}')
    print()

    consecutive_failures = 0

    while True:
        metrics = collect_metrics(device_id)
        success = send_metrics(args.server, metrics)

        if success:
            consecutive_failures = 0
            ts = time.strftime('%H:%M:%S')
            print(f'[{ts}] Sent — CPU: {metrics["cpu_percent"]:.1f}%  '
                  f'RAM: {metrics["ram_percent"]:.1f}%  '
                  f'Disk: {metrics["disk_percent"]:.1f}%')
        else:
            consecutive_failures += 1
            if consecutive_failures % 6 == 0:  # remind every minute
                print(f'[Agent] Failed to reach server {consecutive_failures} times. '
                      f'Is {args.server} running?')

        time.sleep(args.interval)


if __name__ == '__main__':
    main()
