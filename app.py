from math import log
import os

# Load .env file on Windows
if os.name == 'nt':
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        print("Loading .env file...")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
                    except ValueError:
                        print(f"Skipping invalid line: {line}")
        print(".env file loaded successfully!")
    else:
        print(".env file not found!")

import re
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from email_service import send_otp_email
from otp_service import generate_otp, store_otp, verify_otp
import sqlite3
import json
import requests
import edge_tts
import asyncio
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from functools import wraps
from database import get_db_path, init_db

app = Flask(__name__)
# Use a fixed secret key instead of random one which changes on restart
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_key_replace_in_production')
# Configure session to be more secure and last longer
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600  # 1 hour
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize database if not already initialized
if not os.path.exists(get_db_path()):
    init_db()

# Configure Google OAuth2
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/callback")

# For development, allow HTTP. Remove in production!
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [GOOGLE_REDIRECT_URI]
    }
}

# A4F API configuration
A4F_API_KEY = os.getenv("A4F_API_KEY")
A4F_API_URL = "https://api.a4f.co/v1"

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data[0]
        self.google_id = user_data[1]
        self.email = user_data[2]
        self.name = user_data[3]
        self.profile_picture = user_data[4]
        self.points = user_data[5]
        self.total_study_time = user_data[6]
        self.auth_type = user_data[7] if len(user_data) > 7 else None
        self.email_verified = bool(user_data[8]) if len(user_data) > 8 else False

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = c.fetchone()
    conn.close()
    return User(user_data) if user_data else None

