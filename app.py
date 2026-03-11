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
    """Initialises API clients from Streamlit secrets."""
    try:
        vimeo_token = st.secrets["VIMEO_ACCESS_TOKEN"]
        anthropic_key = st.secrets["ANTHROPIC_API_KEY"]
    except KeyError as e:
        st.error(f"❌ Missing secret: {e}. Add it in your Streamlit secrets settings.")
        st.stop()

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
def generate_intro_script(anthropic_client, aggregated_text):
    """Sends truncated transcript text to Claude Haiku to generate the intro script."""
    # Token guard: cap input at 15,000 characters
    safe_text = aggregated_text[:15000]

    prompt = f"""You are an expert educational copywriter. Your job is to write a highly engaging introduction video script for a course module.

Based *only* on the provided transcripts, write a script for the Module Introduction video following these strict parameters:
* Length: Exactly 60 seconds.
* Goal: Generate curiosity and introduce the module to the students.

Guidelines:
* The Hook: Start with an interesting fact, insight, or question that will be answered.
* Value Proposition: Clearly state why this module matters to them.
* Real-World Application: Suggest a concrete, real-world scenario where a student might use these tools to solve a problem, even if a specific scenario is not explicitly mentioned in the text.
* Do NOT simply list the topics. Weave them naturally.
* Tone: Enthusiastic, professional, and encouraging.
* Formatting Restrictions: Do NOT include any section headers, bracketed text, timestamps (e.g., [HOOK]), speaker labels, or bullet points. The final output must be one single, seamless paragraph of natural spoken dialogue.

Raw Transcripts:
{safe_text}"""

    message = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text

# ==========================================
# MAIN UI
# ==========================================
folder_id = st.text_input(
    "Vimeo Folder ID",
    placeholder="e.g.  27095270",
    help="The numeric ID found in your Vimeo folder URL."
)

generate_btn = st.button("✦ Generate Intro Script")

if generate_btn:
    if not folder_id.strip():
        st.warning("Please enter a Vimeo Folder ID before generating.")
    else:
        vimeo_client, anthropic_client = get_clients()

        with st.spinner("Scanning Vimeo folder…"):
            videos_data, folder_videos = get_video_ids_from_folder(vimeo_client, folder_id.strip())

        if not folder_videos:
            st.error("No videos found in that folder. Double-check the Folder ID.")
        else:
            st.info(f"📂 Found **{len(videos_data)}** total videos → processing **{len(folder_videos)}** latest versions.")

            all_transcripts = ""
            progress = st.progress(0, text="Downloading transcripts…")

            for i, vid in enumerate(folder_videos):
                raw_vtt = get_vimeo_transcript(vimeo_client, vid)
                if raw_vtt:
                    clean_text = clean_vtt(raw_vtt)
                    all_transcripts += clean_text + "\n\n"
                progress.progress((i + 1) / len(folder_videos), text=f"Transcript {i+1} of {len(folder_videos)}…")

            progress.empty()

            if not all_transcripts.strip():
                st.error("Transcripts were empty or missing for all videos.")
            else:
                with st.spinner("Crafting your intro script with Claude Haiku…"):
                    script = generate_intro_script(anthropic_client, all_transcripts)

                st.success("✅ Script generated!")
                st.markdown("#### Your 30-Second Intro Script")
                st.markdown(f'<div class="script-output">{script}</div>', unsafe_allow_html=True)

                st.download_button(
                    label="⬇ Download Script (.txt)",
                    data=script,
                    file_name=f"intro_script_{folder_id.strip()}.txt",
                    mime="text/plain",
                )
