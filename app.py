import re
import requests
import vimeo
import anthropic
import streamlit as st

# ==========================================
# PAGE CONFIG & CUSTOM STYLING
# ==========================================
st.set_page_config(
    page_title="AI Intro Script Generator",
    page_icon="🎬",
    layout="centered",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}

/* Dark background */
.stApp {
    background-color: #0d0f14;
    color: #e8e4dc;
}

/* Header */
h1 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
    font-size: 2.4rem !important;
    letter-spacing: -0.03em !important;
    color: #f0ebe0 !important;
    line-height: 1.1 !important;
}

h3 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important;
    color: #b8b0a0 !important;
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* Input label */
label {
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #a09080 !important;
}

/* Text input */
.stTextInput > div > div > input {
    background-color: #1a1d24 !important;
    border: 1px solid #2e3240 !important;
    border-radius: 6px !important;
    color: #e8e4dc !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 1rem !important;
    padding: 0.65rem 0.9rem !important;
    transition: border-color 0.2s;
}
.stTextInput > div > div > input:focus {
    border-color: #c8a96e !important;
    box-shadow: 0 0 0 2px rgba(200, 169, 110, 0.12) !important;
}

/* Button */
.stButton > button {
    background-color: #c8a96e !important;
    color: #0d0f14 !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.8rem !important;
    transition: background-color 0.2s, transform 0.1s;
    width: 100%;
}
.stButton > button:hover {
    background-color: #dfc080 !important;
    transform: translateY(-1px);
}
.stButton > button:active {
    transform: translateY(0px);
}

/* Output box */
.script-output {
    background-color: #13161e;
    border: 1px solid #2e3240;
    border-left: 3px solid #c8a96e;
    border-radius: 8px;
    padding: 1.6rem 1.8rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.92rem;
    line-height: 1.75;
    color: #e8e4dc;
    white-space: pre-wrap;
    margin-top: 1.2rem;
}

/* Status / info boxes */
.stAlert {
    background-color: #1a1d24 !important;
    border: 1px solid #2e3240 !important;
    color: #b8b0a0 !important;
    font-family: 'Syne', sans-serif !important;
}

/* Divider */
hr {
    border-color: #2e3240 !important;
    margin: 1.8rem 0 !important;
}