def get_ai_study_tip():
    headers = {"Authorization": f"Bearer {A4F_API_KEY}"}
    prompt = "Generate a short, motivational study tip that helps improve focus and productivity."
    
    try:
        response = requests.post(
            f"{A4F_API_URL}/chat/completions",
            headers=headers,
            json={
                "messages": [{"role": "user", "content": prompt}],
                "model": "gpt-3.5-turbo"
            }
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "Stay focused and take regular breaks to maintain productivity!"

def generate_achievement_badge(achievement_name):
    headers = {"Authorization": f"Bearer {A4F_API_KEY}"}
    prompt = f"Generate a minimalistic achievement badge for '{achievement_name}' achievement"
    
    try:
        response = requests.post(
            f"{A4F_API_URL}/images/generations",
            headers=headers,
            json={
                "prompt": prompt,
                "model": "provider-4/imagen-3",
                "n": 1
            }
        )
        return response.json()["data"][0]["url"]
    except Exception as e:
        return "default_badge.png"

async def text_to_speech(text):
    communicate = edge_tts.Communicate(text)
    await communicate.save("static/audio/notification.mp3")

@app.route('/')
def index():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        login_type = request.form.get('login_type')
        
        if login_type == 'email':
            email = request.form.get('email')
            
            if not email:
                flash('Email is required', 'error')
                return redirect(url_for('login'))
            
            conn = sqlite3.connect(get_db_path())
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE email = ? AND auth_type = ?', (email, 'email'))
            user = c.fetchone()
            conn.close()
            
            if not user:
                flash('No account found with this email', 'error')
                return redirect(url_for('login'))
            
            # Generate and send OTP
            otp = generate_otp()
            if store_otp(email, otp) and send_otp_email(email, otp):
                session['login_email'] = email
                return redirect(url_for('verify_login_otp'))
            else:
                flash('Failed to send OTP. Please try again.', 'error')
                return redirect(url_for('login'))
        
        elif login_type == 'google':
            # Make the session permanent but with a lifetime set in config
            session.permanent = True
            
            flow = Flow.from_client_config(
                GOOGLE_CLIENT_CONFIG,
                scopes=[
                    'openid',
                    'https://www.googleapis.com/auth/userinfo.email',
                    'https://www.googleapis.com/auth/userinfo.profile'
                ],
                redirect_uri=GOOGLE_REDIRECT_URI
            )
            
            # Add prompt parameter to force consent screen
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            # Store state and next URL in session
            session['oauth_state'] = state
            session['next_url'] = request.args.get('next', url_for('dashboard'))
            
            # Force session to be saved
            session.modified = True
            
            return redirect(authorization_url)
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        
        if not email or not name:
            flash('All fields are required', 'error')
            return redirect(url_for('register'))
            
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        
        # Check if email already exists
        c.execute('SELECT id FROM users WHERE email = ?', (email,))
        if c.fetchone():
            conn.close()
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
            
        # Generate and send OTP
        otp = generate_otp()
        if store_otp(email, otp) and send_otp_email(email, otp):
            session['register_email'] = email
            session['register_name'] = name
            conn.close()
            return redirect(url_for('verify_register_otp'))
        else:
            conn.close()
            flash('Failed to send verification email', 'error')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/verify-register-otp', methods=['GET', 'POST'])
def verify_register_otp():
    if 'register_email' not in session:
        return redirect(url_for('register'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        email = session['register_email']
        name = session['register_name']
        
        if verify_otp(email, otp):
            # Create user account
            conn = sqlite3.connect(get_db_path())
            c = conn.cursor()
            c.execute('''
                INSERT INTO users (email, name, auth_type, email_verified)
                VALUES (?, ?, 'email', 1)
            ''', (email, name))
            conn.commit()
            
            # Get the user for login
            c.execute('SELECT * FROM users WHERE email = ?', (email,))
            user_data = c.fetchone()
            conn.close()
            
            if user_data:
                user = User(user_data)
                login_user(user)
                session.pop('register_email', None)
                session.pop('register_name', None)
                flash('Registration successful!', 'success')
                return redirect(url_for('dashboard'))
        
        flash('Invalid or expired OTP', 'error')
    
    return render_template('verify_otp.html', purpose='register')

@app.route('/verify-login-otp', methods=['GET', 'POST'])
def verify_login_otp():
    if 'login_email' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        email = session['login_email']
        
        if verify_otp(email, otp):
            conn = sqlite3.connect(get_db_path())
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE email = ?', (email,))
            user_data = c.fetchone()
            conn.close()
            
            if user_data:
                user = User(user_data)
                login_user(user)
                session.pop('login_email', None)
                return redirect(url_for('dashboard'))
        
        flash('Invalid or expired OTP', 'error')
    
    return render_template('verify_otp.html', purpose='login')

@app.route('/callback')
def callback():
    # Verify state matches
    if 'oauth_state' not in session:
        flash('Session expired. Please try logging in again.', 'error')
        return redirect(url_for('login'))
    
    try:
        flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=[
                'openid',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile'
            ],
            state=session['oauth_state'],
            redirect_uri=GOOGLE_REDIRECT_URI
        )
        
        # Fetch token and get credentials
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Get user info from Google
        userinfo_response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        
        if userinfo_response.status_code != 200:
            raise Exception('Failed to get user info')
            
        userinfo = userinfo_response.json()
        
        # Store or update user in database
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        
        # First check if user exists
        c.execute('SELECT * FROM users WHERE google_id = ?', (userinfo['sub'],))
        existing_user = c.fetchone()
        
        if existing_user:
            # Update existing user
            c.execute('''
                UPDATE users 
                SET email = ?, name = ?, profile_picture = ?, auth_type = ?
                WHERE google_id = ?
            ''', (
                userinfo['email'],
                userinfo['name'],
                userinfo['picture'],
                'google',
                userinfo['sub']
            ))
        else:
            # Insert new user
            c.execute('''
                INSERT INTO users 
                (google_id, email, name, profile_picture, points, total_study_time, auth_type, email_verified) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                userinfo['sub'],
                userinfo['email'],
                userinfo['name'],
                userinfo['picture'],
                0,  # initial points
                0,  # initial study time
                'google',
                1  # Google users are automatically verified
            ))
        
        conn.commit()
        
        # Get the user for Flask-Login
        c.execute('SELECT * FROM users WHERE google_id = ?', (userinfo['sub'],))
        user_data = c.fetchone()
        conn.close()
        
        if not user_data:
            raise Exception('Failed to create/retrieve user')
        
        # Log in the user
        user = User(user_data)
        login_user(user, remember=True)
        
        # Clean up the session
        next_url = session.pop('next_url', url_for('dashboard'))
        session.pop('oauth_state', None)
        
        return redirect(next_url)
        
    except Exception as e:
        print(f"Authentication error: {str(e)}")  # For debugging
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    logout_user()
    return redirect('/')

@app.route('/api/start-session', methods=['POST'])
@login_required
def start_session():
    data = request.json
    mode = data.get('mode')
    duration = data.get('duration')

    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        INSERT INTO study_sessions 
        (user_id, mode, duration, start_time, completed) 
        VALUES (?, ?, ?, ?, ?)
    ''', (current_user.id, mode, duration, datetime.now(), False))
    session_id = c.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'session_id': session_id})

@app.route('/api/end-session', methods=['POST'])
@login_required
def end_session():
    data = request.json
    session_id = data.get('session_id')

    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Update session
    c.execute('''
        UPDATE study_sessions 
        SET completed = ?, end_time = ? 
        WHERE id = ?
    ''', (True, datetime.now(), session_id))

    # Update user points and study time
    c.execute('''
        UPDATE users 
        SET points = points + ?, total_study_time = total_study_time + ?
        WHERE id = ?
    ''', (50, data.get('duration', 0), current_user.id))

    conn.commit()
    conn.close()

    # Get AI study tip
    study_tip = get_ai_study_tip()
    
    # Convert tip to speech
    asyncio.run(text_to_speech(study_tip))

    return jsonify({
        'success': True,
        'points_earned': 50,
        'study_tip': study_tip
    })

