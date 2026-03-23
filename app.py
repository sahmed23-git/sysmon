import os
import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, Response
from database import db, Device, Metric, Alert, AISummary
from alert_engine import AlertEngine
from ai_analyzer import AIAnalyzer
from telegram_bot import TelegramBot

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sysmon.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

db.init_app(app)

alert_engine = AlertEngine()
ai_analyzer = AIAnalyzer()
telegram_bot = TelegramBot()

# --- API: Receive metrics from agent ---
@app.route('/api/metrics', methods=['POST'])
def receive_metrics():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    required = ['device_id', 'hostname', 'cpu_percent', 'ram_percent', 'disk_percent', 'uptime_seconds']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing fields'}), 400

    # Upsert device
    device = Device.query.filter_by(device_id=data['device_id']).first()
    if not device:
        device = Device(
            device_id=data['device_id'],
            hostname=data['hostname'],
            ip_address=data.get('ip_address', 'unknown'),
            os_name=data.get('os_name', 'unknown'),
            first_seen=datetime.utcnow()
        )
        db.session.add(device)

    device.last_seen = datetime.utcnow()
    device.hostname = data['hostname']
    device.ip_address = data.get('ip_address', device.ip_address)
    device.status = 'online'

    # Store metric
    metric = Metric(
        device_id=data['device_id'],
        cpu_percent=data['cpu_percent'],
        ram_percent=data['ram_percent'],
        disk_percent=data['disk_percent'],
        uptime_seconds=data['uptime_seconds'],
        timestamp=datetime.utcnow()
    )
    db.session.add(metric)
    db.session.commit()

    # Run alert engine in background
    threading.Thread(
        target=check_alerts,
        args=(data['device_id'], data, device.hostname),
        daemon=True
    ).start()

    return jsonify({'status': 'ok'}), 200


def check_alerts(device_id, data, hostname):
    with app.app_context():
        recent_metrics = Metric.query.filter_by(device_id=device_id)\
            .order_by(Metric.timestamp.desc()).limit(30).all()

        triggered = alert_engine.evaluate(data, recent_metrics)

        for alert_data in triggered:
            # Check cooldown: skip if same alert type sent in last 10 minutes
            recent_alert = Alert.query.filter_by(
                device_id=device_id,
                alert_type=alert_data['type']
            ).filter(Alert.timestamp > datetime.utcnow() - timedelta(minutes=10)).first()

            if recent_alert:
                continue

            alert = Alert(
                device_id=device_id,
                alert_type=alert_data['type'],
                severity=alert_data['severity'],
                message=alert_data['message'],
                timestamp=datetime.utcnow(),
                sent_to_phone=False
            )
            db.session.add(alert)
            db.session.commit()

            # Send Telegram
            msg = f"{'🔴 CRITICAL' if alert_data['severity'] == 'critical' else '🟡 WARNING'}: {hostname}\n{alert_data['message']}"
            sent = telegram_bot.send(msg)
            alert.sent_to_phone = sent
            db.session.commit()

        # Periodically generate AI summary (every 5 minutes)
        last_summary = AISummary.query.filter_by(device_id=device_id)\
            .order_by(AISummary.timestamp.desc()).first()
        if not last_summary or (datetime.utcnow() - last_summary.timestamp).seconds > 300:
            metrics_list = [
                {'cpu': m.cpu_percent, 'ram': m.ram_percent, 'disk': m.disk_percent, 'ts': m.timestamp.isoformat()}
                for m in recent_metrics[:10]
            ]
            summary = ai_analyzer.analyze(hostname, data, metrics_list)
            if summary:
                s = AISummary(
                    device_id=device_id,
                    summary_text=summary.get('summary', ''),
                    possible_cause=summary.get('cause', ''),
                    recommendation=summary.get('recommendation', ''),
                    timestamp=datetime.utcnow()
                )
                db.session.add(s)
                db.session.commit()


# --- API: Check offline devices (called by frontend poll) ---
@app.route('/api/check-offline', methods=['POST'])
def check_offline():
    cutoff = datetime.utcnow() - timedelta(seconds=60)
    devices = Device.query.all()
    for device in devices:
        if device.last_seen and device.last_seen < cutoff and device.status == 'online':
            device.status = 'offline'
            alert = Alert(
                device_id=device.device_id,
                alert_type='offline',
                severity='critical',
                message=f'{device.hostname} has gone offline (no check-in for 60s)',
                timestamp=datetime.utcnow(),
                sent_to_phone=False
            )
            db.session.add(alert)
            db.session.commit()
            msg = f"🔴 OFFLINE: {device.hostname} stopped reporting"
            sent = telegram_bot.send(msg)
            alert.sent_to_phone = sent
            db.session.commit()

            # Recovery: if back online, send recovery alert
        elif device.last_seen and device.last_seen >= cutoff and device.status == 'offline':
            device.status = 'online'
            db.session.commit()
            telegram_bot.send(f"✅ RECOVERED: {device.hostname} is back online")

    db.session.commit()
    return jsonify({'status': 'ok'})


