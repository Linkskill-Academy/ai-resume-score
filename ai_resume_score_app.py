# ai_resume_score_app.py
# LinkSkill Academy — AI Resume Score QR Booth (Streamlit)
# Run locally:  streamlit run ai_resume_score_app.py

import io
import re
import time
import base64
import pandas as pd
import streamlit as st
from datetime import datetime

# Optional deps (handled gracefully):
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx2txt
except Exception:
    docx2txt = None

try:
    import qrcode
    from PIL import Image
except Exception:
    qrcode = None
    Image = None

st.set_page_config(page_title="AI Resume Score — LinkSkill Academy", page_icon="🧠", layout="wide")

# -----------------------------
# CONFIG
# -----------------------------
BRAND_PRIMARY = "#0b235a"   # Navy
BRAND_ACCENT  = "#ff7a00"   # Orange
LEADS_CSV     = "leads.csv"

ROLE_KEYWORDS = {
    "General / Fresher": [
        "project", "internship", "team", "lead", "communication", "problem solving", "python", "excel",
        "sql", "presentation", "achievement", "award", "certification"
    ],
    "Data Analyst": [
        "excel", "sql", "python", "pandas", "power bi", "tableau", "dax", "visualization", "dashboard",
        "etl", "statistics", "a/b testing", "business intelligence", "insights", "kpi", "data cleaning"
    ],
    "Business Analyst": [
        "requirements", "user stories", "process mapping", "stakeholder", "jira", "confluence", "bpmn",
        "use case", "gap analysis", "brd", "frd", "acceptance criteria", "sql", "reporting", "kpi"
    ],
    "Digital Marketing": [
        "seo", "sem", "google ads", "meta ads", "content", "copywriting", "email marketing", "crm",
        "analytics", "utm", "landing page", "roi", "cpc", "ctr", "campaign", "canva"
    ],
    "Project Management": [
        "pmp", "agile", "scrum", "kanban", "jira", "risk", "stakeholder", "timeline", "budget",
        "milestone", "scope", "resources", "status report", "dependencies", "deliverables"
    ],
    "UI/UX Design": [
        "figma", "wireframe", "prototype", "user research", "usability", "interaction design", "ui kit",
        "persona", "journey map", "design system", "accessibility", "heuristics", "visual design"
    ],
    "Software Developer": [
        "python", "java", "javascript", "react", "node", "api", "microservices", "docker", "git",
        "testing", "ci/cd", "design patterns", "oop", "algorithm", "data structures"
    ]
}

ACTION_VERBS = [
    "led","built","created","developed","designed","launched","optimized","reduced","increased","improved",
    "automated","migrated","enhanced","analysed","analyzed","implemented","managed","delivered","deployed",
    "streamlined","orchestrated","scaled","designed","architected","spearheaded"
]

CERT_WORDS = [
    "certified","certificate","coursera","udemy","pl-300","pmp","six sigma","itil","aws","azure","gcp",
    "google analytics","meta","hubspot"
]

EDU_WORDS = [
    "b.e","btech","b.tech","bsc","b.sc","msc","m.sc","mca","bca","mba","bachelor","master","degree","college","university"
]

SECTION_HINTS = {
    "Summary/Objectives": ["summary", "objective", "profile"],
    "Experience": ["experience", "work experience", "professional experience", "employment"],
    "Projects": ["projects", "project experience"],
    "Education": ["education", "academics"],
    "Skills": ["skills", "technical skills"],
    "Certifications": ["certifications", "certificates", "licenses"],
    "Achievements": ["awards", "achievements", "accomplishments"]
}

# -----------------------------
# HELPERS
# -----------------------------
def extract_text_from_file(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith(".pdf") and PyPDF2 is not None:
        text = ""
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            for page in reader.pages:
                try:
                    text += page.extract_text() or ""
                except Exception:
                    continue
        except Exception:
            pass
        if text.strip():
            return text
    if name.endswith(".docx") and docx2txt is not None:
        try:
            # docx2txt requires a path; workaround by writing temp
            import tempfile, os
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data)
                tmp.flush()
                path = tmp.name
            text = docx2txt.process(path) or ""
            try:
                os.remove(path)
            except Exception:
                pass
            if text.strip():
                return text
        except Exception:
            pass
    # fallback to plain text
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def contains_any(text, words):
    tl = text.lower()
    return [w for w in words if w in tl]

def count_regex(text, pattern, flags=re.I):
    return len(re.findall(pattern, text, flags))

