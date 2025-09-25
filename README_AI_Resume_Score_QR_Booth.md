# AI Resume Score — QR Booth (Streamlit)

This app lets visitors scan a QR code, upload their resume, and instantly get a **score + feedback**. It also captures **leads** (name, email, phone) to a CSV.

## Run Locally
```bash
pip install -r requirements.txt
streamlit run ai_resume_score_app.py
```

## Deploy (Streamlit Community Cloud)
1. Push these 3 files to a GitHub repo.
2. On https://share.streamlit.io, create a new app pointing to `ai_resume_score_app.py`.
3. After deploy, copy the public URL and, in the app sidebar, paste it in **Public App URL** → click **Generate QR Code** to display/download a printable PNG.

## What it does
- Extracts text from **PDF/DOCX/TXT** resumes (PyPDF2 + docx2txt).
- Scores across 6 buckets: Structure, Keywords, Impact, Education/Certs, ATS, Formatting.
- Adapts **keywords** by Target Role (Data Analyst, BA, Digital Marketing, PM, UI/UX, etc.).
- Saves leads to `leads.csv`. Download any time from the sidebar.
- Generates a **QR code** for the app URL for booth posters.

## Notes
- This is a **heuristic** (rule-based) scorer for fast booth use. For deeper analysis, you can later add an LLM step.
- If `qrcode` or `Pillow` isn't installed, the app will still run; QR generation is disabled with a helpful warning.