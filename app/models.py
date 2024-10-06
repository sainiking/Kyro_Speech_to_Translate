from app import db
from datetime import datetime

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    speeches = db.relationship('Speech', backref='session', lazy=True)

class Speech(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)