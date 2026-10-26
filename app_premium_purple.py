import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import time
import uuid
from urllib.parse import urlparse

import streamlit as st

import agent
from agent import app as graph, llm, to_text

st.set_page_config(page_title="AGENTIC RAG", layout="wide")

ROUTE_LABEL = {"vectorstore": "Papers", "web_search": "Web search",
               "general": "General knowledge", "direct": "Direct answer"}
ROUTE_COLOR = {"vectorstore": "#2563EB", "web_search": "#0891B2",
               "general": "#7C3AED", "direct": "#D97706"}
CHATS_FILE = "chats.json"
USERS_FILE = "users.json"
FEEDBACK_FILE = "feedback.jsonl"
EXAMPLES = [
    "How does QLoRA reduce memory usage?",
    "What is an LLM?",
    "Compare LoRA and QLoRA memory usage",
    "Who is the CEO of Nvidia?",
]
PROVIDER_LABELS = {
    "google": "Continue with Google",
    "microsoft": "Continue with Microsoft",
    "auth0": "Continue with Facebook, GitHub and more",
    "okta": "Continue with Okta",
}
SITE_NAMES = {
    "wikipedia": "Wikipedia", "ibm": "IBM", "aws": "AWS", "nvidia": "NVIDIA", "github": "GitHub",
    "arxiv": "arXiv", "huggingface": "Hugging Face", "medium": "Medium",
    "geeksforgeeks": "GeeksforGeeks", "youtube": "YouTube", "openai": "OpenAI",
    "google": "Google", "microsoft": "Microsoft", "mit": "MIT", "stanford": "Stanford",
    "oracle": "Oracle", "cloudflare": "Cloudflare", "techtarget": "TechTarget",
    "coursera": "Coursera", "datacamp": "DataCamp", "anthropic": "Anthropic",
    "towardsdatascience": "Towards Data Science", "nih": "NIH", "britannica": "Britannica",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow", "kaggle": "Kaggle",
}

