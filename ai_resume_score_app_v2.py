
# ai_resume_score_app_v2.py
# LinkSkill Academy — AI Resume Score (Research-backed) — Streamlit

import io, re, os, base64
from datetime import datetime
import pandas as pd
import streamlit as st

# Optional libs
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx2txt
except Exception:
    docx2txt = None

# Similarity
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None

st.set_page_config(page_title="AI Resume Score — Research-backed", page_icon="🧠", layout="wide")

# ---------------- CONFIG ----------------
BRAND_PRIMARY = "#0b235a"
BRAND_ACCENT  = "#ff7a00"
LEADS_CSV     = "leads.csv"

# Standard sections derived from widely-cited resume guidance
STANDARD_SECTIONS = {
    "Header": ["contact", "email", "phone"],
    "Summary": ["summary", "objective", "profile"],
    "Experience": ["experience", "work experience", "professional experience", "employment"],
    "Education": ["education", "academics", "university", "college"],
    "Skills": ["skills", "technical skills"],
    "Certifications": ["certifications", "licenses", "certificates"]
}

# Role keywords (seeded from O*NET and market norms; extend as needed)
ROLE_KEYWORDS = {
    "Data Analyst": ["excel","sql","python","pandas","power bi","tableau","dax","visualization","dashboard","etl","statistics","a/b testing","business intelligence","insights","kpi","data cleaning","data model","storytelling"],
    "Business Analyst": ["requirements","user stories","process mapping","stakeholder","jira","confluence","bpmn","use case","gap analysis","brd","frd","acceptance criteria","sql","reporting","kpi","as-is","to-be","roadmap"],
    "Digital Marketing": ["seo","sem","google ads","meta ads","content","copywriting","email marketing","crm","analytics","utm","landing page","roi","cpc","ctr","campaign","canva","keyword research","remarketing"],
    "Project Management": ["pmp","agile","scrum","kanban","jira","risk","stakeholder","timeline","budget","milestone","scope","resources","status report","dependencies","deliverables","burndown","retrospective"],
    "UI/UX Design": ["figma","wireframe","prototype","user research","usability","interaction design","ui kit","persona","journey map","design system","accessibility","heuristics","visual design","hifi","lofi"],
    "General / Fresher": ["project","internship","team","lead","communication","problem solving","python","excel","sql","presentation","achievement","award","certification"]
}

ACTION_VERBS = [
    "led","built","created","developed","designed","launched","optimized","reduced","increased","improved",
    "automated","migrated","enhanced","analyzed","implemented","managed","delivered","deployed",
    "streamlined","orchestrated","scaled","architected","spearheaded","boosted","transformed"
]

CERT_WORDS = ["certified","certificate","pl-300","pmp","six sigma","itil","aws","azure","gcp","google analytics","meta","hubspot","scrum"]
EDU_WORDS  = ["b.e","btech","b.tech","bsc","b.sc","msc","m.sc","mca","bca","mba","bachelor","master","degree","college","university"]

# ---------------- HELPERS ----------------
def extract_text(file) -> str:
    name = file.name.lower()
    data = file.read()
    # pdf
    if name.endswith(".pdf") and PyPDF2 is not None:
        text = ""
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            for p in reader.pages:
                try: text += p.extract_text() or ""
                except Exception: continue
        except Exception: pass
        if text.strip(): return text
    # docx
    if name.endswith(".docx") and docx2txt is not None:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data); tmp.flush(); path = tmp.name
            text = docx2txt.process(path) or ""
            try: os.remove(path)
            except Exception: pass
            if text.strip(): return text
        except Exception: pass
    # txt fallback
    try: return data.decode("utf-8", errors="ignore")
    except Exception: return ""

def has_any(text, words):
    tl = text.lower()
    return [w for w in words if w in tl]

def count_regex(text, pattern, flags=re.I):
    return len(re.findall(pattern, text, flags))