def pct(n, d): 
    return 0 if d == 0 else round((n/d)*100, 1)

def estimate_read_time_words(text):
    words = len(text.split())
    return words, max(1, int(words/200))

# -----------------------------
# SCORING
# -----------------------------
def score_resume(text, target_role="General / Fresher", extra_keywords=None):
    """Return total_score, breakdown(dict), suggestions(list)"""
    tl = text.lower()
    word_count = len(tl.split())
    suggestions = []

    # 1) Structure (20)
    structure_points = 0
    structure_hits = {}
    for sec, aliases in SECTION_HINTS.items():
        hit = any(a in tl for a in aliases)
        structure_hits[sec] = hit
        if hit:
            structure_points += 20/len(SECTION_HINTS)
    structure_points = round(structure_points, 1)
    for sec, hit in structure_hits.items():
        if not hit:
            suggestions.append(f"Add a clear “{sec}” section.")

    # 2) Keywords match (30)
    role_words = ROLE_KEYWORDS.get(target_role, ROLE_KEYWORDS["General / Fresher"]).copy()
    if extra_keywords:
        role_words += [k.strip().lower() for k in extra_keywords.split(",") if k.strip()]
    found_role = contains_any(tl, role_words)
    kw_points = min(len(found_role) * (30/12), 30)  # cap
    if len(found_role) < 8:
        suggestions.append(f"Include more role keywords (target: {target_role}). Missing examples: " +
                           ", ".join(sorted(set(role_words) - set(found_role))[:8]))

    # 3) Impact & Achievements (20)
    nums = count_regex(tl, r"\b\d+[%k]?\b")  # numbers, percentages, 'k'
    action_uses = len(contains_any(tl, ACTION_VERBS))
    impact_points = min(10 + min(nums, 5)*2 + min(action_uses, 5)*1.5, 20)
    if nums < 3:
        suggestions.append("Quantify achievements (%, ₹, numbers) to show impact.")
    if action_uses < 3:
        suggestions.append("Start bullet points with strong action verbs (Led, Built, Improved...).")

    # 4) Education/Certifications (10)
    edu_hits = len(contains_any(tl, EDU_WORDS))
    cert_hits = len(contains_any(tl, CERT_WORDS))
    edu_points = min(edu_hits*2 + min(cert_hits, 3)*2, 10)
    if edu_hits == 0:
        suggestions.append("Add Education details (degree, college, year).")
    if cert_hits == 0:
        suggestions.append("List relevant certifications (PMP, PL-300, Google, Meta, etc.).")

    # 5) ATS Compliance (10)
    email_ok = bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", tl))
    phone_ok = bool(re.search(r"\b(\+?\d{1,3}[-\s]?)?\d{10}\b", tl))
    bullets = count_regex(text, r"(\n[-•·])|•")
    special_ratio = sum(not (ch.isalnum() or ch.isspace() or ch in ".,;:-()/&+%") for ch in text) / max(len(text),1)
    ats_points = 0
    if email_ok: ats_points += 3
    if phone_ok: ats_points += 3
    if bullets >= 5: ats_points += 2
    if special_ratio < 0.05: ats_points += 2
    if not email_ok: suggestions.append("Add a professional email address in header.")
    if not phone_ok: suggestions.append("Add a valid phone number with country code.")

    # 6) Formatting / Length (10)
    if 350 <= word_count <= 900:
        fmt_points = 10
    else:
        fmt_points = max(0, 10 - abs(word_count-600)/100)  # penalize outliers
        suggestions.append("Keep resume concise (1–2 pages; ~600–800 words recommended).")

    total = round(structure_points + kw_points + impact_points + edu_points + ats_points + fmt_points, 1)
    breakdown = {
        "Structure": structure_points,
        "Keywords": round(kw_points,1),
        "Impact": round(impact_points,1),
        "Education/Certs": round(edu_points,1),
        "ATS": round(ats_points,1),
        "Formatting": round(fmt_points,1),
        "Word Count": word_count
    }
    # Deduplicate and keep top 8 suggestions
    cleaned = []
    for s in suggestions:
        if s not in cleaned:
            cleaned.append(s)
    return total, breakdown, cleaned[:8]

def init_leads():
    if not os.path.exists(LEADS_CSV):
        pd.DataFrame(columns=[
            "timestamp","name","email","phone","target_role","extra_keywords",
            "score","breakdown","word_count"
        ]).to_csv(LEADS_CSV, index=False)

def save_lead(row: dict):
    init_leads()
    df = pd.read_csv(LEADS_CSV)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(LEADS_CSV, index=False)

