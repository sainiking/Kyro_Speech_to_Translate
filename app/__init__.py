from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from dotenv import load_dotenv

db = SQLAlchemy()
socketio = SocketIO()

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    socketio.init_app(app)

    with app.app_context():
        from app.routes.speech_controller import speech_bp
        app.register_blueprint(speech_bp)

        from .models import Speech
        db.create_all()

    return app