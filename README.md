# Study Smart Timer

A sophisticated study timer application with AI-powered suggestions, gamification, and social features.

## Features

- **Multiple Study Modes**
  - Focus Mode (25/5 minutes)
  - Deep Work Mode (50/10 minutes)
  - Custom Mode with user-defined intervals

- **AI-Powered Study Tips**
  - Personalized suggestions using a4f.co API
  - Context-aware tips based on study patterns
  - Voice announcements using edge-tts

- **Gamification**
  - Points system for completed sessions
  - Unlockable achievements
  - Custom achievement badges

- **Social Features**
  - Create and join study groups
  - Share progress with friends
  - Collaborative study sessions

## Tech Stack

- Backend: Python/Flask
- Database: SQLite3
- AI Integration: a4f.co API
- Authentication: Google OAuth2
- TTS: edge-tts
- Frontend: HTML/CSS/JavaScript with Tailwind CSS

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/TheTechTiger/SmartStudyTimer.git
   cd SmartStudyTimer
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

3. Install dependencies:
   ```bash
   pip install flask requests edge-tts python-dotenv google-auth-oauthlib flask-login
   ```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Add your Google OAuth2 credentials
   - Add your a4f.co API key

5. Initialize the database:
   ```bash
   python database.py
   ```

6. Run the application:
   ```bash
   python app.py
   ```

7. Open http://localhost:5000 in your browser

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.
