
# ai_resume_score_app.py (v1.3)
# Robust PDF support: tries 'pypdf' first, falls back to 'PyPDF2'.

import io
import re
import time
import base64
import os
import pandas as pd
import streamlit as st
from datetime import datetime

# PDF libs (robust import)
PyPDF2 = None
try:
    import pypdf as PyPDF2  # new library name
except Exception:
    try:
        import PyPDF2  # legacy package
    except Exception:
        PyPDF2 = None

# Optional deps (handled gracefully):
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

ALLOWED_EXTS = (".pdf", ".docx", ".txt")
MAX_FILE_MB  = 5
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

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
    "streamlined","orchestrated","scaled","architected","spearheaded"
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

def fmt_mb(num_bytes):
    return f"{num_bytes/1024/1024:.1f} MB"

def precheck_file(file):
    name = file.name
    size = getattr(file, "size", None)
    ext = os.path.splitext(name)[1].lower()
    checks = {
        "type_supported": ext in ALLOWED_EXTS,
        "size_ok": (size is not None and size <= MAX_FILE_BYTES),
        "not_empty": (size or 0) > 0,
        "readable_text": False,
        "not_password_protected": True,
        "pdf_reader_available": PyPDF2 is not None if ext == ".pdf" else True
    }
    first_error = ""
    if not checks["type_supported"]:
        return checks, "Unsupported file type. Please upload PDF, DOCX or TXT."
    if not checks["not_empty"]:
        return checks, "This file is empty. Please upload a valid resume file."
    if not checks["size_ok"]:
        return checks, f"File too large ({fmt_mb(size)}). Max allowed is {MAX_FILE_MB} MB."
    if ext == ".pdf" and not checks["pdf_reader_available"]:
        return checks, "PDF reader is not available on server. Ask us at the desk or upload DOCX."
    try:
        data = file.read()
        file.seek(0)
        if ext == ".pdf" and PyPDF2 is not None:
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(data))
                if getattr(reader, "is_encrypted", False):
                    try:
                        reader.decrypt("")
                    except Exception:
                        checks["not_password_protected"] = False
                        return checks, "This PDF is password-protected. Export an unlocked PDF or upload DOCX."
                txt = ""
                pages = getattr(reader, "pages", [])
                for p in pages[:2]:
                    try:
                        txt += p.extract_text() or ""
                    except Exception:
                        continue
                checks["readable_text"] = bool(txt.strip())
                if not checks["readable_text"]:
                    return checks, "This PDF looks like a scanned image. Upload a text-based PDF or DOCX."
            except Exception:
                return checks, "We couldn't open this PDF. Export a new text-based PDF or upload DOCX."
        else:
            checks["readable_text"] = True
    except Exception:
        return checks, "We couldn't read this file. Re-upload or try a different format."
    return checks, ""

def extract_text_from_file(uploaded_file):
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    uploaded_file.seek(0)
    if name.endswith(".pdf"):
        if PyPDF2 is None:
            return "", "PDF reader not available on server."
        text = ""
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            if getattr(reader, "is_encrypted", False):
                try:
                    reader.decrypt("")
                except Exception:
                    return "", "This PDF is password-protected. Export an unlocked PDF or upload DOCX."
            for page in reader.pages:
                try:
                    text += page.extract_text() or ""
                except Exception:
                    continue
        except Exception:
            return "", "We couldn't open this PDF. Export a new text-based PDF or upload DOCX."
        if not text.strip():
            return "", "This PDF looks like a scanned image. Upload a text-based PDF or DOCX."
        return text, ""
    if name.endswith(".docx"):
        if docx2txt is None:
            return "", "DOCX reader not available on server."
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(data); tmp.flush()
                path = tmp.name
            text = docx2txt.process(path) or ""
            try: os.remove(path)
            except Exception: pass
            if not text.strip():
                return "", "We couldn't read text from this DOCX. Save again or upload as PDF."
            return text, ""
        except Exception:
            return "", "We couldn't open this DOCX. Save again or upload as PDF."
    if name.endswith(".txt"):
        try:
            return data.decode("utf-8", errors="ignore"), ""
        except Exception:
            return "", "This text file could not be read. Please try a PDF or DOCX."
    return "", "Unsupported file type. Please upload PDF, DOCX or TXT."

def contains_any(text, words):
    tl = text.lower()
    return [w for w in words if w in tl]

def count_regex(text, pattern, flags=re.I):
    return len(re.findall(pattern, text, flags))

