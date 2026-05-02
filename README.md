# Mooserage Chatbot Assistant

A modern, AI-powered chatbot built with Flask and Groq (LLaMA 3.3 70B), featuring real-time streaming responses, persistent cloud storage via Supabase, and a premium warm-toned UI.

---

## Features

### Core Chat
- **AI-Powered Conversations** — Uses Groq's LLaMA 3.3 70B model for fast, intelligent responses
- **Real-Time Streaming** — Responses stream token-by-token via Server-Sent Events (SSE), just like ChatGPT
- **Markdown Rendering** — AI responses support full markdown: bold, lists, code blocks, headings, links
- **Voice Input** — Built-in speech-to-text via Web Speech API (Chrome/Edge)
- **Contextual Memory** — Each session retains the last 10 message pairs for coherent multi-turn conversations

### Session Management
- **Multiple Sessions** — Create unlimited chat sessions, each stored independently
- **Session History** — Sidebar displays all past sessions, sorted by last activity
- **Rename Sessions** — Click the edit icon to rename any session
- **Delete Individual Sessions** — Remove specific sessions with a confirmation modal
- **Clear All Sessions** — Bulk delete all sessions with a safety confirmation dialog
- **Auto-Titled Sessions** — New sessions are automatically titled based on the first message

### Cloud Storage (Supabase)
- **Persistent Storage** — All sessions and messages stored in Supabase PostgreSQL (replaces local JSON file)
- **Auto Table Creation** — On first run, the app automatically creates required database tables if they don't exist
- **Cascading Deletes** — Deleting a session automatically removes all its associated messages
- **Storage Monitoring** — Real-time database usage indicator in the sidebar footer
- **Free Tier Awareness** — Warning banner at 80% usage, critical alert at 95% of Supabase's 500 MB free tier
- **Confirmation Modals** — All destructive actions (delete, clear) require explicit confirmation via custom modals

### UI/UX Design
- **Custom Color Palette** — Warm, vibrant design using Orange (#E8862A), Gold (#F5C518), Cream (#FFF8E7), and Light Blue (#7EAAD0)
- **Dark Mode** — Full dark/light theme toggle with deep navy dark mode
- **Glassmorphism Sidebar** — Translucent sidebar with backdrop blur effect
- **Animated Typing Indicator** — Bouncing dots animation while AI generates responses
- **Sidebar Loading States** — Spinner with status text during all API operations (generating, deleting, renaming, loading)
- **Micro-Animations** — Smooth slide-in messages, hover effects, button press feedback
- **Responsive Design** — Mobile-friendly with collapsible sidebar and touch-optimized layout
- **Custom Confirmation Modals** — Styled glassmorphism modals replace native browser dialogs

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python / Flask |
| **AI Model** | Groq API (LLaMA 3.3 70B Versatile) |
| **Database** | Supabase (PostgreSQL) |
| **Frontend** | Vanilla HTML, CSS, JavaScript |
| **Markdown** | marked.js + DOMPurify |
| **Fonts** | Google Fonts (Inter) |
| **Voice** | Web Speech API |

---

## Project Structure

```
mooserage_chatbot/
├── app.py                  # Flask backend — routes, Supabase API, streaming chat
├── .env                    # Environment variables (API keys, database credentials)
├── .gitignore              # Git ignore rules
├── static/
│   ├── index.html          # Main HTML page structure
│   ├── styles.css          # Complete CSS — color palette, animations, responsive
│   └── app.js              # Frontend JavaScript — chat logic, modals, sidebar
└── conversation_history.json  # Legacy local storage (no longer used)
```

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- A [Groq](https://console.groq.com/) API key
- A [Supabase](https://supabase.com/) project (free tier works)

### 1. Clone & Install Dependencies

```bash
git clone <your-repo-url>
cd mooserage_chatbot
python -m venv env
env\Scripts\activate        # Windows
# source env/bin/activate   # macOS/Linux

pip install flask flask-cors python-dotenv groq requests psycopg2-binary
```

### 2. Configure Environment Variables

Edit `.env` with your actual credentials:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here

# Supabase Configuration
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your_supabase_anon_or_publishable_key
DATABASE_URL=postgresql://postgres.your-project-ref:your-password@aws-0-region.pooler.supabase.com:5432/postgres
```

**Where to find these:**
| Variable | Location in Dashboard |
|----------|----------------------|
| `SUPABASE_URL` | Project Settings → General → Project URL |
| `SUPABASE_KEY` | Project Settings → API Keys → Publishable key |
| `DATABASE_URL` | Project Settings → Database → Connection String (URI) |

### 3. Run the App

```bash
flask run
```

On first launch, the app will:
1. Check if database tables exist in Supabase
2. If not found, automatically create `sessions`, `messages` tables and the `get_db_size_bytes()` function
3. Start serving on `http://127.0.0.1:5000`

---

## API Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the chatbot frontend |
| `GET` | `/sessions` | Lists all chat sessions (id, title, last_updated) |
| `GET` | `/sessions/<id>` | Gets a specific session with all its messages |
| `PUT` | `/sessions/<id>/rename` | Renames a session |
| `DELETE` | `/sessions/<id>` | Deletes a specific session and its messages |
| `DELETE` | `/sessions/clear-all` | Deletes ALL sessions and messages |
| `POST` | `/chat/stream` | Sends a message and streams AI response via SSE |
| `GET` | `/storage` | Returns database storage usage stats |

---

## Database Schema

### `sessions` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated session ID |
| `title` | TEXT | Session title (auto-generated from first message) |
| `created_at` | TIMESTAMPTZ | Session creation timestamp |
| `last_updated` | TIMESTAMPTZ | Last activity timestamp |

### `messages` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated message ID |
| `session_id` | UUID (FK) | References sessions.id (CASCADE delete) |
| `user_message` | TEXT | The user's message |
| `ai_message` | TEXT | The AI's response |
| `created_at` | TIMESTAMPTZ | Message timestamp |

---

## Storage Monitoring

The app monitors Supabase database usage against the free tier limit (500 MB):

| Usage Level | Indicator | Action |
|-------------|-----------|--------|
| 0–79% | Blue progress bar | Normal operation |
| 80–94% | Yellow progress bar + warning banner | Consider deleting old sessions |
| 95–100% | Red progress bar + critical banner | Prompted to free up space immediately |

> **Note:** The storage indicator shows the *total* PostgreSQL database size, which includes ~8-15 MB of system overhead (catalogs, extensions, indexes). This is normal even with zero conversations stored.

---

## Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Orange | `#E8862A` | Primary accent, user message bubbles, buttons, active states |
| Gold | `#F5C518` | Highlights, warnings, hover effects |
| Cream | `#FFF8E7` | Light mode background |
| Light Blue | `#7EAAD0` | AI message bubbles, secondary accent, storage bar |
| Deep Navy | `#1A1A2E` | Dark mode background |

---

## License

This project is for personal use. All rights reserved.
