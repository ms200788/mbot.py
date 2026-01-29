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

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

BASE_URL = "https://telegram-93bm.onrender.com"

ADMIN_COOKIE = "admin_session"

# ================= DB SETUP =================
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)

Base = declarative_base()


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, index=True)
    target = Column(String)
    clicks = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    created_at = Column(Integer)


Base.metadata.create_all(bind=engine)

# ================= APP =================
app = FastAPI()


# ================= HELPERS =================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_admin_cookie(request: Request):
    if request.cookies.get(ADMIN_COOKIE) != "true":
        raise HTTPException(status_code=403, detail="Forbidden: Admin only")


def generate_slug(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


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
<!DOCTYPE html>
<html>
<body style="background:#0f2027;color:#fff;font-family:system-ui">
<div style="background:#fff;color:#000;border-radius:16px;padding:16px;margin:16px">
<h3>Admin Login</h3>
<form method="post" action="/admin/login">
<input type="password" name="password" placeholder="Admin password" style="width:100%;padding:12px">
<button style="width:100%;padding:12px;margin-top:10px;background:#ff4b2b;color:#fff;border:none">
Login
</button>
</form>
</div>
</body>
</html>
"""


@app.post("/admin/login")
async def admin_do_login(password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden: Wrong password")

    response = RedirectResponse("/admin/panel", status_code=302)
    response.set_cookie(
        ADMIN_COOKIE,
        "true",
        max_age=86400,
        path="/",
        samesite="lax"
    )
    return response


# ================= ADMIN PANEL =================
@app.get("/admin/panel", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    check_admin_cookie(request)

    links = db.query(Link).all()
    rows = "".join(
        f"<tr><td>{l.slug}</td><td>{l.target}</td><td>{l.clicks}</td><td>{l.completed}</td></tr>"
        for l in links
    )

    return f"""
<html>
<body style="background:#0f2027;color:#fff;font-family:system-ui">
<div style="background:#fff;color:#000;border-radius:16px;padding:16px;margin:16px">
<h3>Create Funnel Link</h3>
<form method="post" action="/admin/create">
<input type="url" name="target" required style="width:100%;padding:12px">
<button style="width:100%;padding:12px;margin-top:8px;background:#4caf50;color:#fff;border:none">
Create
</button>
</form>
</div>

<div style="background:#fff;color:#000;border-radius:16px;padding:16px;margin:16px">
<h3>Stats</h3>
<table border="1" width="100%">
<tr><th>Slug</th><th>Target</th><th>Clicks</th><th>Completed</th></tr>
{rows}
</table>
</div>
</body>
</html>
"""


@app.post("/admin/create", response_class=HTMLResponse)
async def admin_create(
    request: Request,
    target: str = Form(...),
    db: Session = Depends(get_db)
):
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

    full_url = f"{BASE_URL}/go/{slug}"

    return f"""
<html>
<body style="background:#0f2027;color:#fff;font-family:system-ui">
<div style="background:#fff;color:#000;border-radius:16px;padding:16px;margin:16px">
<h3>Link Created</h3>
<input value="{full_url}" style="width:100%;padding:12px" readonly>
</div>
<a href="/admin/panel" style="color:#fff;text-align:center;display:block">Back</a>
</body>
</html>
"""


# ================= USER FUNNEL =================
@app.get("/go/{slug}", response_class=HTMLResponse)
async def go(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return HTMLResponse("Invalid link", status_code=404)

    link.clicks += 1
    db.commit()

    return f"""
<html>
<body>
<p id="msg">Wait <b id="t">20</b> seconds...</p>

<div id="continueBox" style="display:none">
<a href="/redirect/{slug}">
<button>Continue</button>
</a>
</div>

<script>
let t = 20;
let i = setInterval(() => {{
  document.getElementById("t").innerText = t;
  if (t-- <= 0) {{
    clearInterval(i);
    document.getElementById("msg").innerText = "You may continue";
    document.getElementById("continueBox").style.display = "block";
  }}
}}, 1000);
</script>
</body>
</html>
"""


# ================= FINAL REDIRECT =================
@app.get("/redirect/{slug}")
async def redirect(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return RedirectResponse("/")

    link.completed += 1
    db.commit()
    return RedirectResponse(link.target)