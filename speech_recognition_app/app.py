# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Mail, Message
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
# Changes this to a random string in production
app.secret_key = secrets.token_hex(32)
# Adding mail configuration for notffivation of mail 
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@example.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'your-password'  # Replace with your email password
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@example.com'
mail = Mail(app)

# Configure upload folder and allowed file extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'mp4', 'webm', 'flac', 'm4a'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # Limit uploads to 32MB

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

# Enhanced audio handling functions
def convert_to_wav(input_path):
    """Convert any audio/video file to WAV format compatible with speech_recognition"""
    try:
        from pydub import AudioSegment
        
        # Get the file extension
        file_extension = input_path.rsplit('.', 1)[1].lower()
        
        # Create output path with WAV extension
        output_path = os.path.join(
            os.path.dirname(input_path),
            f"{os.path.basename(input_path).rsplit('.', 1)[0]}_converted.wav"
        )
        
        # Load the audio (pydub can handle many formats)
        audio = AudioSegment.from_file(input_path, format=file_extension)
        
        # Export as WAV with specific parameters compatible with speech_recognition
        audio = audio.set_channels(1)  # Convert to mono
        audio = audio.set_frame_rate(16000)  # Set sample rate to 16kHz
        audio.export(output_path, format="wav", parameters=["-ac", "1", "-ar", "16000"])
        
        return output_path, True
    except Exception as e:
        print(f"Error converting audio: {str(e)}")
        return None, False

# Speech recognition function
def transcribe_audio(audio_path):
    """Improved transcription function with better format handling"""
    recognizer = sr.Recognizer()
    
    # Adjust recognition parameters for better results
    recognizer.energy_threshold = 300  # Default is 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8  # Default is 0.8 seconds
    
    # First, try to convert the file to a compatible WAV format
    converted_path, success = convert_to_wav(audio_path)
    
    if not success:
        return "Error transcribing: Could not convert the audio file to a compatible format."
    
    try:
        with sr.AudioFile(converted_path) as source:
            # Adjust for ambient noise first
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)
        
        # Try Google's speech recognition service
        try:
            text = recognizer.recognize_google(audio)
            return text
        except sr.RequestError:
            # If Google service fails, try the offline Sphinx recognizer if available
            try:
                text = recognizer.recognize_sphinx(audio)
                return text + " (processed using offline recognition)"
            except (sr.UnknownValueError, ImportError, AttributeError):
                return "Could not request results. Check your internet connection."
            
    except sr.UnknownValueError:
        return "Could not understand the audio."
    except Exception as e:
        print(f"Error in transcribe_audio: {str(e)}")
        return f"Error transcribing: {str(e)}"
    finally:
        # Clean up the converted file
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except:
                pass

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

# Note: We've replaced this function with the more comprehensive convert_to_wav function above

# Routes
@app.route('/')
def index():
    return render_template('index.html')


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
            try:
                # Generate unique filename to prevent overwriting
                original_filename = secure_filename(file.filename)
                file_extension = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4()}_{original_filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                # Inform user about processing
                flash('Processing audio... This may take a moment.', 'info')
                
                # Transcribe the audio directly using the enhanced transcribe_audio function
                # that now handles conversion internally
                text = transcribe_audio(filepath)

                # Save transcription to database if successful
                if not text.startswith("Error") and text != "Could not understand the audio." and text != "Could not request results. Check your internet connection.":
                    transcription_id = save_transcription(
                        session['user_id'], text, f"Uploaded: {original_filename}")
                    flash('Transcription saved to your history', 'success')
                else:
                    flash('Transcription completed but with possible issues', 'warning')

                # Clean up the original file
                if os.path.exists(filepath):
                    os.remove(filepath)

                # Return the transcription result
                return render_template('transcriptionresult.html', 
                                      transcription=text, 
                                      filename=original_filename,
                                      file_type=file_extension)

            except Exception as e:
                flash(f'Error processing upload: {str(e)}', 'error')
                return redirect(request.url)

        else:
            flash(f'Unsupported file type. Please upload one of these formats: {", ".join(ALLOWED_EXTENSIONS)}', 'error')
            return redirect(request.url)

    return render_template('uploadaudio.html', allowed_extensions=ALLOWED_EXTENSIONS)


@app.route('/record')
@login_required
def record_audio():
    return render_template('recordaudio.html')


@app.route('/process_recording', methods=['POST'])
@login_required
def process_recording():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio data received'})

    file = request.files['audio_data']
    if not file:
        return jsonify({'error': 'Empty file received'})

    # Create temporary input file
    temp_input = None

    try:
        # Save temporary input file
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
        file.save(temp_input.name)
        temp_input.close()

        # Use the enhanced transcribe_audio function that handles conversion internally
        text = transcribe_audio(temp_input.name)

        # Save to database if transcription was successful
        if not text.startswith("Error") and text != "Could not understand the audio." and text != "Could not request results. Check your internet connection.":
            save_transcription(session['user_id'], text, "Live Recording")
            return jsonify({'transcription': text})
        else:
            return jsonify({'error': text})

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return jsonify({'error': f'Error processing audio: {str(e)}'})

    finally:
        # Clean up temp file
        if temp_input and os.path.exists(temp_input.name):
            os.unlink(temp_input.name)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

def send_email_notification(name, email, subject, message):
    msg = Message(
        subject=f"New contact form submission: {subject}",
        recipients=['devanandanas911@gmail.com'],  # Where to send the notification
        body=f"Name: {name}\nEmail: {email}\nMessage: {message}"
    )
    mail.send(msg)
    
@app.route('/contact', methods=['POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Store in database
        conn = sqlite3.connect('speech_app.db')
        c = conn.cursor()
        
        # Create contact_messages table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS contact_messages
                    (id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    subject TEXT,
                    message TEXT,
                    created_at TEXT)''')
        
        message_id = str(uuid.uuid4())
        c.execute("INSERT INTO contact_messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                (message_id, name, email, phone, subject, message, 
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        # Send email notification (optional - requires additional setup)
        # send_email_notification(name, email, subject, message)
        
        flash('Thank you for your message! We will get back to you soon.', 'success')
        return redirect(url_for('index'))
    
    # If someone tries to access this route directly with GET
    return redirect(url_for('index'))
if __name__ == '__main__':
    app.run(debug=True)