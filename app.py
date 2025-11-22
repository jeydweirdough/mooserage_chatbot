from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
from datetime import datetime
from groq import Groq

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize Groq client with explicit configuration
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file!")

client = Groq(
    api_key=api_key,
    timeout=30.0
)

# File path for conversation history
HISTORY_FILE = 'conversation_history.json'

# Initialize history file if it doesn't exist
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'w') as f:
        json.dump([], f)

# Route to serve the HTML file
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Get conversation history
@app.route('/history', methods=['GET'])
def get_history():
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        return jsonify({'history': history, 'success': True})
    except Exception as e:
        print(f"Error reading history: {str(e)}")
        return jsonify({'history': [], 'success': True})

# Clear conversation history
@app.route('/history/clear', methods=['POST'])
def clear_history():
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump([], f)
        return jsonify({'success': True, 'message': 'History cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Save message to history
def save_to_history(user_message, ai_response):
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        
        history.append({
            'timestamp': datetime.now().isoformat(),
            'user': user_message,
            'ai': ai_response
        })
        
        # Keep only last 50 conversations
        if len(history) > 50:
            history = history[-50:]
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving history: {str(e)}")

# Chat endpoint (non-streaming)
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant created for CvSU students. You are knowledgeable, friendly, and provide clear explanations."
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stream=False
        )
        
        ai_message = chat_completion.choices[0].message.content
        
        # Save to history
        save_to_history(user_message, ai_message)
        
        return jsonify({
            'response': ai_message,
            'success': True,
            'model': 'llama-3.3-70b-versatile'
        })
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

# Streaming chat endpoint
@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        def generate():
            try:
                full_response = ""
                
                # Call Groq API with streaming
                stream = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant created for CvSU students. You are knowledgeable, friendly, and provide clear explanations."
                        },
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                    max_tokens=1024,
                    top_p=1,
                    stream=True
                )
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield f"data: {json.dumps({'content': content})}\n\n"
                
                # Save to history after streaming is complete
                save_to_history(user_message, full_response)
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

# Text-to-speech endpoint (optional, requires pyttsx3 or gTTS)
@app.route('/tts', methods=['POST'])
def text_to_speech():
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Note: For actual TTS, you would need to install and use a TTS library
        # This is a placeholder response
        return jsonify({
            'success': True,
            'message': 'TTS functionality requires additional setup'
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

# Run the Flask app
if __name__ == '__main__':
    print("🚀 Starting AI Chatbot with Groq API (Llama 3.3 70B)")
    print("📍 Server running at: http://127.0.0.1:5000/")
    print("✨ Features: Streaming, History Storage, Dark Mode, Speech Input")
    print("💾 Conversation history saved to:", HISTORY_FILE)
    app.run(debug=True, host='127.0.0.1', port=5000)