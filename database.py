from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    hostname = db.Column(db.String(128))
    ip_address = db.Column(db.String(64))
    os_name = db.Column(db.String(128))
    status = db.Column(db.String(16), default='unknown')  # online / offline / unknown
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime)

    metrics = db.relationship('Metric', backref='device', lazy=True, cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='device', lazy=True, cascade='all, delete-orphan')
    summaries = db.relationship('AISummary', backref='device', lazy=True, cascade='all, delete-orphan')


class Metric(db.Model):
    __tablename__ = 'metrics'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), db.ForeignKey('devices.device_id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    cpu_percent = db.Column(db.Float)
    ram_percent = db.Column(db.Float)
    disk_percent = db.Column(db.Float)
    uptime_seconds = db.Column(db.Integer)


class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), db.ForeignKey('devices.device_id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    alert_type = db.Column(db.String(32))   # cpu / ram / disk / offline / anomaly
    severity = db.Column(db.String(16))     # warning / critical
    message = db.Column(db.Text)
    sent_to_phone = db.Column(db.Boolean, default=False)


class AISummary(db.Model):
    __tablename__ = 'ai_summaries'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), db.ForeignKey('devices.device_id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    summary_text = db.Column(db.Text)
    possible_cause = db.Column(db.Text)
    recommendation = db.Column(db.Text)
