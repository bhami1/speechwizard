# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import speech_recognition as sr
import os
import uuid
import hashlib
import sqlite3
import tempfile
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Changes this to a random string in production

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database setup
def init_db():
    conn = sqlite3.connect('speech_app.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, 
                  username TEXT UNIQUE, 
                  password TEXT, 
                  email TEXT UNIQUE,
                  created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transcriptions
                 (id TEXT PRIMARY KEY,
                  user_id TEXT,
                  text TEXT,
                  source TEXT,
                  created_at TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Authentication functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, email):
    conn = sqlite3.connect('speech_app.db')
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(password)
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                 (user_id, username, hashed_password, email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success, user_id if success else None

def verify_user(username, password):
    conn = sqlite3.connect('speech_app.db')
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    
    if result and result[1] == hash_password(password):
        return result[0]  # Return user_id on successful login
    return None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Speech recognition function
def transcribe_audio(audio_path):
    recognizer = sr.Recognizer()
    
    # Adjust recognition parameters for better results
    recognizer.energy_threshold = 300  # Default is 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8  # Default is 0.8 seconds
    
    try:
        with sr.AudioFile(audio_path) as source:
            # Adjust for ambient noise first
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        return "Could not understand the audio."
    except sr.RequestError:
        return "Could not request results. Check your internet connection."
    except Exception as e:
        print(f"Error in transcribe_audio: {str(e)}")
        return f"Error transcribing: {str(e)}"

# Database operations for transcriptions
def save_transcription(user_id, text, source):
    conn = sqlite3.connect('speech_app.db')
    c = conn.cursor()
    transcription_id = str(uuid.uuid4())
    c.execute("INSERT INTO transcriptions VALUES (?, ?, ?, ?, ?)", 
             (transcription_id, user_id, text, source, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return transcription_id

def get_user_transcriptions(user_id):
    conn = sqlite3.connect('speech_app.db')
    c = conn.cursor()
    c.execute("SELECT id, text, source, created_at FROM transcriptions WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    results = c.fetchall()
    conn.close()
    return results

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user_id = verify_user(username, password)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            success, user_id = create_user(username, password, email)
            if success:
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Username or email already exists', 'error')
    
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    transcriptions = get_user_transcriptions(session['user_id'])
    return render_template('dashboard.html', username=session['username'], transcriptions=transcriptions)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_audio():
    if request.method == 'POST':
        if 'audio_file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['audio_file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Transcribe the audio
            text = transcribe_audio(filepath)
            
            # Save transcription to database
            if not text.startswith("Error") and text != "Could not understand the audio." and text != "Could not request results. Check your internet connection.":
                save_transcription(session['user_id'], text, f"Uploaded: {filename}")
                flash('Transcription saved to your history', 'success')
            
            # Remove the file after processing
            os.remove(filepath)
            
            return render_template('result.html', transcription=text)
    
    return render_template('upload.html')

@app.route('/record')
@login_required
def record_audio():
    return render_template('record.html')

@app.route('/process_recording', methods=['POST'])
@login_required
def process_recording():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio data received'})
    
    file = request.files['audio_data']
    if not file:
        return jsonify({'error': 'Empty file received'})
    
    # Create necessary temp files
    temp_input = None
    temp_output = None
    
    try:
        # Save temporary input file
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
        file.save(temp_input.name)
        temp_input.close()
        
        # Convert to WAV format for speech recognition
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_output.close()
        
        # Use pydub to convert
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(temp_input.name)
            audio.export(temp_output.name, format="wav")
            
            # Transcribe
            text = transcribe_audio(temp_output.name)
            
            # Save to database if transcription was successful
            if not text.startswith("Error") and text != "Could not understand the audio." and text != "Could not request results. Check your internet connection.":
                save_transcription(session['user_id'], text, "Live Recording")
                return jsonify({'transcription': text})
            else:
                return jsonify({'error': text})
                
        except ImportError:
            return jsonify({'error': 'Missing pydub library. Please install it with: pip install pydub'})
        
    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return jsonify({'error': f'Error processing audio: {str(e)}'})
    
    finally:
        # Clean up temp files
        if temp_input and os.path.exists(temp_input.name):
            os.unlink(temp_input.name)
        if temp_output and os.path.exists(temp_output.name):
            os.unlink(temp_output.name)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)