/* Spinner text */
.stSpinner > div > div {
    color: #c8a96e !important;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# HEADER
# ==========================================
st.markdown("# 🎬 Intro Script Generator")
st.markdown("### Course Module Automation — Powered by Claude Haiku")
st.markdown("---")

# ==========================================
# SECRETS / API CLIENTS
# ==========================================
def get_clients():
    """Initialises API clients from Streamlit secrets with clear diagnostics."""

    # ── Check both secrets exist ──────────────────────────────────────────────
    missing = [k for k in ("VIMEO_ACCESS_TOKEN", "ANTHROPIC_API_KEY") if k not in st.secrets]
    if missing:
        st.error(
            f"❌ Missing secret(s): **{', '.join(missing)}**\n\n"
            "Go to your app on Streamlit Cloud → ⋮ menu → **Settings → Secrets** "
            "and make sure your `secrets.toml` looks *exactly* like this "
            "(no extra quotes, no extra spaces):\n\n"
            "```toml\n"
            'VIMEO_ACCESS_TOKEN  = "paste_your_vimeo_token_here"\n'
            'ANTHROPIC_API_KEY   = "sk-ant-api03-..."\n'
            "```"
        )
        st.stop()

    # ── Strip accidental whitespace from copied keys ──────────────────────────
    vimeo_token    = st.secrets["VIMEO_ACCESS_TOKEN"].strip()
    anthropic_key  = st.secrets["ANTHROPIC_API_KEY"].strip()

    # ── Basic format sanity checks ────────────────────────────────────────────
    if not anthropic_key.startswith("sk-ant-"):
        st.error(
            "❌ **ANTHROPIC_API_KEY** doesn't look right — it should start with `sk-ant-`.\n\n"
            "Double-check the key at [console.anthropic.com](https://console.anthropic.com) "
            "→ **API Keys**. Make sure you copied the full key without surrounding quotes."
        )
        st.stop()

    if len(vimeo_token) < 20:
        st.error(
            "❌ **VIMEO_ACCESS_TOKEN** looks too short. "
            "Regenerate it at [developer.vimeo.com/apps](https://developer.vimeo.com/apps)."
        )
        st.stop()

    # ── Build clients ─────────────────────────────────────────────────────────
    vc = vimeo.VimeoClient(token=vimeo_token)
    ac = anthropic.Anthropic(api_key=anthropic_key)
    return vc, ac

# ==========================================
# VIMEO HELPERS
# ==========================================
def get_video_ids_from_folder(vimeo_client, folder_id):
    """Fetches videos and returns only the latest version of each AIP_ lecture."""
    response = vimeo_client.get(f'/me/projects/{folder_id}/videos')

    if response.status_code != 200:
        st.error(f"❌ Could not access folder `{folder_id}`. Check your Folder ID and Vimeo token permissions.")
        return []

    videos_data = response.json().get('data', [])
    latest_lectures = {}
    other_videos = []

    for video in videos_data:
        uri = video.get('uri', '')
        vid_id = uri.split('/')[-1]
        title = video.get('name', '')

        match = re.search(r'AIP_(.+)_(?:v|V)?(\d+)', title)
        if match:
            lecture_id = match.group(1)
            version_num = int(match.group(2))
            if lecture_id not in latest_lectures or version_num > latest_lectures[lecture_id]['version']:
                latest_lectures[lecture_id] = {'version': version_num, 'id': vid_id}
        else:
            other_videos.append(vid_id)

    final_video_ids = [info['id'] for info in latest_lectures.values()] + other_videos
    return videos_data, final_video_ids


def get_vimeo_transcript(vimeo_client, video_id):
    """Downloads the VTT transcript for a given Vimeo video."""
    response = vimeo_client.get(f'/videos/{video_id}/texttracks')
    if response.status_code != 200:
        return ""
    tracks = response.json().get('data', [])
    if not tracks:
        return ""
    vtt_link = tracks[0].get('link')
    vtt_response = requests.get(vtt_link)
    return vtt_response.text


def clean_vtt(vtt_text):
    """Strips out VTT timestamps and HTML formatting."""
    text = re.sub(r'WEBVTT.*\n', '', vtt_text)
    text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}.*\n', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return " ".join(text.split())

# ==========================================
# CLAUDE HAIKU — SCRIPT GENERATION
# ==========================================

SYSTEM_PROMPT = """You are an expert educational copywriter who writes highly engaging introduction video scripts for online course modules.
When given transcripts, you produce a script following these strict parameters:

* Length: STRICT MAXIMUM OF 75 WORDS. If it takes longer than 30 seconds to read out loud, it is too long.
* Goal: Generate curiosity and introduce the module to the students.
* The Hook: Start with an interesting fact, insight, or question that will be answered.
* Value Proposition: Clearly state why this module matters to them.
* Real-World Application: Suggest a concrete, real-world scenario where a student might use these tools to solve a problem, even if a specific scenario is not explicitly mentioned in the text.
* Do NOT simply list the topics. Weave them naturally.
* Tone: Enthusiastic, professional, and encouraging.
* Formatting Restrictions: Do NOT include any section headers, bracketed text, timestamps (e.g., [HOOK]), speaker labels, or bullet points. The final output must be one single, seamless paragraph of natural spoken dialogue.

When given refinement feedback, revise the previous script accordingly while keeping the exact same length, quality, and strict formatting restrictions."""

def build_initial_prompt(aggregated_text):
    """Builds the first user message with the transcript context."""
    safe_text = aggregated_text[:15000]  # Token guard
    return (
        "Please write the 30-second module introduction script based on these lecture transcripts:\n\n"
        f"{safe_text}"
    )

