"""
Trip Swarm — app.py

FastAPI application with Google OAuth, thread management,
travel planning, agentic RAG, document management, and report storage.

Travel agent  → stateless: each request is a fresh plan, no history passed.
RAG agent     → conversational: full chat history passed for context.
"""

import os
import io
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List
 
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
 
load_dotenv()
 
from database import get_db, engine
from models import Base, User, ChatThread, ChatMessage, TripReport, UserDocument
from backend import run_travel_workflow
from rag_backend import run_rag_workflow, add_document_to_chroma, delete_document
 
Base.metadata.create_all(bind=engine)
 
app = FastAPI(title="Trip Swarm API", version="1.0.0")
 
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY"),
    max_age=86400 * 7,
    same_site="lax",
    https_only=os.getenv("HTTPS_ONLY", "false").lower() == "true",
)
 
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
 
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "prompt": "select_account"},
)
 
IST = timezone(timedelta(hours=5, minutes=30))
 
 
def now_ist() -> datetime:
    return datetime.now(tz=IST)
 
 
def fmt_utc(dt: datetime) -> str:
    """Serialise datetime to UTC ISO-8601 with Z suffix."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
 
 
# Auth Helpers
 
def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()
 
 
def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
 
 
# PDF Export (ReportLab) 

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FFFF"
    "\U00002600-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)
 
 
def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()
 
 
def _markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        Table, TableStyle, Image, ListFlowable, ListItem,
    )
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from pathlib import Path
 
    try:
        pdfmetrics.registerFont(TTFont("DejaVu",      "static/fonts/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", "static/fonts/DejaVuSans-Bold.ttf"))
    except Exception:
        pass
 
    BLUE      = HexColor("#38bdf8")
    BLUE_DIM  = HexColor("#e0f7ff")
    DARK      = HexColor("#1e293b")
    SLATE     = HexColor("#64748b")
    WHITE     = colors.white
    LIGHT_ROW = HexColor("#f8fafc")
    BORDER    = HexColor("#cbd5e1")
 
    page_w, page_h = A4
    margin = 2 * cm
    buf = io.BytesIO()
 
    def _header_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BLUE); canvas.setLineWidth(2)
        canvas.line(margin, page_h - margin + 6, page_w - margin, page_h - margin + 6)
        canvas.setFont("Helvetica", 8); canvas.setFillColor(SLATE)
        canvas.drawCentredString(page_w / 2, margin / 2, f"Trip Swarm  ·  Page {doc.page}")
        canvas.setStrokeColor(BORDER); canvas.setLineWidth(0.5)
        canvas.line(margin, margin - 4, page_w - margin, margin - 4)
        canvas.restoreState()
 
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin + 0.4 * cm, bottomMargin=margin + 0.2 * cm,
        onFirstPage=_header_footer, onLaterPages=_header_footer,
    )
 
    FONT_NORMAL = "DejaVu"
    FONT_BOLD   = "DejaVu-Bold"
    FONT_ITALIC = "Helvetica-Oblique"
 
    def style(name, **kw):
        return ParagraphStyle(name, **kw)
 
    S = {
        "title":  style("TripTitle", fontName=FONT_BOLD,   fontSize=22, textColor=BLUE,  spaceAfter=6,  alignment=TA_CENTER, leading=26),
        "h1":     style("H1",        fontName=FONT_BOLD,   fontSize=16, textColor=BLUE,  spaceBefore=14, spaceAfter=6,  leading=20),
        "h2":     style("H2",        fontName=FONT_BOLD,   fontSize=13, textColor=DARK,  spaceBefore=10, spaceAfter=4,  leading=16),
        "h3":     style("H3",        fontName=FONT_BOLD,   fontSize=11, textColor=SLATE, spaceBefore=8,  spaceAfter=3,  leading=14),
        "body":   style("Body",      fontName=FONT_NORMAL, fontSize=10, textColor=DARK,  spaceAfter=4,  leading=15),
        "bullet": style("Bullet",    fontName=FONT_NORMAL, fontSize=10, textColor=DARK,  leftIndent=14, spaceAfter=3, leading=14, bulletIndent=4, bulletFontName=FONT_NORMAL),
        "meta":   style("Meta",      fontName=FONT_ITALIC, fontSize=9,  textColor=SLATE, spaceAfter=12, leading=12, alignment=TA_CENTER),
    }
 
    def _inline(text: str) -> str:
        text = _strip_emoji(text)
        text = re.sub(r"\\([*_`\\])", r"\1", text)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
        text = re.sub(r"\*\*(.+?)\*\*",     r"<b>\1</b>",         text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r'<font name="Courier" size="9" color="#0369a1">\1</font>', text)
        return text
 
    def _parse_table(lines: list):
        rows = []
        for raw in lines:
            stripped = raw.strip().strip("|")
            if re.match(r"^[\s\-:|\s]+$", stripped):
                continue
            rows.append([c.strip() for c in stripped.split("|")])
        if len(rows) < 2:
            return None
        header, data_rows = rows[0], rows[1:]
        col_count  = len(header)
        table_data = [[Paragraph(f"<b>{_inline(h)}</b>", S["body"]) for h in header]]
        for dr in data_rows:
            while len(dr) < col_count: dr.append("")
            table_data.append([Paragraph(_inline(c), S["body"]) for c in dr[:col_count]])
        avail_w = page_w - 2 * margin
        tbl = Table(table_data, colWidths=[avail_w / col_count] * col_count, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",     (0,0),  (-1,0),  BLUE_DIM),
            ("TEXTCOLOR",      (0,0),  (-1,0),  DARK),
            ("FONTNAME",       (0,0),  (-1,0),  FONT_BOLD),
            ("FONTSIZE",       (0,0),  (-1,0),  9.5),
            ("FONTNAME",       (0,1),  (-1,-1), FONT_NORMAL),
            ("FONTSIZE",       (0,1),  (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1),  (-1,-1), [WHITE, LIGHT_ROW]),
            ("GRID",           (0,0),  (-1,-1), 0.4, BORDER),
            ("VALIGN",         (0,0),  (-1,-1), "TOP"),
            ("LEFTPADDING",    (0,0),  (-1,-1), 6),
            ("RIGHTPADDING",   (0,0),  (-1,-1), 6),
            ("TOPPADDING",     (0,0),  (-1,-1), 5),
            ("BOTTOMPADDING",  (0,0),  (-1,-1), 5),
        ]))
        return tbl
 
    story = []
    logo_path = Path("static/images/Trip_Swarm_Logo.png")
    if logo_path.exists():
        logo = Image(str(logo_path))
        logo.drawHeight = 3 * cm; logo.drawWidth = 3 * cm; logo.hAlign = "CENTER"
        story.append(logo); story.append(Spacer(1, 0.3 * cm))
 
    def _add_rule():
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))
 
    lines = markdown_text.splitlines()
    n = len(lines); i = 0
 
    doc_title = "Trip Plan"
    for ln in lines:
        if ln.startswith("# "):     doc_title = _strip_emoji(ln[2:].strip()); break
        elif ln.strip():            doc_title = _strip_emoji(ln.strip());      break
 
    story.append(Paragraph(_inline(doc_title), S["title"]))
    story.append(Paragraph(f"Generated by Trip Swarm  ·  {datetime.now().strftime('%d %b %Y')}", S["meta"]))
    _add_rule()
 
    while i < n:
        line = lines[i]
        if not line.strip(): i += 1; continue
        if line.startswith("# ") and i == 0: i += 1; continue
        if line.startswith("# "):   story.append(Paragraph(_inline(line[2:].strip()), S["h1"])); i += 1; continue
        if line.startswith("## "):  story.append(Paragraph(_inline(line[3:].strip()), S["h2"])); i += 1; continue
        if line.startswith("### "): story.append(Paragraph(_inline(line[4:].strip()), S["h3"])); i += 1; continue
        if re.match(r"^[-*_]{3,}\s*$", line): _add_rule(); i += 1; continue
        if line.strip().startswith("|"):
            tbl_lines = []
            while i < n and lines[i].strip().startswith("|"): tbl_lines.append(lines[i]); i += 1
            tbl = _parse_table(tbl_lines)
            if tbl: story.append(Spacer(1, 6)); story.append(tbl); story.append(Spacer(1, 8))
            continue
        if re.match(r"^[\-\*\+] ", line):
            items = []
            while i < n and re.match(r"^[\-\*\+] ", lines[i]):
                items.append(ListItem(Paragraph(_inline(lines[i][2:].strip()), S["bullet"]), bulletColor=BLUE)); i += 1
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=18, bulletFontSize=10, bulletOffsetY=-1))
            story.append(Spacer(1, 4)); continue
        if re.match(r"^\d+\. ", line):
            items = []
            while i < n and re.match(r"^\d+\. ", lines[i]):
                items.append(ListItem(Paragraph(_inline(re.sub(r"^\d+\.\s*", "", lines[i]).strip()), S["bullet"]), bulletColor=BLUE)); i += 1
            story.append(ListFlowable(items, bulletType="1", leftIndent=18, bulletFontSize=10))
            story.append(Spacer(1, 4)); continue
        if line.startswith("> "):
            quote_lines = []
            while i < n and lines[i].startswith("> "): quote_lines.append(lines[i][2:]); i += 1
            bq_style = style("BQ", fontName=FONT_ITALIC, fontSize=10, textColor=SLATE, leftIndent=18, spaceAfter=6, borderPad=4, borderWidth=0, leading=14)
            story.append(Paragraph(f"<i>{_inline(' '.join(quote_lines))}</i>", bq_style)); continue
        if line.startswith("```"):
            code_lines = []; i += 1
            while i < n and not lines[i].startswith("```"): code_lines.append(lines[i]); i += 1
            i += 1
            code_style = style("Code", fontName="Courier", fontSize=8, textColor=DARK, backColor=LIGHT_ROW, leftIndent=10, rightIndent=10, spaceAfter=6, leading=12)
            story.append(Paragraph("\n".join(code_lines).replace("\n", "<br/>"), code_style)); continue
        story.append(Paragraph(_inline(line.strip()), S["body"])); i += 1
 
    doc.build(story)
    buf.seek(0)
    return buf.read()
 
 
# Pages
 
@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db: Session = Depends(get_db)):
    """
    Always serve the marketing homepage (index.html).
    Session state is checked client-side via /api/me — no server-side redirect here.
    """
    return templates.TemplateResponse(request=request, name="index.html")
 
 
@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: Session = Depends(get_db)):
    """
    Serve the chat application (chat.html).
    Requires an active session — redirect to / if not logged in.
    The ?mode and ?q query params are handled client-side by app.js.
    """
    user = get_current_user(request, db)
    if not user:
        # Preserve the original destination so we can redirect back after login
        next_url = str(request.url)
        return RedirectResponse(url=f"/?next={next_url}", status_code=302)
    return templates.TemplateResponse(request=request, name="chat.html", context={"user": user})


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html")
 
 
# Session check endpoint (used by homepage JS)─
 
@app.get("/api/me")
async def api_me(request: Request, db: Session = Depends(get_db)):
    """
    Returns current session state for the homepage to render auth-aware UI.
    Safe to call unauthenticated — never raises 401.
    """
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"logged_in": False, "user": None})
    return JSONResponse({
        "logged_in": True,
        "user": {
            "id":      user.id,
            "name":    user.name,
            "email":   user.email,
            "picture": user.picture or "",
        },
    })
 
 
# Google OAuth
 
@app.get("/auth/login")
async def auth_login(request: Request):
    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri, prompt="select_account")
 
 
@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token     = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            user_info = await oauth.google.userinfo(token=token)
 
        google_id = user_info["sub"]
        email     = user_info["email"]
        name      = user_info.get("name", email.split("@")[0])
        picture   = user_info.get("picture", "")
 
        user = db.query(User).filter(User.google_id == google_id).first()
        if not user:
            user = User(google_id=google_id, email=email, name=name, picture=picture)
            db.add(user)
        else:
            user.name    = name
            user.picture = picture
 
        db.commit()
        db.refresh(user)
        request.session["user_id"] = user.id
 
        # After successful login always go to /chat
        return RedirectResponse(url="/chat", status_code=302)
 
    except Exception as e:
        print(f"Auth error: {e}")
        return RedirectResponse(url="/?error=auth_failed", status_code=302)
 
 
@app.get("/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    # Always return to homepage after logout
    return RedirectResponse(url="/", status_code=302)
 
 
# Thread Mangement
 
@app.get("/api/threads")
async def list_threads(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    threads = (
        db.query(ChatThread)
        .filter(ChatThread.user_id == user.id)
        .order_by(ChatThread.updated_at.desc())
        .limit(60)
        .all()
    )
    return JSONResponse([
        {
            "id":         t.id,
            "title":      t.title,
            "type":       t.thread_type,
            "created_at": fmt_utc(t.created_at),
            "updated_at": fmt_utc(t.updated_at),
        }
        for t in threads
    ])
 
 
@app.post("/api/threads")
async def create_thread(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    body = await request.json()
    thread = ChatThread(
        user_id=user.id,
        thread_type=body.get("type", "travel"),
        title=body.get("title", "New Chat"),
    )
    db.add(thread); db.commit(); db.refresh(thread)
    return JSONResponse({
        "id":         thread.id,
        "title":      thread.title,
        "type":       thread.thread_type,
        "created_at": fmt_utc(thread.created_at),
        "updated_at": fmt_utc(thread.updated_at),
    })
 
 
@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: int, request: Request, db: Session = Depends(get_db)):
    user   = require_user(request, db)
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.user_id == user.id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    db.delete(thread); db.commit()
    return JSONResponse({"ok": True})
 
 
@app.patch("/api/threads/{thread_id}/rename")
async def rename_thread(thread_id: int, request: Request, db: Session = Depends(get_db)):
    user      = require_user(request, db)
    body      = await request.json()
    new_title = (body.get("title") or "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title is required")
    if len(new_title) > 80:
        raise HTTPException(status_code=400, detail="Title too long (max 80 chars)")
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.user_id == user.id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.title      = new_title
    thread.updated_at = datetime.utcnow()
    db.commit()
    return JSONResponse({"id": thread.id, "title": thread.title, "updated_at": fmt_utc(thread.updated_at)})
 
 
@app.get("/api/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: int, request: Request, db: Session = Depends(get_db)):
    user   = require_user(request, db)
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.user_id == user.id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return JSONResponse([
        {"id": m.id, "role": m.role, "content": m.content, "created_at": fmt_utc(m.created_at)}
        for m in messages
    ])
 
 
# Travel Planning
 
@app.post("/api/travel")
async def travel_endpoint(request: Request, db: Session = Depends(get_db)):
    user    = require_user(request, db)
    body    = await request.json()
    message   = (body.get("message") or "").strip()
    thread_id = body.get("thread_id")
 
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
 
    thread = None
    if thread_id:
        thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.user_id == user.id).first()
    if not thread:
        thread = ChatThread(user_id=user.id, thread_type="travel", title=message[:60] + ("..." if len(message) > 60 else ""))
        db.add(thread); db.commit(); db.refresh(thread)
 
    user_msg = ChatMessage(thread_id=thread.id, user_id=user.id, role="user", content=message)
    db.add(user_msg)
 
    result        = await run_travel_workflow(message=message, user_id=str(user.id))
    response_text = result.get("response", "No response generated.")
 
    ai_msg = ChatMessage(thread_id=thread.id, user_id=user.id, role="assistant", content=response_text)
    db.add(ai_msg)
 
    thread.updated_at = datetime.utcnow()
    if not db.query(ChatMessage).filter(ChatMessage.thread_id == thread.id, ChatMessage.role == "user").count() > 1:
        thread.title = message[:60]
 
    report = TripReport(user_id=user.id, thread_id=thread.id, title=f"Trip Plan: {message[:55]}", content=response_text)
    db.add(report); db.commit()
    db.refresh(user_msg); db.refresh(ai_msg)
 
    return JSONResponse({
        "response":             response_text,
        "thread_id":            thread.id,
        "thread_title":         thread.title,
        "user_created_at":      fmt_utc(user_msg.created_at),
        "assistant_created_at": fmt_utc(ai_msg.created_at),
    })
 

# Agentic RAG (Q&A) - Conversational

 
@app.post("/api/rag")
async def rag_endpoint(request: Request, db: Session = Depends(get_db)):
    user      = require_user(request, db)
    body      = await request.json()
    query     = (body.get("query") or "").strip()
    thread_id = body.get("thread_id")
 
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
 
    thread = None
    if thread_id:
        thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.user_id == user.id).first()
    if not thread:
        thread = ChatThread(user_id=user.id, thread_type="rag", title=query[:60] + ("..." if len(query) > 60 else ""))
        db.add(thread); db.commit(); db.refresh(thread)
 
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(20)
        .all()
    )
    chat_history = [{"role": m.role, "content": m.content} for m in history_rows]
 
    user_msg = ChatMessage(thread_id=thread.id, user_id=user.id, role="user", content=query)
    db.add(user_msg)
 
    result = await run_rag_workflow(query=query, user_id=str(user.id), chat_history=chat_history)
    answer = result.get("answer", "No answer generated.")
 
    ai_msg = ChatMessage(thread_id=thread.id, user_id=user.id, role="assistant", content=answer)
    db.add(ai_msg)
    thread.updated_at = datetime.utcnow()
    if not history_rows:
        thread.title = query[:60]
 
    db.commit()
    db.refresh(user_msg); db.refresh(ai_msg)
 
    return JSONResponse({
        "answer":               answer,
        "source":               result.get("source", "llm"),
        "documents_used":       result.get("documents_used", []),
        "thread_id":            thread.id,
        "user_created_at":      fmt_utc(user_msg.created_at),
        "assistant_created_at": fmt_utc(ai_msg.created_at),
    })
 
 
# Document Management
 
@app.post("/api/docs/upload")
async def upload_documents(request: Request, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    user     = require_user(request, db)
    uploaded = []
    for file in files:
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"{file.filename} exceeds 50MB limit")
        doc_id = await add_document_to_chroma(
            file_content=content, filename=file.filename,
            content_type=file.content_type or "text/plain", user_id=str(user.id),
        )
        db.add(UserDocument(
            user_id=user.id, filename=file.filename, chroma_doc_id=doc_id,
            file_size=len(content), content_type=file.content_type or "application/octet-stream",
        ))
        uploaded.append({"filename": file.filename, "doc_id": doc_id})
    db.commit()
    return JSONResponse({"uploaded": uploaded, "count": len(uploaded)})
 
 
@app.get("/api/docs")
async def list_documents(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    docs = db.query(UserDocument).filter(UserDocument.user_id == user.id).order_by(UserDocument.created_at.desc()).all()
    return JSONResponse([
        {"id": d.id, "filename": d.filename, "file_size": d.file_size, "content_type": d.content_type, "created_at": fmt_utc(d.created_at)}
        for d in docs
    ])
 
 
@app.delete("/api/docs/{doc_id}")
async def delete_doc(doc_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    doc  = db.query(UserDocument).filter(UserDocument.id == doc_id, UserDocument.user_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.chroma_doc_id:
        await delete_document(chroma_doc_id=doc.chroma_doc_id, user_id=str(user.id))
    db.delete(doc); db.commit()
    return JSONResponse({"ok": True})
 
 
@app.get("/api/debug/chroma/{user_id}")
async def debug_chroma(user_id: str, request: Request, db: Session = Depends(get_db)):
    from rag_backend import get_collection
    collection   = get_collection()
    by_string    = collection.get(where={"user_id": {"$eq": user_id}})
    all_docs     = collection.get()
    all_user_ids = list({m["user_id"] for m in all_docs["metadatas"]}) if all_docs["metadatas"] else []
    user         = db.query(User).filter(User.id == int(user_id)).first()
    db_docs      = db.query(UserDocument).filter(UserDocument.user_id == int(user_id)).all() if user else []
    return {
        "queried_user_id":       user_id,
        "chroma_chunks_found":   len(by_string["ids"]),
        "all_user_ids_in_chroma": all_user_ids,
        "db_documents":          [{"filename": d.filename, "chroma_doc_id": d.chroma_doc_id} for d in db_docs],
        "total_chunks_in_chroma": len(all_docs["ids"]),
    }
 
 
# Trip Reports
 
@app.get("/api/reports")
async def list_reports(request: Request, db: Session = Depends(get_db)):
    user    = require_user(request, db)
    reports = (
        db.query(TripReport)
        .filter(TripReport.user_id == user.id)
        .order_by(TripReport.created_at.desc())
        .limit(60)
        .all()
    )
    return JSONResponse([
        {"id": r.id, "title": r.title, "content": r.content, "created_at": fmt_utc(r.created_at)}
        for r in reports
    ])
 
 
@app.post("/api/export/pdf")
async def export_pdf(request: Request, db: Session = Depends(get_db)):
    user    = require_user(request, db)
    body    = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")
    try:
        pdf_bytes = _markdown_to_pdf_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="trip-plan-{user.id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
 
 
# Health
 
@app.get("/health")
async def health():
    return {"status": "ok", "service": "Trip Swarm"}
 
 
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")