# ---------------- premium purple / black theme ----------------
st.markdown("""
<style>
:root {
  --bg: #07050d; --panel: rgba(20, 14, 32, .78); --panel-strong: rgba(26, 18, 42, .94);
  --line: rgba(167, 139, 250, .22); --purple: #a78bfa; --violet: #8b5cf6;
  --pink: #e879f9; --text: #f4efff; --muted: #b8adc9;
}
.stApp {
  background: radial-gradient(ellipse at 12% 0%, rgba(109,40,217,.24), transparent 38%),
              radial-gradient(ellipse at 90% 16%, rgba(192,38,211,.14), transparent 34%),
              linear-gradient(145deg, #07050d 0%, #0d0817 48%, #090611 100%);
  background-attachment: fixed; color: var(--text); isolation: isolate;
}
.stApp::before, .stApp::after { content:""; position:fixed; width:440px; height:440px; border-radius:50%;
  filter:blur(100px); pointer-events:none; z-index:0; opacity:.24; }
.stApp::before { top:-170px; left:-100px; background:#7c3aed; animation:orbFloatA 19s ease-in-out infinite; }
.stApp::after { right:-150px; bottom:-190px; background:#c026d3; animation:orbFloatB 23s ease-in-out infinite; }
[data-testid="stAppViewContainer"] { position:relative; z-index:1; }
[data-testid="stHeader"] { background:rgba(7,5,13,.35); backdrop-filter:blur(14px); }
[data-testid="stMainBlockContainer"], .block-container { padding-top:2rem; padding-bottom:3rem; max-width:1450px; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,rgba(13,8,23,.98),rgba(9,6,17,.98));
  border-right:1px solid rgba(167,139,250,.18); }
[data-testid="stSidebar"] > div:first-child { background:transparent; }
[data-testid="stSidebar"] h1 { color:#e9d5ff; letter-spacing:.11em; font-weight:850;
  text-shadow:0 0 24px rgba(168,85,247,.38); }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color:#d8b4fe; }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#c9bfd8; }
[data-testid="stSidebar"] hr { border-color:rgba(167,139,250,.18); }
[data-testid="stChatMessage"] { background:linear-gradient(135deg,rgba(28,19,43,.9),rgba(15,11,25,.92));
  border:1px solid var(--line); border-radius:20px; padding:16px 18px; margin:12px 0;
  box-shadow:0 12px 32px rgba(0,0,0,.20); backdrop-filter:blur(18px); animation:fadeUp .42s ease both; }
[data-testid="stChatMessage"]:hover { border-color:rgba(192,132,252,.42); box-shadow:0 14px 34px rgba(91,33,182,.13); }
[data-testid="stExpander"] { border:1px solid rgba(167,139,250,.22); border-radius:15px;
  background:rgba(19,13,30,.72); overflow:hidden; }
[data-testid="stExpander"] summary { color:#e9d5ff; }
[data-testid="stForm"] { background:linear-gradient(145deg,rgba(27,18,42,.9),rgba(13,9,22,.94));
  border:1px solid rgba(167,139,250,.25); border-radius:22px; padding:20px;
  box-shadow:0 20px 55px rgba(0,0,0,.28); backdrop-filter:blur(20px); }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:8px; border-bottom:1px solid rgba(167,139,250,.18); }
[data-testid="stTabs"] button[role="tab"] { border-radius:10px 10px 0 0; color:#b8adc9; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color:#f5d0fe; border-bottom-color:#c084fc; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  color:#fff; background:linear-gradient(110deg,#7c3aed 0%,#9333ea 52%,#c026d3 100%);
  border:1px solid rgba(216,180,254,.26); border-radius:12px; font-weight:650; min-height:2.55rem;
  box-shadow:0 5px 18px rgba(124,58,237,.16); transition:transform .2s ease, box-shadow .2s ease, filter .2s ease;
}
.stButton > button *, .stDownloadButton > button *, [data-testid="stFormSubmitButton"] > button * { color:#fff !important; }
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  transform:translateY(-2px); filter:brightness(1.12); box-shadow:0 9px 27px rgba(168,85,247,.32); border-color:rgba(232,121,249,.6); }
.stButton > button:active { transform:translateY(0) scale(.99); }
.stTextInput input, .stTextArea textarea, .stNumberInput input, [data-testid="stChatInput"] textarea {
  background:rgba(12,8,20,.82) !important; color:#f5f3ff !important;
  border:1px solid rgba(167,139,250,.25) !important; border-radius:13px !important; }
.stTextInput input:focus, .stTextArea textarea:focus, [data-testid="stChatInput"]:focus-within {
  border-color:#c084fc !important; box-shadow:0 0 0 1px rgba(192,132,252,.35),0 0 24px rgba(147,51,234,.16) !important; }
[data-baseweb="select"] > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div { background:rgba(15,10,25,.88); border-color:rgba(167,139,250,.25); border-radius:11px; }
[data-testid="stSlider"] [role="slider"] { background:#c084fc; border-color:#c084fc; }
[data-testid="stToggle"] [data-checked="true"] { background:#8b5cf6; }
[data-testid="stChatInput"] { border-radius:17px; }
[data-testid="stChatInput"] > div { background:rgba(17,11,28,.94); border:1px solid rgba(167,139,250,.3); border-radius:17px; }
[data-testid="stChatInput"] button { color:#e9d5ff; }
a { color:#d8b4fe; }
a:hover { color:#f0abfc; }
.hero { position:relative; overflow:hidden; background:linear-gradient(115deg,rgba(76,29,149,.34),rgba(49,17,72,.24) 52%,rgba(131,24,67,.18));
  border:1px solid rgba(192,132,252,.28); padding:27px 31px; border-radius:24px; margin-bottom:22px;
  box-shadow:0 16px 48px rgba(0,0,0,.23), inset 0 1px rgba(255,255,255,.04); backdrop-filter:blur(18px);
  animation:fadeUp .65s ease both; }
.hero::before { content:""; position:absolute; inset:-1px; pointer-events:none; opacity:.7;
  background:linear-gradient(110deg,transparent 10%,rgba(216,180,254,.09) 45%,transparent 70%);
  background-size:220% 100%; animation:heroSweep 9s linear infinite; }
.hero h1 { position:relative; background:linear-gradient(90deg,#f5d0fe 0%,#c4b5fd 42%,#e879f9 78%,#ddd6fe 100%);
  background-size:220% 100%; -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
  color:transparent; margin:0; padding:0; font-size:clamp(2rem,3.5vw,2.8rem); line-height:1.12; font-weight:850; letter-spacing:-.035em;
  animation:gradientShift 10s ease infinite; }
.hero p { position:relative; margin:9px 0 0; color:#d2c5e5; line-height:1.6; }
.hero-center { text-align:center; }
.badge { display:inline-block; padding:5px 11px; border:1px solid rgba(255,255,255,.12); border-radius:999px;
  font-size:.78rem; font-weight:650; margin:4px 6px 4px 0; color:#fff; box-shadow:0 3px 12px rgba(0,0,0,.12); animation:popIn .3s ease both; }
[data-testid="stMetric"] { background:rgba(24,15,38,.72); border:1px solid rgba(167,139,250,.2); border-radius:16px; padding:16px; }
[data-testid="stMetricValue"] { color:#f5d0fe; }
[data-testid="stAlert"] { border-radius:14px; }
hr { border-color:rgba(167,139,250,.18); }
@keyframes fadeUp { from {opacity:0;transform:translateY(12px)} to {opacity:1;transform:translateY(0)} }
@keyframes popIn { from {opacity:0;transform:scale(.96)} to {opacity:1;transform:scale(1)} }
@keyframes orbFloatA { 0%,100% {transform:translate(0,0) scale(1)} 50% {transform:translate(70px,55px) scale(1.12)} }
@keyframes orbFloatB { 0%,100% {transform:translate(0,0) scale(1)} 50% {transform:translate(-65px,-45px) scale(1.13)} }
@keyframes gradientShift { 0%,100% {background-position:0% 50%} 50% {background-position:100% 50%} }
@keyframes heroSweep { 0% {background-position:120% 0} 100% {background-position:-120% 0} }
@media (max-width: 700px) { .hero {padding:21px 18px;border-radius:18px} [data-testid="stChatMessage"] {padding:12px;border-radius:15px} }
@media (prefers-reduced-motion: reduce) { *,*::before,*::after {animation:none !important;transition:none !important;scroll-behavior:auto !important} }
</style>
""", unsafe_allow_html=True)