def call_claude(anthropic_client, messages):
    """Sends the full conversation history to Claude Haiku and returns the reply text."""
    try:
        response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text
    except anthropic.AuthenticationError:
        st.error(
            "❌ **Anthropic Authentication Error** — the API key was rejected.\n\n"
            "**Most common causes:**\n"
            "1. Extra quotes in Streamlit Secrets, e.g. `'sk-ant-...'` — remove them.\n"
            "2. Key copied with a leading/trailing space.\n"
            "3. Key has been revoked — generate a new one at "
            "[console.anthropic.com](https://console.anthropic.com) → API Keys.\n\n"
            "Correct format:\n```toml\nANTHROPIC_API_KEY = \"sk-ant-api03-...\"\n```"
        )
        st.stop()
    except anthropic.APIStatusError as e:
        st.error(f"❌ Anthropic API error ({e.status_code}): {e.message}")
        st.stop()

# ==========================================
# SESSION STATE INITIALISATION
# ==========================================
for key, default in {
    "transcripts": None,       # Cached transcript text — avoids re-fetching Vimeo
    "folder_id_loaded": None,  # Which folder the transcripts belong to
    "messages": [],            # Full Claude conversation history
    "script_versions": [],     # List of {"label": str, "script": str}
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==========================================
# EXTRA STYLES FOR REFINEMENT UI
# ==========================================
st.markdown("""
<style>
/* Textarea */
.stTextArea > div > div > textarea {
    background-color: #1a1d24 !important;
    border: 1px solid #2e3240 !important;
    border-radius: 6px !important;
    color: #e8e4dc !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.88rem !important;
    line-height: 1.6 !important;
    transition: border-color 0.2s;
}
.stTextArea > div > div > textarea:focus {
    border-color: #c8a96e !important;
    box-shadow: 0 0 0 2px rgba(200, 169, 110, 0.12) !important;
}
/* Version history pill */
.version-label {
    display: inline-block;
    background: #1e2230;
    border: 1px solid #2e3240;
    border-radius: 4px;
    padding: 0.15rem 0.55rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    color: #7a8090;
    margin-bottom: 0.5rem;
}
/* Secondary (ghost) button — Reset */
div[data-testid="column"]:last-child .stButton > button {
    background-color: transparent !important;
    color: #7a8090 !important;
    border: 1px solid #2e3240 !important;
}
div[data-testid="column"]:last-child .stButton > button:hover {
    border-color: #c8a96e !important;
    color: #c8a96e !important;
    transform: none;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# MAIN UI
# ==========================================
folder_id = st.text_input(
    "Vimeo Folder ID",
    placeholder="e.g.  27095270",
    help="The numeric ID found in your Vimeo folder URL.",
    value=st.session_state.folder_id_loaded or "",
)

col_gen, col_reset = st.columns([3, 1])
with col_gen:
    generate_btn = st.button("✦ Generate Intro Script", use_container_width=True)
with col_reset:
    reset_btn = st.button("↺ Reset", use_container_width=True)

# ── Reset clears all session state ────────────────────────────────────────────
if reset_btn:
    for key in ("transcripts", "folder_id_loaded", "messages", "script_versions"):
        st.session_state[key] = [] if key in ("messages", "script_versions") else None
    st.rerun()

# ── Initial generation ────────────────────────────────────────────────────────
if generate_btn:
    if not folder_id.strip():
        st.warning("Please enter a Vimeo Folder ID before generating.")
    else:
        vimeo_client, anthropic_client = get_clients()

        # Only re-fetch Vimeo if the folder has changed
        if st.session_state.folder_id_loaded != folder_id.strip() or not st.session_state.transcripts:
            with st.spinner("Scanning Vimeo folder…"):
                videos_data, folder_videos = get_video_ids_from_folder(vimeo_client, folder_id.strip())

            if not folder_videos:
                st.error("No videos found. Double-check the Folder ID.")
                st.stop()

            st.info(f"📂 Found **{len(videos_data)}** total videos → processing **{len(folder_videos)}** latest versions.")

            all_transcripts = ""
            progress = st.progress(0, text="Downloading transcripts…")
            for i, vid in enumerate(folder_videos):
                raw_vtt = get_vimeo_transcript(vimeo_client, vid)
                if raw_vtt:
                    all_transcripts += clean_vtt(raw_vtt) + "\n\n"
                progress.progress((i + 1) / len(folder_videos), text=f"Transcript {i+1} of {len(folder_videos)}…")
            progress.empty()

            if not all_transcripts.strip():
                st.error("Transcripts were empty or missing for all videos.")
                st.stop()

            # Cache transcripts and reset conversation
            st.session_state.transcripts = all_transcripts
            st.session_state.folder_id_loaded = folder_id.strip()
            st.session_state.messages = []
            st.session_state.script_versions = []

        # Build first user message and call Claude
        first_message = build_initial_prompt(st.session_state.transcripts)
        st.session_state.messages = [{"role": "user", "content": first_message}]

        with st.spinner("Crafting your intro script with Claude Haiku…"):
            script = call_claude(anthropic_client, st.session_state.messages)

        # Store Claude's reply in conversation history
        st.session_state.messages.append({"role": "assistant", "content": script})
        st.session_state.script_versions = [{"label": "v1 — Initial", "script": script}]
        st.rerun()

# ── Display results + refinement UI ──────────────────────────────────────────
if st.session_state.script_versions:
    latest = st.session_state.script_versions[-1]

    st.success("✅ Script ready!")
    st.markdown("#### Current Script")
    st.markdown(f'<div class="script-output">{latest["script"]}</div>', unsafe_allow_html=True)

    st.download_button(
        label="⬇ Download Script (.txt)",
        data=latest["script"],
        file_name=f"intro_script_{st.session_state.folder_id_loaded}.txt",
        mime="text/plain",
    )

    # ── Refinement section ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✏️ Refine the Script")
    st.markdown(
        "<p style='color:#7a8090;font-size:0.82rem;font-family:Syne,sans-serif;margin-top:-0.6rem'>"
        "Describe what to change, add, or remove — Claude has full context of the previous script."
        "</p>",
        unsafe_allow_html=True,
    )

    refinement_input = st.text_area(
        "Your feedback or instructions",
        placeholder=(
            "e.g. 'Make the opening hook more surprising'\n"
            "     'Mention that students will build a live dashboard'\n"
            "     'Shorten the value proposition and add more energy to the close'"
        ),
        height=120,
        label_visibility="collapsed",
    )

    refine_btn = st.button("✦ Regenerate with Feedback", use_container_width=True)

    if refine_btn:
        if not refinement_input.strip():
            st.warning("Please describe what you'd like to change before regenerating.")
        else:
            _, anthropic_client = get_clients()

            # Append user feedback to the live conversation
            st.session_state.messages.append({"role": "user", "content": refinement_input.strip()})

            with st.spinner("Revising your script…"):
                revised_script = call_claude(anthropic_client, st.session_state.messages)

            st.session_state.messages.append({"role": "assistant", "content": revised_script})
            version_num = len(st.session_state.script_versions) + 1
            st.session_state.script_versions.append({
                "label": f"v{version_num} — {refinement_input.strip()[:40]}{'…' if len(refinement_input) > 40 else ''}",
                "script": revised_script,
            })
            st.rerun()

    # ── Version history ───────────────────────────────────────────────────────
    if len(st.session_state.script_versions) > 1:
        st.markdown("---")
        st.markdown("#### 🕓 Version History")
        for i, version in enumerate(reversed(st.session_state.script_versions)):
            idx = len(st.session_state.script_versions) - i
            is_current = (idx == len(st.session_state.script_versions))
            label_suffix = " ← current" if is_current else ""
            with st.expander(f"{version['label']}{label_suffix}"):
                st.markdown(f'<div class="script-output">{version["script"]}</div>', unsafe_allow_html=True)
                st.download_button(
                    label=f"⬇ Download v{idx}",
                    data=version["script"],
                    file_name=f"intro_script_{st.session_state.folder_id_loaded}_v{idx}.txt",
                    mime="text/plain",
                    key=f"dl_v{idx}",
                )
