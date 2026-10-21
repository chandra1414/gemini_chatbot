import base64
import io
import json
import mimetypes
import os
import shutil
import time
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

st.set_page_config(page_title="Gemini Chatbot", page_icon="💬", layout="centered")

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "chats.json"  # all chats are saved here
UPLOAD_DIR = BASE_DIR / "uploads"    # uploaded images are saved here
MAX_HISTORY = 10                     # messages sent to the model (shorter prompt = faster)
MAX_DOC_CHARS = 150_000              # max characters of uploaded documents sent to the model

IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]
DOC_TYPES = ["pdf", "docx", "txt", "md", "csv", "json", "py"]

# ---------------- Custom styling ----------------
st.markdown(
    """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 820px;}

.hero-title {
    font-size: 2.6rem; font-weight: 800; text-align: center; margin-bottom: 0;
    background: linear-gradient(90deg, #8B5CF6, #3B82F6, #06B6D4);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-sub {text-align: center; color: #9AA4B8; margin: 4px 0 28px 0; font-size: 1.05rem;}

[data-testid="stChatMessage"] {
    background: #131A2B; border: 1px solid #222C45;
    border-radius: 16px; padding: 14px 18px; margin-bottom: 12px;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(135deg, #1E1B4B, #172554); border-color: #312E81;
}
[data-testid="stChatInput"] {border-radius: 28px; border: 1px solid #312E81;}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F1424, #131A2B);
    border-right: 1px solid #222C45;
}

.stButton > button {
    border-radius: 12px; border: 1px solid #312E81; background: #131A2B;
    transition: all .2s ease; padding: 10px 10px; width: 100%;
    text-align: left; justify-content: flex-start;
}
.stButton > button:hover {
    border-color: #8B5CF6; background: #1E1B4B; transform: translateY(-1px);
}
/* active chat (primary button) */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #4C1D95, #1D4ED8); border-color: #8B5CF6; color: white;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- API key ----------------
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("GOOGLE_API_KEY not found. Add it to your .env file and restart.")
    st.stop()


# ---------------- Saving / loading chats ----------------
def load_data():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_data():
    try:
        DATA_FILE.write_text(
            json.dumps(
                {"chats": st.session_state.chats, "current": st.session_state.current_id},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        st.warning(f"Could not save chats: {e}")


def new_chat():
    # Don't create another empty chat if the current one is already empty
    cur = st.session_state.chats.get(st.session_state.get("current_id"))
    if cur is not None and not cur["messages"]:
        return
    cid = uuid.uuid4().hex[:8]
    st.session_state.chats[cid] = {"title": "New chat", "messages": [], "docs": [], "created": time.time()}
    st.session_state.current_id = cid
    save_data()


def switch_chat(cid):
    st.session_state.current_id = cid
    save_data()


def delete_chat(cid):
    st.session_state.chats.pop(cid, None)
    shutil.rmtree(UPLOAD_DIR / cid, ignore_errors=True)
    if st.session_state.current_id == cid:
        if st.session_state.chats:
            latest = max(st.session_state.chats, key=lambda k: st.session_state.chats[k]["created"])
            st.session_state.current_id = latest
        else:
            st.session_state.current_id = None
            new_chat()
    save_data()


def set_pending(text):
    st.session_state.pending = text


# ---------------- File handling ----------------
def extract_document_text(name, data):
    """Return plain text from a PDF / DOCX / text file."""
    ext = name.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            pages.append(f"[Page {i}]\n{page.extract_text() or ''}")
        return "\n\n".join(pages)
    if ext == "docx":
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    return data.decode("utf-8", errors="ignore")


def process_uploads(files, chat_id):
    """Save images to disk, extract text from documents. Returns (names, image_paths)."""
    names, image_paths = [], []
    for f in files:
        name = f.name
        data = f.getvalue()
        ext = name.rsplit(".", 1)[-1].lower()
        names.append(name)
        if ext in IMAGE_TYPES:
            folder = UPLOAD_DIR / chat_id
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{uuid.uuid4().hex[:6]}_{name}"
            path.write_bytes(data)
            image_paths.append(path.relative_to(BASE_DIR).as_posix())
        else:
            try:
                text = extract_document_text(name, data).strip()
            except Exception as e:
                st.warning(f"Could not read {name}: {e}")
                continue
            if not text:
                st.warning(f"No readable text found in {name} (scanned PDF?).")
                continue
            st.session_state.chats[chat_id].setdefault("docs", []).append(
                {"name": name, "text": text}
            )
    return names, image_paths


def image_part(rel_path):
    path = BASE_DIR / rel_path
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


# ---------------- Session state ----------------
if "chats" not in st.session_state:
    data = load_data()
    st.session_state.chats = data.get("chats", {})
    st.session_state.current_id = data.get("current")
    if st.session_state.current_id not in st.session_state.chats:
        st.session_state.current_id = None
        if st.session_state.chats:
            st.session_state.current_id = max(
                st.session_state.chats, key=lambda k: st.session_state.chats[k]["created"]
            )
        else:
            new_chat()
if "pending" not in st.session_state:
    st.session_state.pending = None

chat = st.session_state.chats[st.session_state.current_id]
messages = chat["messages"]

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("## 💬 Gemini Chat")
    st.button("➕ New chat", on_click=new_chat, key="new_chat_btn")
    st.markdown("**Your chats**")

    with st.container(height=300, border=False):
        ordered = sorted(st.session_state.chats.items(), key=lambda kv: kv[1]["created"], reverse=True)
        for cid, c in ordered:
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.button(
                    f"💬 {c['title']}",
                    key=f"chat_{cid}",
                    on_click=switch_chat,
                    args=(cid,),
                    type="primary" if cid == st.session_state.current_id else "secondary",
                )
            with col_b:
                st.button("🗑️", key=f"del_{cid}", on_click=delete_chat, args=(cid,), help="Delete this chat")

    if chat.get("docs"):
        with st.expander(f"📎 Files in this chat ({len(chat['docs'])})"):
            for d in chat["docs"]:
                st.caption(f"📄 {d['name']}")

    with st.expander("⚙️ Settings"):
        model_name = st.text_input("Model", value="gemini-3.5-flash-lite")
        temperature = st.slider("Creativity", 0.0, 1.0, 0.7, 0.1)
        fast_mode = st.checkbox("⚡ Fast mode", value=True)

    st.caption(f"{len(st.session_state.chats)} chats saved • Built with Streamlit, LangChain & Gemini")

# ---------------- LLM ----------------
llm_kwargs = {}
if fast_mode:
    llm_kwargs["thinking_level"] = "low"

llm = ChatGoogleGenerativeAI(
    model=model_name,
    temperature=temperature,
    google_api_key=api_key,
    timeout=30,
    max_retries=1,
    **llm_kwargs,
)


def build_history():
    """System prompt (with uploaded documents) + recent messages = memory."""
    system = "You are a helpful, friendly AI assistant."
    docs = chat.get("docs", [])
    if docs:
        system += (
            "\n\nThe user has uploaded the files below. Use them to answer questions about them. "
            "If the answer is not in the files, say so.\n"
        )
        budget = MAX_DOC_CHARS
        for d in docs:
            text = d["text"][:budget]
            budget -= len(text)
            system += f"\n=== FILE: {d['name']} ===\n{text}\n"
            if budget <= 0:
                break

    history = [SystemMessage(content=system)]
    for m in messages[-MAX_HISTORY:]:
        if m["role"] == "user":
            imgs = m.get("images", [])
            if imgs:
                content = [{"type": "text", "text": m["content"]}]
                for rel in imgs:
                    try:
                        content.append(image_part(rel))
                    except Exception:
                        pass
                history.append(HumanMessage(content=content))
            else:
                history.append(HumanMessage(content=m["content"]))
        else:
            history.append(AIMessage(content=m["content"]))
    return history


def extract_text(chunk):
    text = getattr(chunk, "text", None)
    if callable(text):
        text = text()
    if isinstance(text, str) and text:
        return text
    content = chunk.content
    if isinstance(content, str):
        return content
    out = ""
    for part in content or []:
        if isinstance(part, str):
            out += part
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            if part.get("type", "text") == "text":
                out += part["text"]
    return out


def token_stream(history):
    for chunk in llm.stream(history):
        text = extract_text(chunk)
        if text:
            yield text


# ---------------- Input (typed or suggestion click) ----------------
try:
    typed = st.chat_input(
        "Ask me anything, or attach a file (📎)...",
        accept_file="multiple",
        file_type=IMAGE_TYPES + DOC_TYPES,
    )
except TypeError:  # older Streamlit without file support
    typed = st.chat_input("Ask me anything...")
    st.sidebar.warning("Run: pip install -U streamlit  (needed for file upload)")

files = []
prompt = None
if typed is not None:
    if isinstance(typed, str):
        prompt = typed
    else:
        prompt = (getattr(typed, "text", "") or "").strip()
        files = list(getattr(typed, "files", []) or [])
        if files and not prompt:
            prompt = "Please summarize / describe the attached file(s)."
        if not prompt:
            prompt = None
elif st.session_state.pending:
    prompt = st.session_state.pending
st.session_state.pending = None

# ---------------- Welcome screen / title ----------------
if not messages and not prompt:
    st.markdown('<div class="hero-title">Gemini Chatbot</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-sub">Your AI assistant. Ask anything, get answers in real time.</div>',
        unsafe_allow_html=True,
    )
    suggestions = [
        "💡 Explain AI in simple words",
        "🐍 Write a Python function to reverse a string",
        "📚 Give me a 7-day study plan for Data Science",
        "✉️ Write a professional email asking for leave",
    ]
    c1, c2 = st.columns(2)
    for i, s in enumerate(suggestions):
        with (c1 if i % 2 == 0 else c2):
            st.button(s, key=f"sugg_{i}", on_click=set_pending, args=(s,))
else:
    st.markdown('<div class="hero-title" style="font-size:1.8rem">Gemini Chatbot</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

# ---------------- Show history of the current chat ----------------
for m in messages:
    avatar = "🧑‍💻" if m["role"] == "user" else "💬"
    with st.chat_message(m["role"], avatar=avatar):
        for rel in m.get("images", []):
            if (BASE_DIR / rel).exists():
                st.image(str(BASE_DIR / rel), width=260)
        other = [n for n in m.get("files", []) if not n.lower().endswith(tuple(IMAGE_TYPES))]
        if other:
            st.caption("📎 " + ", ".join(other))
        st.markdown(m["content"])

# ---------------- Handle new message ----------------
if prompt:
    names, image_paths = [], []
    if files:
        with st.spinner("Reading your files..."):
            names, image_paths = process_uploads(files, st.session_state.current_id)
    messages.append({"role": "user", "content": prompt, "files": names, "images": image_paths})
    if chat["title"] == "New chat":
        chat["title"] = prompt[:28] + ("…" if len(prompt) > 28 else "")
    with st.chat_message("user", avatar="🧑‍💻"):
        for rel in image_paths:
            st.image(str(BASE_DIR / rel), width=260)
        docs_only = [n for n in names if not n.lower().endswith(tuple(IMAGE_TYPES))]
        if docs_only:
            st.caption("📎 " + ", ".join(docs_only))
        st.markdown(prompt)

    success = False
    with st.chat_message("assistant", avatar="💬"):
        try:
            history = build_history()
            reply = st.write_stream(token_stream(history))

            if not reply or not str(reply).strip():
                response = llm.invoke(history)
                reply = extract_text(response)
                if reply.strip():
                    st.markdown(reply)

            if reply and str(reply).strip():
                messages.append({"role": "assistant", "content": reply})
                success = True
            else:
                st.warning("The model returned an empty response. Try a different model name in Settings.")
                messages.pop()
        except Exception as e:
            st.error(f"Something went wrong: {e}")
            messages.pop()

    save_data()
    if success:
        st.rerun()  # refresh sidebar so the new chat title shows up