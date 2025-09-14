import sqlite3
import os
import platform

def get_db_path():
    if platform.system() == 'Windows':
        return 'SmartStudy.db'
    return '/tmp/SmartStudy.db'

def init_db():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    # Drop existing tables
    c.executescript('''
        DROP TABLE IF EXISTS user_achievements;
        DROP TABLE IF EXISTS group_members;
        DROP TABLE IF EXISTS study_groups;
        DROP TABLE IF EXISTS achievements;
        DROP TABLE IF EXISTS study_sessions;
        DROP TABLE IF EXISTS otp_storage;
        DROP TABLE IF EXISTS users;
    ''')

    # Create users table with auth_type
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE,
            email TEXT UNIQUE,
            name TEXT,
            profile_picture TEXT,
            points INTEGER DEFAULT 0,
            total_study_time INTEGER DEFAULT 0,
            auth_type TEXT CHECK(auth_type IN ('google', 'email')) NOT NULL,
            email_verified BOOLEAN DEFAULT 0
        )
    ''')
    
    # Create OTP storage table
    c.execute('''
        CREATE TABLE IF NOT EXISTS otp_storage (
            email TEXT PRIMARY KEY,
            otp TEXT NOT NULL,
            expiration TIMESTAMP NOT NULL
        )
    ''')

    # Create study_sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mode TEXT,
            duration INTEGER,
            completed BOOLEAN,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create achievements table
    c.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            points_required INTEGER,
            badge_image TEXT
        )
    ''')

    # Create user_achievements table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id INTEGER,
            achievement_id INTEGER,
            date_earned TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (achievement_id) REFERENCES achievements (id),
            PRIMARY KEY (user_id, achievement_id)
        )
    ''')

    # Create study_groups table
    c.execute('''
        CREATE TABLE IF NOT EXISTS study_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            created_by INTEGER,
            created_at TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    # Create group_members table
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER,
            user_id INTEGER,
            joined_at TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES study_groups (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            PRIMARY KEY (group_id, user_id)
        )
    ''')

    # Insert default achievements
    default_achievements = [
        ('Early Bird', 'Complete 5 study sessions before 10 AM', 100, 'early_bird.png'),
        ('Night Owl', 'Complete 5 study sessions after 8 PM', 100, 'night_owl.png'),
        ('Focus Master', 'Complete 10 Focus Mode sessions', 200, 'focus_master.png'),
        ('Deep Thinker', 'Complete 10 Deep Work Mode sessions', 300, 'deep_thinker.png'),
        ('Study Streak', 'Study for 7 consecutive days', 500, 'study_streak.png')
    ]

    c.executemany('''
        INSERT OR IGNORE INTO achievements (name, description, points_required, badge_image)
        VALUES (?, ?, ?, ?)
    ''', default_achievements)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
