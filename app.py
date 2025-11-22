from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import uuid
from datetime import datetime
from groq import Groq

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize Groq
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file!")

client = Groq(api_key=api_key, timeout=30.0)

HISTORY_FILE = 'conversation_history.json'
MAX_SESSIONS = 20

# --- SESSION MANAGEMENT ---

def load_data():
    if not os.path.exists(HISTORY_FILE):
        return {"sessions": []}
    try:
        with open(HISTORY_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, list): return {"sessions": []}
            return data
    except Exception:
        return {"sessions": []}

def save_data(data):
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def get_session(session_id, data):
    for session in data['sessions']:
        if session['id'] == session_id:
            return session
    return None

def create_session(first_message, data):
    title = first_message[:30] + "..." if len(first_message) > 30 else first_message
    new_session = {
        "id": str(uuid.uuid4()),
        "title": title,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "messages": []
    }
    data['sessions'].insert(0, new_session)
    if len(data['sessions']) > MAX_SESSIONS:
        data['sessions'] = data['sessions'][:MAX_SESSIONS]
    return new_session

# --- ROUTES ---

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/sessions', methods=['GET'])
def get_sessions():
    data = load_data()
    summary = [{'id': s['id'], 'title': s['title'], 'last_updated': s['last_updated']} for s in data['sessions']]
    return jsonify({'sessions': summary, 'success': True})

@app.route('/sessions/<session_id>', methods=['GET'])
def get_session_details(session_id):
    data = load_data()
    session = get_session(session_id, data)
    if session:
        return jsonify({'session': session, 'success': True})
    return jsonify({'error': 'Session not found', 'success': False}), 404

@app.route('/sessions/<session_id>/rename', methods=['PUT'])
def rename_session(session_id):
    try:
        data = request.get_json()
        new_title = data.get('title')
        if not new_title:
            return jsonify({'error': 'No title provided'}), 400
            
        db_data = load_data()
        session = get_session(session_id, db_data)
        if session:
            session['title'] = new_title
            save_data(db_data)
            return jsonify({'success': True, 'title': new_title})
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    try:
        db_data = load_data()
        initial_count = len(db_data['sessions'])
        db_data['sessions'] = [s for s in db_data['sessions'] if s['id'] != session_id]
        
        if len(db_data['sessions']) < initial_count:
            save_data(db_data)
            return jsonify({'success': True})
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- STREAMING CHAT ---
@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        session_id = data.get('session_id')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        db_data = load_data()
        current_session = get_session(session_id, db_data)
        
        is_new_session = False
        if not current_session:
            current_session = create_session(user_message, db_data)
            session_id = current_session['id']
            is_new_session = True
        
        # UPDATED PERSONA: Mooserage Chatbot Assistant
        system_prompt = "You are 'Mooserage Chatbot Assistant', a friendly, professional, and helpful AI assistant for the general public. You are capable of assisting with a wide variety of tasks including writing, general knowledge, planning, and problem-solving. Your responses are clear, polite, and accessible to everyone."
        
        messages_payload = [{"role": "system", "content": system_prompt}]
        for msg in current_session['messages'][-10:]:
            messages_payload.append({"role": "user", "content": msg['user']})
            messages_payload.append({"role": "assistant", "content": msg['ai']})
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
                
                current_session['messages'].append({
                    'timestamp': datetime.now().isoformat(),
                    'user': user_message,
                    'ai': full_response
                })
                current_session['last_updated'] = datetime.now().isoformat()
                
                if current_session in db_data['sessions']:
                    db_data['sessions'].remove(current_session)
                db_data['sessions'].insert(0, current_session)
                
                save_data(db_data)
                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

if __name__ == '__main__':
    print("🚀 Mooserage Chatbot Assistant Running on http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)