def download_bytes(b, filename, label):
    st.download_button(label, b, file_name=filename)

def make_qr_png_bytes(url: str):
    if not qrcode or not Image:
        st.warning("Install 'qrcode' and 'Pillow' to generate QR codes (see requirements.txt).")
        return None
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# -----------------------------
# UI
# -----------------------------
st.markdown(f"""
<div style='padding:10px 16px;border-radius:12px;background:{BRAND_PRIMARY};color:white'>
  <h2 style='margin:0'>🧠 AI Resume Score — LinkSkill Academy</h2>
  <p style='margin:6px 0 0 0'>Scan. Upload. Get a score & actionable feedback. (Stall Exclusive)</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Admin / Booth Controls")
    st.info("Tip: Enter your public app URL to generate a printable QR code for the booth.")

    qr_url = st.text_input("Public App URL (for QR)", placeholder="https://your-app-url")
    if st.button("Generate QR Code"):
        if qr_url.strip():
            qr_png = make_qr_png_bytes(qr_url.strip())
            if qr_png:
                st.image(qr_png, caption="Scan to open this app")
                st.download_button("Download QR PNG", qr_png, file_name="ai_resume_qr.png")
        else:
            st.warning("Enter a valid URL first.")

    st.markdown("---")
    st.subheader("Leads Export")
    init_leads()
    df_leads = pd.read_csv(LEADS_CSV)
    st.write(f"Total leads captured: **{len(df_leads)}**")
    st.dataframe(df_leads.tail(10))
    csv_bytes = df_leads.to_csv(index=False).encode("utf-8")
    st.download_button("Download all leads (CSV)", csv_bytes, file_name="leads.csv")

st.markdown("### 👇 Get Your Resume Score")
with st.form("resume_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        name  = st.text_input("Full Name", "")
        email = st.text_input("Email", "")
        phone = st.text_input("Phone", "")
    with col2:
        target_role = st.selectbox("Target Role", list(ROLE_KEYWORDS.keys()), index=0)
        extra_kw = st.text_input("Extra Keywords (comma-separated, optional)", placeholder="power bi, pl-300, snowflake")
    uploaded = st.file_uploader("Upload Resume (PDF/DOCX/TXT)", type=["pdf","docx","txt"])
    agree = st.checkbox("I agree to be contacted by LinkSkill Academy about training & placement.")
    submitted = st.form_submit_button("🔍 Score My Resume", use_container_width=True)

if submitted:
    if not (name and email and phone and uploaded and agree):
        st.error("Please fill all fields, upload a resume, and accept the consent checkbox.")
    else:
        with st.spinner("Analyzing your resume..."):
            raw_text = extract_text_from_file(uploaded)
            if not raw_text.strip():
                st.error("Could not read your file. Please upload a PDF/DOCX/TXT resume.")
            else:
                total, breakdown, suggestions = score_resume(raw_text, target_role, extra_kw)
                # Save lead
                save_lead({
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "name": name, "email": email, "phone": phone,
                    "target_role": target_role, "extra_keywords": extra_kw,
                    "score": total, "breakdown": str(breakdown), "word_count": breakdown.get("Word Count", 0)
                })

                st.success(f"🎉 Your Resume Score: **{total}/100**")
                st.caption("This score is heuristic, for quick guidance at the booth. Book a full review for detailed, role-specific feedback.")

                met1, met2, met3 = st.columns(3)
                met1.metric("Structure", f"{breakdown['Structure']}/20")
                met2.metric("Keywords", f"{breakdown['Keywords']}/30")
                met3.metric("Impact", f"{breakdown['Impact']}/20")
                met4, met5, met6 = st.columns(3)
                met4.metric("Education/Certs", f"{breakdown['Education/Certs']}/10")
                met5.metric("ATS", f"{breakdown['ATS']}/10")
                met6.metric("Formatting", f"{breakdown['Formatting']}/10")

                st.markdown("#### 📌 Top Suggestions")
                for s in suggestions:
                    st.write(f"- {s}")

                st.markdown("---")
                st.info("Want a professional Resume Makeover & Mock Interview? Visit our stall for the **Stall-Only Offer ₹999**.")

st.markdown("---")
st.markdown(f"""
<div style="padding:8px 12px;border:1px dashed {BRAND_ACCENT};border-radius:10px">
  <b>Privacy:</b> Your details are stored only for the event follow-up by LinkSkill Academy.
</div>
""", unsafe_allow_html=True)