def tfidf_similarity(a, b):
    if not TfidfVectorizer or not a.strip() or not b.strip(): return 0.0
    vec = TfidfVectorizer(stop_words="english")
    m = vec.fit_transform([a, b])
    sim = cosine_similarity(m[0:1], m[1:2])[0][0]
    return float(sim)

# ---------------- SCORING ----------------
def score_resume(text, role="General / Fresher", jd_text=""):
    tl = text.lower()
    word_count = len(tl.split())
    suggestions = []

    # A) JD Similarity (0–35)
    jd_points = 0.0
    if jd_text and len(jd_text.split()) > 20:
        sim = tfidf_similarity(text, jd_text)
        jd_points = min(35.0, round(sim * 35.0, 1))
        if sim < 0.25:
            suggestions.append("Tailor content to the job description—add specific tools/skills from the JD.")
    else:
        suggestions.append("Paste a Job Description to improve match scoring.")

    # B) Role Keywords Coverage (0–25)
    role_words = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["General / Fresher"])
    found = has_any(tl, role_words)
    coverage = len(found) / max(len(set(role_words)), 1)
    kw_points = min(25.0, round(coverage * 25.0 + min(len(found), 12), 1))  # blend breadth + count
    if coverage < 0.5:
        missing = ", ".join(sorted(set(role_words) - set(found))[:10])
        suggestions.append(f"Add relevant {role} keywords (e.g., {missing}).")

    # C) Structure & Sections (0–15)
    struct = 0.0
    for sec, aliases in {
        "Summary/Objectives": ["summary","objective","profile"],
        "Experience": ["experience","work experience","professional experience","employment"],
        "Education": ["education","academics","university","college"],
        "Skills": ["skills","technical skills"],
        "Certifications": ["certifications","licenses","certificates"]
    }.items():
        if any(a in tl for a in aliases): struct += 15.0/5.0
        else: suggestions.append(f"Add a clear “{sec}” section.")
    struct = round(struct, 1)

    # D) Impact Signals (Action Verbs + Numbers) (0–15)
    nums = count_regex(tl, r"\b\d+[%k]?\b")
    actions = len(has_any(tl, ACTION_VERBS))
    impact = min(15.0, round(min(nums, 6)*1.8 + min(actions, 6)*0.9, 1))
    if nums < 3: suggestions.append("Quantify achievements with numbers (%, ₹, users, time saved).")
    if actions < 3: suggestions.append("Start bullets with strong action verbs (Led, Built, Improved...).")

    # E) ATS Basics & Formatting (0–10)
    email_ok = bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", tl))
    phone_ok = bool(re.search(r"\b(\+?\d{1,3}[-\s]?)?\d{10}\b", tl))
    bullets  = count_regex(text, r"(\n[-•·])|•")
    specials = sum(not (ch.isalnum() or ch.isspace() or ch in ".,;:-()/&+%") for ch in text) / max(len(text),1)
    ats = 0.0
    if email_ok: ats += 3
    if phone_ok: ats += 3
    if bullets >= 5: ats += 2
    if specials < 0.05: ats += 2
    if not email_ok: suggestions.append("Add a professional email in the header.")
    if not phone_ok: suggestions.append("Add a valid phone number with country code.")
    if specials >= 0.05: suggestions.append("Avoid heavy graphics/tables; use simple text formatting.")

    # F) Education & Certifications (0–5)
    edu_hits  = len(has_any(tl, EDU_WORDS))
    cert_hits = len(has_any(tl, CERT_WORDS))
    edu = min(5.0, round( (1 if edu_hits>0 else 0)*3 + min(cert_hits,2)*1.0 ,1))
    if edu_hits == 0: suggestions.append("Include Education (degree, college, year).")
    if cert_hits == 0: suggestions.append("Add relevant certifications (PMP, PL-300, Google/Meta, etc.).")

    if not (300 <= word_count <= 900):
        suggestions.append("Keep resume ~1–2 pages (approx. 600–800 words).")

    total = round(jd_points + kw_points + struct + impact + ats + edu, 1)
    breakdown = {
        "JD Similarity": jd_points,
        "Keywords": kw_points,
        "Structure": struct,
        "Impact": impact,
        "ATS": ats,
        "Education/Certs": edu,
        "Word Count": word_count
    }
    out = []
    for s in suggestions:
        if s not in out: out.append(s)
    return total, breakdown, out[:10]