# --- API: Get all devices ---
@app.route('/api/devices', methods=['GET'])
def get_devices():
    devices = Device.query.all()
    result = []
    for d in devices:
        latest = Metric.query.filter_by(device_id=d.device_id)\
            .order_by(Metric.timestamp.desc()).first()
        active_alerts = Alert.query.filter_by(device_id=d.device_id)\
            .filter(Alert.timestamp > datetime.utcnow() - timedelta(hours=1)).count()
        result.append({
            'device_id': d.device_id,
            'hostname': d.hostname,
            'ip_address': d.ip_address,
            'os_name': d.os_name,
            'status': d.status,
            'last_seen': d.last_seen.isoformat() if d.last_seen else None,
            'cpu': latest.cpu_percent if latest else None,
            'ram': latest.ram_percent if latest else None,
            'disk': latest.disk_percent if latest else None,
            'uptime': latest.uptime_seconds if latest else None,
            'active_alerts': active_alerts
        })
    return jsonify(result)


# --- API: Get device detail + history ---
@app.route('/api/devices/<device_id>', methods=['GET'])
def get_device_detail(device_id):
    device = Device.query.filter_by(device_id=device_id).first_or_404()
    metrics = Metric.query.filter_by(device_id=device_id)\
        .order_by(Metric.timestamp.desc()).limit(60).all()
    alerts = Alert.query.filter_by(device_id=device_id)\
        .order_by(Alert.timestamp.desc()).limit(20).all()
    summary = AISummary.query.filter_by(device_id=device_id)\
        .order_by(AISummary.timestamp.desc()).first()

    return jsonify({
        'device': {
            'device_id': device.device_id,
            'hostname': device.hostname,
            'ip_address': device.ip_address,
            'os_name': device.os_name,
            'status': device.status,
            'first_seen': device.first_seen.isoformat() if device.first_seen else None,
            'last_seen': device.last_seen.isoformat() if device.last_seen else None,
        },
        'metrics': [
            {'ts': m.timestamp.isoformat(), 'cpu': m.cpu_percent,
             'ram': m.ram_percent, 'disk': m.disk_percent, 'uptime': m.uptime_seconds}
            for m in reversed(metrics)
        ],
        'alerts': [
            {'id': a.id, 'type': a.alert_type, 'severity': a.severity,
             'message': a.message, 'ts': a.timestamp.isoformat(), 'phone': a.sent_to_phone}
            for a in alerts
        ],
        'ai_summary': {
            'summary': summary.summary_text,
            'cause': summary.possible_cause,
            'recommendation': summary.recommendation,
            'ts': summary.timestamp.isoformat()
        } if summary else None
    })


# --- API: All alerts ---
@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    alerts = Alert.query.order_by(Alert.timestamp.desc()).limit(100).all()
    return jsonify([
        {'id': a.id, 'device_id': a.device_id, 'type': a.alert_type,
         'severity': a.severity, 'message': a.message,
         'ts': a.timestamp.isoformat(), 'phone': a.sent_to_phone}
        for a in alerts
    ])


# --- API: Settings ---
@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    cfg_path = 'instance/settings.json'
    defaults = {
        'cpu_warn': 80, 'cpu_crit': 90,
        'ram_warn': 85, 'ram_crit': 95,
        'disk_warn': 85, 'disk_crit': 95,
        'offline_seconds': 60,
        'cooldown_minutes': 10,
        'telegram_token': os.environ.get('TELEGRAM_TOKEN', ''),
        'telegram_chat_id': os.environ.get('TELEGRAM_CHAT_ID', '')
    }
    if request.method == 'POST':
        data = request.get_json()
        os.makedirs('instance', exist_ok=True)
        with open(cfg_path, 'w') as f:
            json.dump(data, f)
        # Update bot credentials live
        telegram_bot.update_credentials(data.get('telegram_token', ''), data.get('telegram_chat_id', ''))
        return jsonify({'status': 'saved'})
    else:
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                return jsonify(json.load(f))
        return jsonify(defaults)


# --- Dashboard routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/device/<device_id>')
def device_detail(device_id):
    return render_template('device.html', device_id=device_id)

@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