def score_resume(text, target_role="General / Fresher", extra_keywords=None):
    tl = text.lower()
    word_count = len(tl.split())
    suggestions = []
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
    role_words = ROLE_KEYWORDS.get(target_role, ROLE_KEYWORDS["General / Fresher"]).copy()
    if extra_keywords:
        role_words += [k.strip().lower() for k in extra_keywords.split(",") if k.strip()]
    found_role = contains_any(tl, role_words)
    kw_points = min(len(found_role) * (30/12), 30)
    if len(found_role) < 8:
        suggestions.append(f"Include more role keywords (target: {target_role}). Missing examples: " +
                           ", ".join(sorted(set(role_words) - set(found_role))[:8]))
    nums = count_regex(tl, r"\b\d+[%k]?\b")
    action_uses = len(contains_any(tl, ACTION_VERBS))
    impact_points = min(10 + min(nums, 5)*2 + min(action_uses, 5)*1.5, 20)
    if nums < 3:
        suggestions.append("Quantify achievements (%, ₹, numbers) to show impact.")
    if action_uses < 3:
        suggestions.append("Start bullet points with strong action verbs (Led, Built, Improved...).")
    edu_hits = len(contains_any(tl, EDU_WORDS))
    cert_hits = len(contains_any(tl, CERT_WORDS))
    edu_points = min(edu_hits*2 + min(cert_hits, 3)*2, 10)
    if edu_hits == 0:
        suggestions.append("Add Education details (degree, college, year).")
    if cert_hits == 0:
        suggestions.append("List relevant certifications (PMP, PL-300, Google, Meta, etc.).")
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
    if 350 <= word_count <= 900: fmt_points = 10
    else:
        fmt_points = max(0, 10 - abs(word_count-600)/100)
        suggestions.append("Keep resume concise (1–2 pages; ~600–800 words recommended).")
    total = round(structure_points + kw_points + impact_points + edu_points + ats_points + fmt_points, 1)
    breakdown = {
        "Structure": structure_points, "Keywords": round(kw_points,1), "Impact": round(impact_points,1),
        "Education/Certs": round(edu_points,1), "ATS": round(ats_points,1), "Formatting": round(fmt_points,1),
        "Word Count": word_count
    }
    cleaned = []
    for s in suggestions:
        if s not in cleaned: cleaned.append(s)
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

def make_qr_png_bytes(url: str):
    if not qrcode or not Image:
        st.warning("Install 'qrcode' and 'Pillow' to generate QR codes (see requirements.txt).")
        return None
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
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

st.markdown(f"### 👇 Get Your Resume Score")
st.caption(f"Allowed: **PDF/DOCX/TXT** • Max size: **{MAX_FILE_MB} MB** • If upload fails in Instagram/LinkedIn, open in Chrome/Safari.")

with st.form("resume_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        name  = st.text_input("Full Name", "")
        email = st.text_input("Email", "")
        phone = st.text_input("Phone", "")
    with col2:
        target_role = st.selectbox("Target Role", list(ROLE_KEYWORDS.keys()), index=0)
        extra_kw = st.text_input("Extra Keywords (comma-separated, optional)", placeholder="power bi, pl-300, snowflake")
    uploaded = st.file_uploader("Upload Resume", type=[ext.strip(".") for ext in ALLOWED_EXTS], accept_multiple_files=False)
    agree = st.checkbox("I agree to be contacted by LinkSkill Academy about training & placement.")
    submitted = st.form_submit_button("🔍 Score My Resume", use_container_width=True)

if submitted:
    if not (name and email and phone and uploaded and agree):
        st.error("Please fill all fields, upload a resume, and accept the consent checkbox.")
    else:
        checks, first_error = precheck_file(uploaded)
        st.markdown("#### Pre-checks")
        cols = st.columns(6)
        cols[0].write(("✅" if checks["type_supported"] else "❌") + " Type supported")
        size_txt = f"{fmt_mb(getattr(uploaded, 'size', 0))} / {MAX_FILE_MB} MB"
        cols[1].write(("✅" if checks["size_ok"] else "❌") + f" Size OK ({size_txt})")
        cols[2].write(("✅" if checks["not_empty"] else "❌") + " Not empty")
        cols[3].write(("✅" if checks["not_password_protected"] else "❌") + " Not password-protected")
        cols[4].write(("✅" if checks["pdf_reader_available"] else "❌") + " PDF reader available")
        cols[5].write(("✅" if checks["readable_text"] else "⚠️") + " Text is readable")

        if first_error:
            st.error(first_error)
        else:
            with st.spinner("Analyzing your resume..."):
                raw_text, hint = extract_text_from_file(uploaded)
                if hint:
                    st.error(hint)
                elif not raw_text.strip():
                    st.error("We couldn't read any text. Please upload a **text-based** PDF or a DOCX file (not a photo/scanned image).")
                else:
                    total, breakdown, suggestions = score_resume(raw_text, target_role, extra_kw)
                    save_lead({
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "name": name, "email": email, "phone": phone,
                        "target_role": target_role, "extra_keywords": extra_kw,
                        "score": total, "breakdown": str(breakdown), "word_count": breakdown.get("Word Count", 0)
                    })
                    st.success(f"🎉 Your Resume Score: **{total}/100**")
                    met1, met2, met3 = st.columns(3)
                    met1.metric("Structure", f"{breakdown['Structure']}/20")
                    met2.metric("Keywords", f"{breakdown['Keywords']}/30")
                    met3.metric("Impact", f"{breakdown['Impact']}/20")
                    met4, met5, met6 = st.columns(3)
                    met4.metric("Education/Certs", f"{breakdown['Education/Certs']}/10")
                    met5.metric("ATS", f"{breakdown['ATS']}/10")
                    met6.metric("Formatting", f"{breakdown['Formatting']}/10")
                    st.markdown("#### 📌 Top Suggestions")
                    for s in suggestions: st.write(f"- {s}")
                    st.markdown("---")
                    st.info("Want a professional Resume Makeover & Mock Interview? Visit our stall for the **Stall-Only Offer ₹999**.")

st.markdown("---")
st.markdown(f"""
<div style="padding:8px 12px;border:1px dashed {BRAND_ACCENT};border-radius:10px">
  <b>Privacy:</b> Your details are stored only for the event follow-up by LinkSkill Academy.
</div>
""", unsafe_allow_html=True)
