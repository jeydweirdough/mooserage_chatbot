from flask import Flask, request, jsonify, send_file, Response, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
import os
import json
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests as http_client
from datetime import datetime
from groq import Groq

load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(32).hex())
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False  # Set to True if deploying with HTTPS
)
CORS(app)

# --- GROQ SETUP ---
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file!")
client = Groq(api_key=api_key, timeout=30.0)

# --- AUTH CONFIG ---
AUTH_EMAIL = os.getenv('AUTH_EMAIL', '')
AUTH_EMAIL_PASSWORD = os.getenv('AUTH_EMAIL_PASSWORD', '')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
DATABASE_URL = os.getenv('DATABASE_URL', '')
FREE_TIER_BYTES = 500 * 1024 * 1024  # 500 MB


# --- 2FA AUTHENTICATION ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            if request.is_json or request.headers.get('Accept') == 'text/event-stream':
                return jsonify({'error': 'Unauthorized', 'redirect': '/login'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def send_verification_email(code):
    """Send 2FA verification code via email."""
    if not AUTH_EMAIL or not AUTH_EMAIL_PASSWORD:
        print("[WARN] AUTH_EMAIL or AUTH_EMAIL_PASSWORD not set.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = AUTH_EMAIL
        msg['To'] = AUTH_EMAIL
        msg['Subject'] = f'Mooserage Chatbot - Verification Code: {code}'

        body = f"""
        <html>
        <body style="font-family: 'Inter', Arial, sans-serif; background: #FFF8E7; padding: 40px;">
            <div style="max-width: 400px; margin: 0 auto; background: #fff; border-radius: 16px; padding: 32px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
                <div style="text-align: center; margin-bottom: 24px;">
                    <div style="width: 48px; height: 48px; border-radius: 50%; background: linear-gradient(135deg, #E8862A, #F5C518); margin: 0 auto 12px; display: flex; align-items: center; justify-content: center;">
                        <span style="color: white; font-size: 20px; font-weight: bold;">M</span>
                    </div>
                    <h2 style="color: #2D2A26; margin: 0;">Mooserage Chatbot</h2>
                </div>
                <p style="color: #8A8278; font-size: 14px; text-align: center;">Your verification code is:</p>
                <div style="background: linear-gradient(135deg, #E8862A, #F5C518); border-radius: 12px; padding: 20px; text-align: center; margin: 16px 0;">
                    <span style="color: white; font-size: 32px; font-weight: 700; letter-spacing: 8px;">{code}</span>
                </div>
                <p style="color: #8A8278; font-size: 12px; text-align: center;">This code expires when you close the server. Do not share it with anyone.</p>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(AUTH_EMAIL, AUTH_EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[OK] Verification code sent to {AUTH_EMAIL}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


# --- AUTH ROUTES ---

@app.route('/login')
def login_page():
    if session.get('authenticated'):
        return redirect('/')
    return send_file(os.path.join(app.static_folder, 'login.html'))


@app.route('/auth/send-code', methods=['POST'])
def send_code():
    code = str(random.randint(100000, 999999))
    session['verification_code'] = code
    session['code_attempts'] = 0

    success = send_verification_email(code)
    masked = AUTH_EMAIL[:3] + '***' + AUTH_EMAIL[AUTH_EMAIL.index('@'):] if AUTH_EMAIL else '***'

    if success:
        return jsonify({'success': True, 'email': masked})
    else:
        return jsonify({'success': False, 'error': 'Failed to send email. Check SMTP settings.'}), 500


@app.route('/auth/verify', methods=['POST'])
def verify_code():
    data = request.get_json()
    entered_code = data.get('code', '')
    stored_code = session.get('verification_code', '')
    attempts = session.get('code_attempts', 0)

    if attempts >= 5:
        session.pop('verification_code', None)
        return jsonify({'success': False, 'error': 'Too many attempts. Request a new code.'}), 429

    session['code_attempts'] = attempts + 1

    if entered_code == stored_code:
        session['authenticated'] = True
        session.pop('verification_code', None)
        session.pop('code_attempts', None)
        return jsonify({'success': True})
    else:
        remaining = 5 - session['code_attempts']
        return jsonify({'success': False, 'error': f'Invalid code. {remaining} attempts remaining.'}), 400


@app.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


# --- ROUTES ---

@app.route('/')
@login_required
def index():
    return send_file(os.path.join(app.static_folder, 'index.html'))

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}


def sb_get(path, params=None):
    """GET request to Supabase REST API."""
    r = http_client.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS, params=params or {})
    r.raise_for_status()
    return r.json()


def sb_post(path, data):
    """POST request to Supabase REST API."""
    r = http_client.post(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()


def sb_patch(path, data):
    """PATCH request to Supabase REST API."""
    r = http_client.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()


def sb_delete(path):
    """DELETE request to Supabase REST API."""
    r = http_client.delete(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    r.raise_for_status()
    return True


def sb_rpc(fn_name):
    """Call a Supabase RPC function."""
    r = http_client.post(f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}", headers=HEADERS, json={})
    r.raise_for_status()
    return r.json()


# --- AUTO TABLE CREATION ---
def create_tables():
    if not DATABASE_URL:
        print("[ERROR] DATABASE_URL not set. Please create tables manually.")
        return False
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                last_updated TIMESTAMPTZ DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
                user_message TEXT NOT NULL,
                ai_message TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
            CREATE OR REPLACE FUNCTION get_db_size_bytes()
            RETURNS BIGINT LANGUAGE sql SECURITY DEFINER
            AS $$ SELECT pg_database_size(current_database()); $$;
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("[OK] Tables created successfully!")
        return True
    except Exception as e:
        print(f"[ERROR] Table creation failed: {e}")
        return False


def init_database():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[WARN] SUPABASE_URL/KEY not set. Running without database.")
        return False
    try:
        sb_get('sessions', {'select': 'id', 'limit': '1'})
        print("[OK] Database tables verified.")
        return True
    except Exception as e:
        err = str(e)
        if '404' in err or '42P01' in err or 'does not exist' in err.lower():
            print("[WARN] Tables not found. Auto-creating...")
            ok = create_tables()
            if ok:
                import time
                time.sleep(2)
            return ok
        print(f"[WARN] DB check error: {err}")
        return False


def format_size(b):
    for u in ['B', 'KB', 'MB', 'GB']:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


# --- ROUTES ---


@app.route('/sessions', methods=['GET'])
@login_required
def get_sessions():
    try:
        data = sb_get('sessions', {
            'select': 'id,title,last_updated',
            'order': 'last_updated.desc'
        })
        return jsonify({'sessions': data, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/sessions/<session_id>', methods=['GET'])
@login_required
def get_session_details(session_id):
    try:
        sessions = sb_get('sessions', {'id': f'eq.{session_id}'})
        if not sessions:
            return jsonify({'error': 'Not found', 'success': False}), 404
        session_data = sessions[0]
        msgs = sb_get('messages', {
            'session_id': f'eq.{session_id}',
            'select': 'user_message,ai_message,created_at',
            'order': 'created_at.asc'
        })
        session_data['messages'] = [
            {'user': m['user_message'], 'ai': m['ai_message'], 'timestamp': m['created_at']}
            for m in msgs
        ]
        return jsonify({'session': session_data, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/sessions/<session_id>/rename', methods=['PUT'])
@login_required
def rename_session(session_id):
    try:
        data = request.get_json()
        new_title = data.get('title')
        if not new_title:
            return jsonify({'error': 'No title'}), 400
        sb_patch(f'sessions?id=eq.{session_id}', {'title': new_title})
        return jsonify({'success': True, 'title': new_title})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/sessions/<session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    try:
        sb_delete(f'messages?session_id=eq.{session_id}')
        sb_delete(f'sessions?id=eq.{session_id}')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/sessions/clear-all', methods=['DELETE'])
@login_required
def clear_all_sessions():
    try:
        sb_delete('messages?created_at=gte.1970-01-01T00:00:00Z')
        sb_delete('sessions?created_at=gte.1970-01-01T00:00:00Z')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/storage', methods=['GET'])
@login_required
def get_storage():
    try:
        size_bytes = sb_rpc('get_db_size_bytes')
        if not isinstance(size_bytes, (int, float)):
            size_bytes = 0
        pct = (size_bytes / FREE_TIER_BYTES) * 100
        return jsonify({
            'size_bytes': size_bytes,
            'size_pretty': format_size(size_bytes),
            'limit_pretty': '500 MB',
            'percentage': round(pct, 1),
            'warning': pct >= 80,
            'critical': pct >= 95,
            'success': True
        })
    except Exception as e:
        return jsonify({
            'size_bytes': 0, 'size_pretty': 'N/A',
            'percentage': 0, 'warning': False, 'critical': False,
            'success': False
        })


# --- STREAMING CHAT ---
@app.route('/chat/stream', methods=['POST'])
@login_required
def chat_stream():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        session_id = data.get('session_id')

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        is_new_session = False
        current_session = None

        if session_id:
            try:
                sessions = sb_get('sessions', {'id': f'eq.{session_id}'})
                if sessions:
                    current_session = sessions[0]
            except Exception:
                current_session = None

        if not current_session:
            title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            result = sb_post('sessions', {'title': title})
            current_session = result[0] if isinstance(result, list) else result
            session_id = current_session['id']
            is_new_session = True

        # Get recent messages for context
        recent = sb_get('messages', {
            'session_id': f'eq.{session_id}',
            'select': 'user_message,ai_message',
            'order': 'created_at.asc',
            'limit': '10'
        })

        system_prompt = (
            "You are 'Mooserage Chatbot Assistant', a friendly, professional, and helpful AI "
            "assistant for the general public. You are capable of assisting with a wide variety "
            "of tasks including writing, general knowledge, planning, and problem-solving. "
            "Your responses are clear, polite, and accessible to everyone."
        )

        messages_payload = [{"role": "system", "content": system_prompt}]
        for msg in recent:
            messages_payload.append({"role": "user", "content": msg['user_message']})
            messages_payload.append({"role": "assistant", "content": msg['ai_message']})
        messages_payload.append({"role": "user", "content": user_message})

        def generate():
            full_response = ""
            try:
                yield f"data: {json.dumps({'session_id': session_id, 'title': current_session['title'], 'is_new': is_new_session})}\n\n"

                stream = client.chat.completions.create(
                    messages=messages_payload,
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True
                )

                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield f"data: {json.dumps({'content': content})}\n\n"

                sb_post('messages', {
                    'session_id': session_id,
                    'user_message': user_message,
                    'ai_message': full_response
                })
                sb_patch(f'sessions?id=eq.{session_id}', {
                    'last_updated': datetime.now().isoformat()
                })

                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


# --- INITIALIZE DATABASE ON STARTUP ---
print("[Mooserage] Initializing database...")
init_database()

if __name__ == '__main__':
    print("[Mooserage] Running on http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)