def hero(title, subtitle, center=False):
    cls = "hero hero-center" if center else "hero"
    st.markdown(f'<div class="{cls}"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def badge(text, color):
    return f'<span class="badge" style="background:{color}">{text}</span>'


# ---------------- chat storage (one file per user) ----------------
def chats_path():
    return "chats_" + st.session_state["user"] + ".json"


def load_chats():
    if st.session_state.get("guest"):
        return {}
    if os.path.exists(chats_path()):
        try:
            return json.load(open(chats_path(), encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_chats():
    if st.session_state.get("guest"):
        return
    keep = {k: v for k, v in st.session_state["chats"].items() if v["messages"]}
    with open(chats_path(), "w", encoding="utf-8") as f:
        json.dump(keep, f)


def new_chat():
    cid = uuid.uuid4().hex[:8]
    st.session_state["chats"][cid] = {"title": "New chat", "created": time.time(), "messages": []}
    st.session_state["chat_id"] = cid


def latest_chat_id():
    chats = st.session_state["chats"]
    return max(chats, key=lambda c: chats[c]["created"])


def current_chat():
    return st.session_state["chats"][st.session_state["chat_id"]]


def cb_new_chat():
    new_chat()


def cb_pick():
    st.session_state["chat_id"] = st.session_state["chat_picker"]


def cb_clear():
    chat = current_chat()
    chat["messages"] = []
    chat["title"] = "New chat"
    save_chats()


def cb_delete():
    st.session_state["chats"].pop(st.session_state["chat_id"], None)
    if st.session_state["chats"]:
        st.session_state["chat_id"] = latest_chat_id()
    else:
        new_chat()
    save_chats()


# ---------------- accounts and login ----------------
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            return json.load(open(USERS_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f)


def hash_pw(password, salt_hex):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200000).hex()


def create_account(username, password, confirm):
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,20}", username):
        return "Username must be 3-20 characters: letters, numbers or underscore."
    if username == "guest" or username.startswith("sso_"):
        return "That username is reserved."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password != confirm:
        return "Passwords do not match."
    users = load_users()
    if username in users:
        return "That username is already taken."
    salt = secrets.token_hex(16)
    users[username] = {"salt": salt, "hash": hash_pw(password, salt), "created": time.time()}
    save_users(users)
    new_file = "chats_" + username + ".json"
    if len(users) == 1 and os.path.exists(CHATS_FILE) and not os.path.exists(new_file):
        shutil.copy(CHATS_FILE, new_file)  # first account adopts the earlier single-user history
    st.session_state["user"] = username
    return None


def check_login(username, password):
    username = username.strip().lower()
    u = load_users().get(username)
    if u:
        ok = hmac.compare_digest(hash_pw(password, u["salt"]), u["hash"])
    else:
        hash_pw(password, "00" * 16)  # similar timing for unknown users
        ok = False
    return username if ok else None


def sso_user():
    try:
        u = st.user
        if getattr(u, "is_logged_in", False):
            return u
    except Exception:
        pass
    return None


def sso_providers():
    try:
        cfg = st.secrets["auth"]
    except Exception:
        return []
    out = []
    for k in cfg:
        try:
            if hasattr(cfg[k], "keys"):
                out.append((k, PROVIDER_LABELS.get(k, "Continue with " + str(k).title())))
        except Exception:
            pass
    if not out and "client_id" in cfg:
        out.append((None, "Continue with single sign-on"))
    return out


def cb_logout():
    for k in ["user", "guest", "chats", "chat_id", "chat_picker", "pending",
              "fails", "locked_until", "display"]:
        st.session_state.pop(k, None)
    if sso_user() is not None:
        st.logout()


def login_page():
    st.markdown("""<style>
[data-testid="stMainBlockContainer"], .block-container { min-height: 100vh; display: flex;
    flex-direction: column; justify-content: center; padding-top: 1rem !important;
    padding-bottom: 1rem !important; }
</style>""", unsafe_allow_html=True)
    hero("AGENTIC RAG", "Sign in to continue. Your chats are saved to your account.", center=True)
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        locked = time.time() < st.session_state.get("locked_until", 0)
        if locked:
            st.error("Too many failed attempts. Please wait 30 seconds and try again.")
        tab_in, tab_up = st.tabs(["Log in", "Sign up"])
        with tab_in:
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                go = st.form_submit_button("Log in")
            if go and not locked:
                who = check_login(u, p)
                if who:
                    st.session_state["user"] = who
                    st.session_state["fails"] = 0
                    st.rerun()
                else:
                    fails = st.session_state.get("fails", 0) + 1
                    st.session_state["fails"] = fails
                    if fails >= 5:
                        st.session_state["locked_until"] = time.time() + 30
                        st.session_state["fails"] = 0
                    st.error("Incorrect username or password.")
        with tab_up:
            with st.form("signup_form"):
                nu = st.text_input("Choose a username")
                np1 = st.text_input("Password (at least 8 characters)", type="password")
                np2 = st.text_input("Confirm password", type="password")
                create = st.form_submit_button("Create account")
            if create:
                err = create_account(nu, np1, np2)
                if err:
                    st.error(err)
                else:
                    st.rerun()
        providers = sso_providers()
        st.divider()
        if providers:
            st.markdown("**Or continue with**")
            for prov, label in providers:
                st.button(label, key="sso_" + str(prov), on_click=st.login, args=[prov])
        else:
            st.caption("Social login (Google, Facebook, ...) is not set up yet.")
        st.divider()
        if st.button("Continue as guest (chats are not saved)"):
            st.session_state["user"] = "guest"
            st.session_state["guest"] = True
            st.rerun()


if not st.session_state.get("user"):
    su = sso_user()
    ident = str(getattr(su, "email", None) or getattr(su, "sub", None) or "") if su is not None else ""
    if ident:
        st.session_state["user"] = "sso_" + hashlib.sha256(ident.encode("utf-8")).hexdigest()[:16]
        st.session_state["display"] = str(getattr(su, "name", None) or getattr(su, "email", None)
                                          or "Signed-in user")
    else:
        login_page()
        st.stop()

if "chats" not in st.session_state:
    st.session_state["chats"] = load_chats()
if not st.session_state["chats"]:
    new_chat()
if st.session_state.get("chat_id") not in st.session_state["chats"]:
    st.session_state["chat_id"] = latest_chat_id()


# ---------------- sources ----------------
def page_no(p):
    return p + 1 if isinstance(p, int) else p


def source_kind(s):
    return s.get("type") or ("web" if str(s["source"]).startswith("http") else "paper")


def site_name(url):
    """Readable website name from a URL, e.g. https://en.wikipedia.org/... -> Wikipedia."""
    host = urlparse(str(url)).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "gov", "ac", "edu"):
        core = parts[-3]
    elif len(parts) >= 2:
        core = parts[-2]
    else:
        core = host
    return SITE_NAMES.get(core, core.replace("-", " ").title())


def docs_to_sources(docs):
    out = []
    for d in docs:
        src = str(d.metadata.get("source"))
        is_web = src.startswith("http")
        out.append({
            "type": "web" if is_web else "paper",
            "source": src if is_web else os.path.basename(src),
            "title": d.metadata.get("title") or "",
            "page": d.metadata.get("page"),
            "text": d.page_content,
        })
    return out


def show_sources(sources, route=""):
    st.markdown("**Sources used**")
    if not sources:
        if route == "direct":
            st.caption("None. This was a direct reply and needed no sources.")
        else:
            st.caption("None. This answer came from the model's own knowledge, not from any document.")
        return
    chips = []
    for s in sources:
        if source_kind(s) == "paper":
            chips.append(badge(f"{s['source']} p.{page_no(s['page'])}", "#2563EB"))
        else:
            chips.append(badge(site_name(s["source"]), "#0891B2"))
    st.markdown(" ".join(dict.fromkeys(chips)), unsafe_allow_html=True)
    for i, s in enumerate(sources, 1):
        if source_kind(s) == "web":
            title = (s.get("title") or s["source"]).replace("[", "(").replace("]", ")")
            st.markdown(f"{i}. **{site_name(s['source'])}** - [{title}]({s['source']})")
        else:
            st.markdown(f"{i}. **Paper:** {s['source']}, page {page_no(s['page'])}")
    with st.expander("View the text used"):
        for i, s in enumerate(sources, 1):
            label = site_name(s["source"]) if source_kind(s) == "web" else s["source"]
            st.markdown(f"**[{i}]** {label}")
            st.caption(s["text"][:500])


# ---------------- agent helpers ----------------
def run_agent(question, status=None):
    """Run the graph, streaming each step into the status box. Never raises."""
    final = {}
    t0 = time.time()
    try:
        for update in graph.stream({"question": question, "steps": []}, stream_mode="updates"):
            for _node, delta in update.items():
                if not delta:
                    continue
                final.update(delta)
                if status is not None and delta.get("steps"):
                    status.write("- " + delta["steps"][-1])
    except Exception as e:
        final = {
            "generation": "Sorry, something went wrong (" + type(e).__name__ + "). "
                          "If this was a rate limit, wait a minute and try again.",
            "steps": final.get("steps", []) + ["Error: " + type(e).__name__],
            "route": final.get("route", ""),
            "documents": [],
        }
    return final, time.time() - t0


def make_standalone(question, messages):
    """Turn a follow-up question into a standalone one using recent chat history."""
    prior = messages[-6:]
    if not prior:
        return question
    convo = "\n".join(f"{m['role'].upper()}: {m['content'][:300]}" for m in prior)
    prompt = (
        "Given the conversation and a follow-up question, rewrite the follow-up as a "
        "standalone question that can be understood without the conversation. "
        "If it is already standalone, return it unchanged. Return ONLY the question.\n\n"
        f"Conversation:\n{convo}\n\nFollow-up: {question}"
    )
    try:
        return to_text(llm.invoke(prompt)).strip() or question
    except Exception:
        return question


def suggest_followups(question, answer):
    prompt = (
        "Suggest 3 short follow-up questions a student might ask next about this topic. "
        "Return ONLY the 3 questions, one per line, no numbering.\n\n"
        f"Question: {question}\nAnswer: {answer[:600]}"
    )
    try:
        lines = [l.strip(" -*0123456789.").strip() for l in to_text(llm.invoke(prompt)).splitlines()]
        return [l for l in lines if l.endswith("?")][:3]
    except Exception:
        return []


def word_stream(text):
    for token in text.split(" "):
        yield token + " "
        time.sleep(0.015)


def save_feedback(entry):
    row = {"user": st.session_state.get("user", ""), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
           "rating": entry["rating"], "question": entry.get("question", ""),
           "answer": entry["content"], "route": entry["meta"].get("route", "")}
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def feedback_counts():
    up = down = 0
    if os.path.exists(FEEDBACK_FILE):
        for line in open(FEEDBACK_FILE, encoding="utf-8"):
            try:
                r = json.loads(line)["rating"]
                up += r == "up"
                down += r == "down"
            except Exception:
                pass
    return up, down


def render_feedback(idx, entry):
    if "rating" in entry:
        st.caption("You rated this answer: " + ("helpful" if entry["rating"] == "up" else "not helpful"))
        return
    if not hasattr(st, "feedback"):
        return  # needs a newer Streamlit: pip install --upgrade streamlit
    r = st.feedback("thumbs", key=f"fb_{st.session_state['chat_id']}_{idx}")
    if r is not None:
        entry["rating"] = "up" if r == 1 else "down"
        save_feedback(entry)
        save_chats()
        st.caption("Thanks for the feedback!")


def render_followups(meta, idx):
    for j, q in enumerate(meta.get("followups") or []):
        if st.button(q, key=f"fu_{st.session_state['chat_id']}_{idx}_{j}"):
            st.session_state["pending"] = q


def render_meta(meta):
    route = meta.get("route", "")
    html = badge(ROUTE_LABEL.get(route, route or "unknown"), ROUTE_COLOR.get(route, "#475569"))
    v = meta.get("verified")
    if route == "general":
        html += badge("Not from the papers", "#D97706")
    elif v is True:
        html += badge("Verified", "#16A34A")
    elif v is False:
        html += badge("Check failed", "#DC2626")
    html += badge(f"{meta.get('retries', 0)} retries", "#4F46E5")
    html += badge(f"{meta.get('secs', 0):.1f}s", "#0369A1")
    html += badge(f"{len(meta.get('sources', []))} sources", "#1D4ED8")
    st.markdown(html, unsafe_allow_html=True)
    if meta.get("searched") and meta.get("searched") != meta.get("asked"):
        st.caption(f"Understood your question as: {meta['searched']}")
    if SHOW_STEPS and meta.get("steps"):
        with st.expander("Agent steps"):
            for s in meta["steps"]:
                st.write("- " + s)
    show_sources(meta.get("sources", []), route=route)


# ---------------- sidebar ----------------
chats = st.session_state["chats"]

with st.sidebar:
    st.title("AGENTIC RAG")
    if st.session_state.get("guest"):
        st.caption("Guest session - chats are not saved")
    else:
        st.caption("Signed in as " + str(st.session_state.get("display") or st.session_state["user"]))
    st.button("Log out", on_click=cb_logout)
    st.divider()

    st.button("+ New chat", on_click=cb_new_chat)
    order = sorted(chats, key=lambda c: chats[c]["created"], reverse=True)
    st.session_state["chat_picker"] = st.session_state["chat_id"]
    st.selectbox("Chat history", order, format_func=lambda c: chats[c]["title"],
                 key="chat_picker", on_change=cb_pick)

    st.divider()
    st.subheader("Settings")
    K = st.slider("Chunks retrieved (k)", 1, 8, 4)
    MAX_RETRIES = st.slider("Max retries", 0, 4, 2)
    SHOW_STEPS = st.toggle("Show agent steps", value=True)
    USE_MEMORY = st.toggle("Remember conversation", value=True)
    FOLLOWUPS = st.toggle("Suggest follow-up questions", value=False)

    st.divider()
    chat_now = current_chat()
    if chat_now["messages"]:
        md = "\n\n".join(f"**{'You' if m['role'] == 'user' else 'Assistant'}:** {m['content']}"
                         for m in chat_now["messages"])
        st.download_button("Download this chat", data=md, file_name="chat.md", mime="text/markdown")
    st.button("Clear this chat", on_click=cb_clear)
    st.button("Delete this chat", on_click=cb_delete)
    up, down = feedback_counts()
    st.caption(f"Feedback saved: {up} up, {down} down")

    st.divider()
    st.caption("Sources: 5 ML papers in a local ChromaDB, plus the web. Model: Gemini.")

agent.retriever.search_kwargs["k"] = K
agent.MAX_RETRIES = MAX_RETRIES


# ---------------- chat ----------------
hero("AGENTIC RAG",
     "An agent that routes your question, searches the papers or the web, grades what it finds, "
     "and checks its own answers.")

chat = current_chat()
messages = chat["messages"]

welcome = st.empty()
if not messages:
    with welcome.container():
        st.markdown("#### Try asking")
        cols = st.columns(2)
        for j, ex in enumerate(EXAMPLES):
            if cols[j % 2].button(ex, key=f"ex_{j}"):
                st.session_state["pending"] = ex

for i, m in enumerate(messages):
    with st.chat_message(m["role"]):
        st.write(m["content"])
        if m["role"] == "assistant":
            render_meta(m["meta"])
            render_feedback(i, m)
            if i == len(messages) - 1:
                render_followups(m["meta"], i)

prompt = st.chat_input("Ask a question...")
if not prompt:
    prompt = st.session_state.pop("pending", None)

if prompt:
    welcome.empty()
    standalone = make_standalone(prompt, messages) if USE_MEMORY else prompt
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.status("Agent working...", expanded=SHOW_STEPS) as status:
            final, secs = run_agent(standalone, status)
            status.update(label="Done", state="complete")
        answer = final.get("generation", "No answer was produced.")
        st.write_stream(word_stream(answer))

        meta = {
            "route": final.get("route", ""),
            "verified": final.get("answer_ok"),
            "retries": final.get("retries", 0),
            "secs": secs,
            "steps": final.get("steps", []),
            "sources": docs_to_sources(final.get("documents") or []),
            "asked": prompt,
            "searched": standalone,
            "followups": [],
        }
        if FOLLOWUPS and not answer.startswith(("I couldn't", "Sorry")):
            meta["followups"] = suggest_followups(prompt, answer)
        render_meta(meta)

        entry = {"role": "assistant", "content": answer, "meta": meta, "question": prompt}
        idx = len(messages)
        messages.append(entry)
        if chat["title"] == "New chat":
            chat["title"] = prompt[:45]
        save_chats()
        render_feedback(idx, entry)
        render_followups(meta, idx)
