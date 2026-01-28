import os
import time
import random
import string
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ================= CONFIG =================
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL", "https://example.com")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# ================= DB SETUP =================
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Link(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, index=True)
    target = Column(String)
    clicks = Column(Integer, default=0)
    step2_views = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    created_at = Column(Integer)

Base.metadata.create_all(bind=engine)

# ================= APP =================
app = FastAPI()
ADMIN_COOKIE = "admin_session"

# ================= HELPERS =================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_admin_cookie(request: Request):
    if request.cookies.get(ADMIN_COOKIE) != "true":
        raise HTTPException(status_code=403, detail="Admin only")

def generate_slug(length=6):
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

# ================= HEALTH =================
@app.get("/health")
async def health():
    return {"status": "alive"}

# ================= HOME =================
@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h2 style='text-align:center'>Fast Link Gateway</h2>"

# ================= ADMIN LOGIN =================
@app.get("/admin", response_class=HTMLResponse)
async def admin_login():
    return """
    <form method="post" action="/admin/login">
        <input type="password" name="password" placeholder="Admin password">
        <button>Login</button>
    </form>
    """

@app.post("/admin/login")
async def admin_do_login(password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Wrong password")
    resp = RedirectResponse("/admin/panel", status_code=302)
    resp.set_cookie(
        ADMIN_COOKIE,
        "true",
        max_age=86400,
        httponly=True,
        samesite="lax"
    )
    return resp

# ================= ADMIN PANEL =================
@app.get("/admin/panel", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    check_admin_cookie(request)
    rows = ""
    for l in db.query(Link).all():
        rows += f"<tr><td>{l.slug}</td><td>{l.clicks}</td><td>{l.step2_views}</td><td>{l.completed}</td></tr>"
    return f"""
    <h3>Create Link</h3>
    <form method="post" action="/admin/create">
        <input name="target" placeholder="Target URL">
        <button>Create</button>
    </form>

    <table border="1">
        <tr><th>Slug</th><th>Clicks</th><th>Step2</th><th>Completed</th></tr>
        {rows}
    </table>
    """

@app.post("/admin/create", response_class=HTMLResponse)
async def admin_create(request: Request, target: str = Form(...), db: Session = Depends(get_db)):
    check_admin_cookie(request)
    slug = generate_slug()
    while db.query(Link).filter_by(slug=slug).first():
        slug = generate_slug()
    db.add(Link(
        slug=slug,
        target=target,
        created_at=int(time.time())
    ))
    db.commit()
    return f"<p>Created: <b>{BASE_URL}/go/{slug}</b></p><a href='/admin/panel'>Back</a>"

# ================= PAGE 1 =================
@app.get("/go/{slug}", response_class=HTMLResponse)
async def page1(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return HTMLResponse("Invalid", 404)

    link.clicks += 1
    db.commit()

    return f"""
<!DOCTYPE html>
<html>
<body>
<h2>Please wait <span id="t">20</span>s</h2>
<div id="go" style="display:none">
<a href="/step2/{slug}">Continue</a>
</div>

<script>
let t=20, timer=null;
function start(){{
 if(timer) return;
 timer=setInterval(()=>{{
  document.getElementById("t").innerText=t;
  if(t<=0){{clearInterval(timer);document.getElementById("go").style.display="block";}}
  t--;
 }},1000);
}}
start();
document.addEventListener("visibilitychange",()=>{{ if(document.hidden) clearInterval(timer); else timer=null,start(); }});
</script>
</body>
</html>
"""

# ================= PAGE 2 =================
@app.get("/step2/{slug}", response_class=HTMLResponse)
async def step2(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return HTMLResponse("Invalid", 404)

    link.step2_views += 1
    db.commit()

    return f"""
<!DOCTYPE html>
<html>
<body>
<h2>Almost done</h2>
<div id="b" style="display:none">
<a href="/redirect/{slug}">Open Link</a>
</div>
<script>
setTimeout(()=>{{document.getElementById("b").style.display="block"}},7000);
</script>
</body>
</html>
"""

# ================= FINAL REDIRECT =================
@app.get("/redirect/{slug}")
async def final(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return RedirectResponse("/")
    link.completed += 1
    db.commit()
    return RedirectResponse(link.target)