def init_leads():
    if not os.path.exists(LEADS_CSV):
        pd.DataFrame(columns=["timestamp","name","email","phone","target_role","score","breakdown","word_count"]).to_csv(LEADS_CSV, index=False)

def save_lead(row: dict):
    init_leads()
    df = pd.read_csv(LEADS_CSV)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(LEADS_CSV, index=False)

# ---------------- UI ----------------
st.markdown(f"""
<div style='padding:10px 16px;border-radius:12px;background:{BRAND_PRIMARY};color:white'>
  <h2 style='margin:0'>🧠 AI Resume Score — Research‑backed</h2>
  <p style='margin:6px 0 0 0'>Paste a Job Description for best accuracy. We score JD match, keywords, sections, quantified impact, ATS basics, and credentials.</p>
</div>
""", unsafe_allow_html=True)

with st.form("form"):
    col1, col2 = st.columns([1,1])
    with col1:
        name  = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        role  = st.selectbox("Target Role", list(ROLE_KEYWORDS.keys()))
        resume_file = st.file_uploader("Upload Resume (PDF/DOCX/TXT)", type=["pdf","docx","txt"])
    with col2:
        jd_text = st.text_area("Paste Job Description (optional for higher accuracy)", height=220, placeholder="Paste JD here…")
        consent = st.checkbox("I agree to be contacted by LinkSkill Academy for training & placement.", value=True)
    submitted = st.form_submit_button("🔍 Score My Resume", use_container_width=True)

if submitted:
    if not (name and email and phone and resume_file and consent):
        st.error("Please fill all fields, upload a resume, and accept consent.")
    else:
        raw = extract_text(resume_file)
        if not raw.strip():
            st.error("Could not read your file. Please upload a text-based PDF/DOCX/TXT.")
        else:
            total, breakdown, tips = score_resume(raw, role, jd_text)
            save_lead({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "name": name, "email": email, "phone": phone,
                "target_role": role, "score": total, "breakdown": str(breakdown), "word_count": breakdown.get("Word Count", 0)
            })
            st.success(f"🎉 Resume Score: **{total}/100**")
            st.caption("Weights: JD 35, Keywords 25, Structure 15, Impact 15, ATS 10, Education 5.")

            a,b,c = st.columns(3)
            a.metric("JD Similarity", f"{breakdown['JD Similarity']}/35")
            b.metric("Keywords", f"{breakdown['Keywords']}/25")
            c.metric("Structure", f"{breakdown['Structure']}/15")
            d,e,f = st.columns(3)
            d.metric("Impact", f"{breakdown['Impact']}/15")
            e.metric("ATS", f"{breakdown['ATS']}/10")
            f.metric("Education/Certs", f"{breakdown['Education/Certs']}/5")

            st.markdown("#### 📌 Top Suggestions")
            for t in tips:
                st.write(f"- {t}")

            st.info("Want a Resume Makeover + Mock Interview? Visit our stall for the **Stall-Only Offer ₹999**.")

# Admin panel
with st.sidebar:
    st.markdown("### Leads Export")
    init_leads()
    df = pd.read_csv(LEADS_CSV)
    st.write(f"Total leads captured: **{len(df)}**")
    st.dataframe(df.tail(10))
    st.download_button("Download all leads (CSV)", df.to_csv(index=False).encode("utf-8"), file_name="leads.csv")
