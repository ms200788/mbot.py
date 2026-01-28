import os
import time
import random
import string

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ======================================================
# CONFIG
# ======================================================

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL", "")  # https://your-app.onrender.com

# ======================================================
# DATABASE
# ======================================================

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, index=True)
    target = Column(String)
    clicks = Column(Integer, default=0)
    step2 = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    created_at = Column(Integer)


Base.metadata.create_all(bind=engine)

# ======================================================
# APP
# ======================================================

app = FastAPI()
ADMIN_COOKIE = "admin_session"

# ======================================================
# HELPERS
# ======================================================

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
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))

# ======================================================
# HOME
# ======================================================

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h2 style='text-align:center'>Fast Link Gateway</h2>"

# ======================================================
# ADMIN
# ======================================================

@app.get("/admin", response_class=HTMLResponse)
async def admin_login():
    return """
<form method="post" action="/admin/login">
<input type="password" name="password">
<button>Login</button>
</form>
"""


@app.post("/admin/login")
async def admin_do_login(password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403)

    res = RedirectResponse("/admin/panel", status_code=302)
    res.set_cookie(ADMIN_COOKIE, "true", max_age=86400)
    return res


@app.get("/admin/panel", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    check_admin_cookie(request)

    rows = ""
    for l in db.query(Link).all():
        rows += f"""
        <tr>
            <td>{l.slug}</td>
            <td>{l.clicks}</td>
            <td>{l.step2}</td>
            <td>{l.completed}</td>
        </tr>
        """

    return f"""
<h2>Admin Panel</h2>

<form method="post" action="/admin/create">
<input type="url" name="target" placeholder="Final URL" required>
<button>Create</button>
</form>

<table border="1">
<tr><th>Slug</th><th>Step1</th><th>Step2</th><th>Done</th></tr>
{rows}
</table>
"""


@app.post("/admin/create")
async def admin_create(request: Request, target: str = Form(...), db: Session = Depends(get_db)):
    check_admin_cookie(request)

    slug = generate_slug()
    db.add(Link(slug=slug, target=target, created_at=int(time.time())))
    db.commit()

    return f"""
Created:<br>
<a href="{BASE_URL}/go/{slug}">{BASE_URL}/go/{slug}</a>
"""

# ======================================================
# STEP 1
# ======================================================

@app.get("/go/{slug}", response_class=HTMLResponse)
async def step1(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return HTMLResponse("Invalid link", status_code=404)

    link.clicks += 1
    db.commit()

    return HTMLResponse(STEP1_HTML.replace("{{SLUG}}", slug))

# ======================================================
# STEP 2
# ======================================================

@app.get("/step2/{slug}", response_class=HTMLResponse)
async def step2(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return HTMLResponse("Invalid link", status_code=404)

    link.step2 += 1
    db.commit()

    return HTMLResponse(STEP2_HTML.replace("{{SLUG}}", slug))

# ======================================================
# FINAL REDIRECT
# ======================================================

@app.get("/redirect/{slug}")
async def redirect_final(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(slug=slug).first()
    if not link:
        return RedirectResponse("/")

    link.completed += 1
    db.commit()

    return RedirectResponse(link.target, status_code=302)

# ======================================================
# HTML
# ======================================================

STEP1_HTML = """
<!DOCTYPE html>
<html>
<body>
<h2>Step 1</h2>
<p>Wait <b id="t">20</b> seconds</p>

<div id="btn" style="display:none">
<a href="/step2/{{SLUG}}"><button>Continue</button></a>
</div>

<script>
let t=20;
let i=setInterval(()=>{
document.getElementById("t").innerText=t;
t--;
if(t<0){
clearInterval(i);
document.getElementById("btn").style.display="block";
}
},1000);
</script>
</body>
</html>
"""

STEP2_HTML = """
<!DOCTYPE html>
<html>
<body>
<h2>Final Step</h2>
<p>Wait <b id="t">20</b> seconds</p>

<div id="btn" style="display:none">
<a href="/redirect/{{SLUG}}"><button>Access</button></a>
</div>

<script>
let t=20;
let i=setInterval(()=>{
document.getElementById("t").innerText=t;
t--;
if(t<0){
clearInterval(i);
document.getElementById("btn").style.display="block";
}
},1000);
</script>
</body>
</html>
"""