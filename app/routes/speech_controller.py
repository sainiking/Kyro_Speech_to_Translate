from flask import Blueprint, jsonify, request, render_template, current_app
from flask_socketio import SocketIO, emit
from azure.cognitiveservices.speech import SpeechConfig, SpeechRecognizer, audio, PropertyId, ResultReason, CancellationDetails
from app.models import Speech, Session
from app import db, socketio
import os
import pyaudio
import threading

speech_bp = Blueprint('speech_bp', __name__)

recognition_active = False

def check_microphone():
    p = pyaudio.PyAudio()
    mic_available = False
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:
            mic_available = True
            break
    p.terminate()
    return mic_available

def recognize_speech(api_key, region, app_context, session_id):
    global recognition_active
    recognition_active = True

    speech_config = SpeechConfig(subscription=api_key, region=region)
    speech_config.speech_recognition_language = "en-US"
    audio_config = audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    speech_recognizer.properties.set_property(PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "30000")
    speech_recognizer.properties.set_property(PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "30000")

    with app_context:
        socketio.emit('new_message', {'text': "Speak into your microphone. Say 'stop session' to end."})

        while recognition_active:
            try:
                speech_recognition_result = speech_recognizer.recognize_once_async().get()

                if speech_recognition_result.reason == ResultReason.RecognizedSpeech:
                    message = f"Recognizer: {speech_recognition_result.text}"
                    socketio.emit('new_message', {'text': message})
                    # Store recognized speech in the database
                    new_speech = Speech(text=speech_recognition_result.text, session_id=session_id)
                    db.session.add(new_speech)
                    db.session.commit()
                    if "stop session" in speech_recognition_result.text.lower():
                        socketio.emit('new_message', {'text': "Session ended by user."})
                        recognition_active = False
                        break
                elif speech_recognition_result.reason == ResultReason.NoMatch:
                    socketio.emit('new_message', {'text': "No speech could be recognized."})
                elif speech_recognition_result.reason == ResultReason.Canceled:
                    cancellation_details = CancellationDetails.from_result(speech_recognition_result)
                    socketio.emit('new_message', {'text': f"Speech Recognition canceled: {cancellation_details.reason}"})
                    if cancellation_details.reason == CancellationDetails.Reason.Error:
                        socketio.emit('new_message', {'text': f"Error details: {cancellation_details.error_details}"})
            except Exception as e:
                socketio.emit('new_message', {'text': f"An error occurred: {e}"})

        socketio.emit('new_message', {'text': "Speech recognition stopped."})
        stop_recognition()  # Call the stop_recognition function to stop the microphone stream
        
def start_recognition_thread(api_key, region):
    global recognition_active
    recognition_active = False  # Reset the flag before starting a new session
    app_context = current_app.app_context()
    new_session = Session()
    db.session.add(new_session)
    db.session.commit()
    session_id = new_session.id
    thread = threading.Thread(target=recognize_speech, args=(api_key, region, app_context, session_id))
    thread.start()

@speech_bp.route('/start_recognition', methods=['POST'])
def start_recognition():
    if not check_microphone():
        return jsonify({"message": "No microphone available. Please connect a microphone and try again."}), 400

    api_key = os.getenv("api_key")
    region = os.getenv("region")
    start_recognition_thread(api_key, region)
    return jsonify({"message": "Speech recognition started"}), 200

@speech_bp.route('/stop_recognition', methods=['POST'])
def stop_recognition():
    global recognition_active
    recognition_active = False
    with current_app.app_context():
        socketio.emit('new_message', {'text': "Session closed"})
    return jsonify({"message": "Speech recognition stopped"}), 200

@speech_bp.route('/')
def index():
    return render_template('index.html')

from collections import Counter
from flask import jsonify

@speech_bp.route('/user_statistics/<int:session_id>', methods=['GET'])
def user_statistics(session_id):
    user_speeches = Speech.query.filter_by(session_id=session_id).all()
    all_speeches = Speech.query.all()

    user_words = Counter()
    all_words = Counter()
    user_phrases = Counter()

    for speech in user_speeches:
        words = speech.text.split()
        user_words.update(words)
        user_phrases.update([' '.join(words[i:i+3]) for i in range(len(words)-2)])

    for speech in all_speeches:
        words = speech.text.split()
        all_words.update(words)

    top_user_words = user_words.most_common(10)
    top_all_words = all_words.most_common(10)
    top_user_phrases = user_phrases.most_common(3)

    return jsonify({
        'top_user_words': top_user_words,
        'top_all_words': top_all_words,
        'top_user_phrases': top_user_phrases
    })