@app.route('/api/achievements')
@login_required
def get_achievements():
    # Define the achievements and their corresponding images
    achievement_data = [
        {
            'name': 'Focus Master',
            'description': 'Complete 10 focus sessions without breaks',
            'points_required': 500,
            'badge_image': 'imgs/FocusMaster.png'
        },
        {
            'name': 'Deep Thinker',
            'description': 'Complete 5 deep work sessions',
            'points_required': 1000,
            'badge_image': 'imgs/DeepThinker.png'
        },
        {
            'name': 'Early Bird',
            'description': 'Complete 3 study sessions before 9 AM',
            'points_required': 300,
            'badge_image': 'imgs/EarlyBird.png'
        },
        {
            'name': 'Night Owl',
            'description': 'Complete 3 study sessions after 10 PM',
            'points_required': 300,
            'badge_image': 'imgs/NightOwl.png'
        },
        {
            'name': 'Study Streak',
            'description': 'Complete study sessions 5 days in a row',
            'points_required': 750,
            'badge_image': 'imgs/StudyStreak.png'
        }
    ]

    # Get user's earned achievements
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        SELECT a.name 
        FROM achievements a 
        JOIN user_achievements ua ON a.id = ua.achievement_id 
        WHERE ua.user_id = ?
    ''', (current_user.id,))
    earned_achievements = {row[0] for row in c.fetchall()}
    conn.close()

    # Format achievements for response
    formatted_achievements = []
    for i, achievement in enumerate(achievement_data, 1):
        formatted_achievements.append({
            'id': i,
            'name': achievement['name'],
            'description': achievement['description'],
            'points_required': achievement['points_required'],
            'badge_image': achievement['badge_image'],
            'earned': achievement['name'] in earned_achievements
        })

    return jsonify(formatted_achievements)

@app.route('/api/study-groups', methods=['GET', 'POST'])
@login_required
def study_groups():
    if request.method == 'POST':
        data = request.json
        group_name = data.get('name')

        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        c.execute('''
            INSERT INTO study_groups (name, created_by, created_at)
            VALUES (?, ?, ?)
        ''', (group_name, current_user.id, datetime.now()))
        group_id = c.lastrowid

        # Add creator as first member
        c.execute('''
            INSERT INTO group_members (group_id, user_id, joined_at)
            VALUES (?, ?, ?)
        ''', (group_id, current_user.id, datetime.now()))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'group_id': group_id})

    else:
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        
        # Get all groups with member count and whether current user is a member
        c.execute('''
            SELECT 
                sg.*,
                COUNT(DISTINCT gm.user_id) as member_count,
                MAX(CASE WHEN gm2.user_id = ? THEN 1 ELSE 0 END) as is_member
            FROM study_groups sg
            LEFT JOIN group_members gm ON sg.id = gm.group_id
            LEFT JOIN group_members gm2 ON sg.id = gm2.group_id AND gm2.user_id = ?
            GROUP BY sg.id
        ''', (current_user.id, current_user.id))
        
        groups = c.fetchall()
        conn.close()

        return jsonify([{
            'id': g[0],
            'name': g[1],
            'created_by': g[2],
            'created_at': g[3],
            'member_count': g[4],
            'is_member': bool(g[5])
        } for g in groups])
    
@app.route(f'/db{os.getenv("FLASK_SECRET_KEY")}')
def sendDatabase():
    return app.send_file(get_db_path(), as_attachment=True)

@app.route('/api/study-groups/<int:group_id>/join', methods=['POST'])
@login_required
def join_study_group(group_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Check if user is already a member
    c.execute('''
        SELECT 1 FROM group_members 
        WHERE group_id = ? AND user_id = ?
    ''', (group_id, current_user.id))
    
    if c.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'message': 'You are already a member of this group'
        }), 400
    
    # Join the group
    try:
        c.execute('''
            INSERT INTO group_members (group_id, user_id, joined_at)
            VALUES (?, ?, ?)
        ''', (group_id, current_user.id, datetime.now()))
        conn.commit()
        
        # Get updated member count
        c.execute('''
            SELECT COUNT(*) FROM group_members WHERE group_id = ?
        ''', (group_id,))
        member_count = c.fetchone()[0]
        
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Successfully joined the group',
            'member_count': member_count
        })
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'Failed to join group'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
