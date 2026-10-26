ANIM = r"""
@keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
@keyframes slideIn { from { opacity: 0; transform: translateX(-18px); } to { opacity: 1; transform: translateX(0); } }
@keyframes popIn { from { opacity: 0; transform: scale(0.85); } to { opacity: 1; transform: scale(1); } }
@keyframes shimmer { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
@keyframes floatA { 0%, 100% { transform: translate(0, 0) scale(1); } 50% { transform: translate(60px, 40px) scale(1.15); } }
@keyframes floatB { 0%, 100% { transform: translate(0, 0) scale(1); } 50% { transform: translate(-70px, -30px) scale(1.1); } }
@keyframes glowPulse { 0%, 100% { box-shadow: 0 8px 30px rgba(37,99,235,0.25); } 50% { box-shadow: 0 8px 42px rgba(34,211,238,0.38); } }
.stApp { isolation: isolate; }
.stApp::before, .stApp::after { content: ""; position: fixed; border-radius: 50%; filter: blur(90px);
    opacity: 0.35; pointer-events: none; z-index: -1; }
.stApp::before { width: 460px; height: 460px; top: -120px; left: -80px; background: #2563EB;
    animation: floatA 16s ease-in-out infinite; }
.stApp::after { width: 420px; height: 420px; bottom: -140px; right: -90px; background: #06B6D4;
    animation: floatB 19s ease-in-out infinite; }
.hero { animation: fadeUp 0.7s ease both, glowPulse 5s ease-in-out infinite; }
.hero-center { text-align: center; }
.hero h1, [data-testid="stSidebar"] h1 { background-size: 300% 100% !important;
    animation: shimmer 7s ease infinite; }
[data-testid="stChatMessage"] { animation: fadeUp 0.5s ease both; }
[data-testid="stExpander"] { animation: fadeUp 0.45s ease both; }
[data-testid="stForm"] { animation: fadeUp 0.7s ease 0.1s both; }
.badge { animation: popIn 0.35s ease both; }
[data-testid="stSidebar"] .stButton, [data-testid="stSidebar"] [data-testid="stSelectbox"],
[data-testid="stSidebar"] [data-testid="stSlider"], [data-testid="stSidebar"] [data-testid="stToggle"] {
    animation: slideIn 0.5s ease both; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
    transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease; }
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px); box-shadow: 0 6px 18px rgba(14,165,233,0.45); }
[data-testid="stChatInput"] { transition: box-shadow 0.25s ease; }
[data-testid="stChatInput"]:focus-within { box-shadow: 0 0 0 2px rgba(59,130,246,0.55), 0 0 22px rgba(34,211,238,0.25); }
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; } }
"""

OLD_HERO = r'''def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)'''
NEW_HERO = r'''def hero(title, subtitle, center=False):
    cls = "hero hero-center" if center else "hero"
    st.markdown(f'<div class="{cls}"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)'''

OLD_LOGIN = r'''def login_page():
    hero("AGENTIC RAG", "Sign in to continue. Your chats are saved to your account.")
    _, mid, _ = st.columns([1, 2, 1])'''
NEW_LOGIN = r'''def login_page():
    st.markdown("""<style>
[data-testid="stMainBlockContainer"], .block-container { min-height: 100vh; display: flex;
    flex-direction: column; justify-content: center; padding-top: 1rem !important;
    padding-bottom: 1rem !important; }
</style>""", unsafe_allow_html=True)
    hero("AGENTIC RAG", "Sign in to continue. Your chats are saved to your account.", center=True)
    _, mid, _ = st.columns([1, 1.6, 1])'''

EDITS = [
    ("animations", "</style>", ANIM + "</style>"),
    ("hero function", OLD_HERO, NEW_HERO),
    ("centered login page", OLD_LOGIN, NEW_LOGIN),
]

s = open("app.py", encoding="utf-8").read()
if "keyframes fadeUp" in s:
    print("app.py: animations already added")
else:
    for name, old, new in EDITS:
        if old in s:
            s = s.replace(old, new, 1)
            print("applied:", name)
        else:
            print("NOT FOUND:", name)
    open("app.py", "w", encoding="utf-8").write(s)
