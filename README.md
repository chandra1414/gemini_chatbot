# 💬 Interactive Full-Stack AI Chatbot with Streamlit

A web-based chatbot built with **Streamlit**, **LangChain** and **Google Gemini**. It supports real-time streaming responses, chat history and conversation memory.

## Features
- Chat UI using `st.chat_message` and `st.chat_input`
- Streaming token-by-token responses
- Conversation memory (full history sent to the model each turn)
- Session state management with a "Clear chat" button
- Model and temperature controls in the sidebar
- Error handling (missing API key, API failures)

## Tech Stack
Python 3, Streamlit, LangChain, Google Gemini API

## Project Structure
```
full-stack AI chatbot
    ├── app.py              # main Streamlit app
    ├── requirements.txt    # dependencies
    ├── .env                # your real API key (create from .env.example)
    ├── .env.example        # template showing what goes in .env
    ├── .gitignore          # keeps .env out of GitHub (add this)
    └── README.md           # setup steps + screenshots (add this)
```

## Setup
1. Clone or download this project.
2. (Optional) Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # Mac/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Get a free API key from https://aistudio.google.com/apikey
5. Create a `.env` file (copy `.env.example`) and add:
   ```
   GOOGLE_API_KEY=your_key_here
   ```
6. Run the app:
   ```
   streamlit run app.py
   ```
7. Open http://localhost:8501 in your browser.

## How It Works
- **Session state:** `st.session_state.messages` stores the chat so it survives Streamlit reruns.
- **Memory:** every request sends the full message history to Gemini, so it remembers earlier turns.
- **Streaming:** LangChain's `.stream()` yields chunks, and `st.write_stream` displays them live.

## Screenshots
_Add screenshots of your app here._

## Author
Your Name