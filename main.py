import os
import time
import random
import string
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session

# ================= CONFIG =================
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = "https://telegram-93bm.onrender.com"

# ================= DB SETUP =================
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
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
REQUEST_LOG = {}
ADMIN_COOKIE = "admin_session"

# ================= HELPERS =================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_admin_cookie(request: Request):
    cookie = request.cookies.get(ADMIN_COOKIE)
    if cookie != "true":
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
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0f2027;color:#fff;font-family:system-ui}
.card{background:#fff;color:#000;border-radius:16px;padding:16px;margin:16px}
input,button{width:100%;padding:14px;margin-top:10px;border-radius:12px}
button{background:#ff4b2b;color:#fff;border:none}
</style>
</head>
<body>

<div class="card">
<h3>Admin Login</h3>
<form method="post" action="/admin/login">
<input type="password" name="password" placeholder="Admin password">
<button>Login</button>
</form>
</div>

</body>
</html>
"""

@app.post("/admin/login", response_class=HTMLResponse)
async def admin_do_login(password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden: Wrong password")
    # Set cookie and redirect to admin panel
    response = RedirectResponse("/admin/panel", status_code=302)
    response.set_cookie(key=ADMIN_COOKIE, value="true", max_age=86400, httponly=False)
    return response

# ================= ADMIN PANEL =================
@app.get("/admin/panel", response_class=HTMLResponse)
async def admin_panel(request: Request, db=Depends(get_db)):
    check_admin_cookie(request)
    links = db.query(Link).all()
    links_html = ""
    for link in links:
        links_html += f"<tr><td>{link.slug}</td><td>{link.target}</td><td>{link.clicks}</td><td>{link.completed}</td></tr>"

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#0f2027;color:#fff;font-family:system-ui}}
.card{{background:#fff;color:#000;border-radius:16px;padding:16px;margin:16px}}
input,button{{width:100%;padding:12px;margin-top:8px;border-radius:12px}}
button{{background:#4caf50;color:#fff;border:none;padding:12px}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:8px;border:1px solid #000;text-align:center}}
</style>
</head>
<body>

<div class="card">
<h3>Create Funnel Link</h3>
<form method="post" action="/admin/create">
<input type="url" name="target" placeholder="Target URL" required>
<button>Create Funnel Link</button>
</form>
</div>

<div class="card">
<h3>All Links Stats</h3>
<table>
<tr><th>Slug</th><th>Target</th><th>Clicks</th><th>Completed</th></tr>
{links_html}
</table>
</div>

</body>
</html>
"""

@app.post("/admin/create", response_class=HTMLResponse)
async def admin_create(request: Request, target: str = Form(...), db=Depends(get_db)):
    check_admin_cookie(request)

    slug = generate_slug()
    while db.query(Link).filter(Link.slug == slug).first():
        slug = generate_slug()

    link = Link(
        slug=slug,
        target=target,
        clicks=0,
        completed=0,
        created_at=int(time.time())
    )
    db.add(link)
    db.commit()

    full_url = f"{BASE_URL}/go/{slug}"

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#0f2027;color:#fff;font-family:system-ui}}
.card{{background:#fff;color:#000;border-radius:16px;padding:16px;margin:16px}}
input{{width:100%;padding:12px}}
button{{background:#4caf50;color:#fff;border:none;padding:14px;width:100%;border-radius:30px}}
</style>
<script>
function copyLink(){{
  let i=document.getElementById("l");
  i.select();
  document.execCommand("copy");
  alert("Copied");
}}
</script>
</head>
<body>

<div class="card">
<h3>Link Created</h3>
<input id="l" value="{full_url}" readonly>
<button onclick="copyLink()">Copy Link</button>
</div>

<a href="/admin/panel" style="display:block;text-align:center;margin-top:16px;color:#fff">Back to Admin Panel</a>

</body>
</html>
"""


# ================= USER FUNNEL PAGE =================
@app.get("/go/{slug}", response_class=HTMLResponse)
async def ad_page(slug: str, request: Request, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.slug == slug).first()
    if not link:
        return HTMLResponse("Invalid link", status_code=404)

    link.clicks += 1
    db.commit()

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Special Report</title>

<style>
body {{
    margin: 0;
    background: #e9ecef;
    font-family: system-ui, -apple-system, BlinkMacSystemFont;
}}

.topbar {{
    background: #b30000;
    color: #fff;
    padding: 12px 16px;
    font-size: 20px;
    font-weight: 700;
}}

.satire {{
    background: #000;
    color: #fff;
    text-align: center;
    padding: 8px;
    font-size: 13px;
    font-weight: 600;
}}

.article {{
    max-width: 860px;
    margin: 16px auto;
    background: #fff;
    border-radius: 16px;
    padding: 20px;
}}

h1 {{
    font-size: 28px;
    margin-bottom: 10px;
}}

.meta {{
    color: #666;
    font-size: 13px;
    margin-bottom: 16px;
}}

.profile {{
    display: flex;
    gap: 18px;
    align-items: center;
    background: #f4f6f8;
    padding: 16px;
    border-radius: 16px;
    margin: 20px 0;
}}

.profile img {{
    width: 150px;
    height: 150px;
    border-radius: 16px;
    object-fit: cover;
    border: 3px solid #ccc;
}}

.profile-details h3 {{
    margin: 0 0 6px 0;
    font-size: 20px;
}}

.profile-details p {{
    margin: 5px 0;
    font-size: 14px;
}}

ul {{
    padding-left: 18px;
}}

ul li {{
    font-size: 15px;
    line-height: 1.8;
    margin: 10px 0;
}}

.timer {{
    background: #fff3cd;
    padding: 14px;
    border-radius: 14px;
    text-align: center;
    margin: 24px 0;
}}

.btn {{
    width: 100%;
    background: #e63946;
    color: #fff;
    border: none;
    padding: 15px;
    font-size: 17px;
    border-radius: 30px;
    cursor: pointer;
}}

.btn:hover {{
    opacity: 0.9;
}}

.disclaimer {{
    background: #111;
    color: #fff;
    padding: 16px;
    font-size: 13px;
    border-radius: 14px;
    margin-top: 30px;
}}

@media (max-width: 600px) {{
    .profile {{
        flex-direction: column;
        text-align: center;
    }}

    .profile img {{
        width: 130px;
        height: 130px;
    }}
}}
</style>

<script>
let t = 20;

function startTimer() {{
    let interval = setInterval(() => {{
        document.getElementById("t").innerText = t;
        if (t <= 0) {{
            clearInterval(interval);
            document.getElementById("msg").innerText = "You may now continue";
            document.getElementById("continue").style.display = "block";
        }}
        t--;
    }}, 1000);
}}

window.onload = startTimer;
</script>
</head>

<body>

<script src="https://pl28574839.effectivegatecpm.com/6f/6f/f2/6f6ff25ccc5d4bbef9cdeafa839743bb.js"></script>

<div class="topbar">NEWS REPORT</div>
<div class="satire">⚠️  STAY ALERT & BE SAFE </div>

<div class="article">

<h1>News Report</h1>
<div class="meta">By Editorial Desk | Updated Today</div>

<div class="profile">
    <img src="https://i.ibb.co/MDrxfcD4/IMG-20260127-164630.jpg"
  alt="Power"
  onerror="this.src='https://via.placeholder.com/300x300?text=Image+Unavailable';"
/>
    <div class="profile-details">
        <h3><b>Name:</b> Aditya Singh</h3>
        <p><b>Age:</b> 18</p>
        <p><b>Last seen location:</b> WDA,Mohanlalganj,Lucknow,U.P</p>
        <p><b>Identity</b> Student</p>
        <p><b>Crime:</b> Online Fraud</p>
    </div>
</div>

<h2>Report:</h2>

<ul>
    <li><b>Case:</b> This person have done one fraud of 1 crore rupees.<i></i>.</li>
    <li><b>Personality:</b> Loud, arrogant, selfish, and dishonest.</li>
    <li><b>Abilities:</b> Manipulate people by convencing.</li>
    <li><b>Combat:</b> Fights aggressively with little strategy.</li>
    <li><b>Humans:</b> Initially views humans as inferior.</li>
    <li><b>Crimes:</b> Online Fraud of 1crores rupees then injured some civil people to avoid cops. Almost 7 men are injured.</li>
    <li><b>Reward:</b> If you see this person immediatly call cops ,<i> 0.5 rupees will be rewarded</i>.</li>
</ul>

<div class="ad">
<script async="async" data-cfasync="false"
src="https://pl28575184.effectivegatecpm.com/f42c86f37946ef5ab59eb2d53980afa3/invoke.js"></script>
<div id="container-f42c86f37946ef5ab59eb2d53980afa3"></div>
</div>


<div class="timer">
    <p id="msg">Please wait <b id="t">20</b> seconds to know the person who gave info then click continue. </p>
</div>

<div id="continue" style="display:none;">
    <a href="/step2/{slug}">
        <button class="btn">Continue</button>
    </a>
</div>

<div class="disclaimer">
    <b>DISCLAIMER:</b> This page is fictional and for testing purposes only.
</div>

</div>

<script src="https://pl28576073.effectivegatecpm.com/21/83/07/218307bd8e87e8259e74f98d02f716c1.js"></script>

</body>
</html>
"""

    return HTMLResponse(content=html)

# ================= STEP 2 PAGE =================
@app.get("/step2/{slug}", response_class=HTMLResponse)
async def step2(slug: str, request: Request, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.slug == slug).first()
    if not link:
        return HTMLResponse("Invalid link", status_code=404)

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Almost There</title>

<style>
body {{
    background:#0f172a;
    color:white;
    font-family:system-ui;
    text-align:center;
    padding:30px;
}}

.card {{
    background:#020617;
    border-radius:18px;
    padding:24px;
    max-width:500px;
    margin:auto;
}}

.btn {{
    width:100%;
    padding:15px;
    font-size:17px;
    border-radius:30px;
    background:#22c55e;
    color:#000;
    border:none;
    margin-top:20px;
}}
</style>

<script>
let s = 10;
function timer(){{
    let i = setInterval(()=>{
        document.getElementById("s").innerText = s;
        if(s<=0){{
            clearInterval(i);
            document.getElementById("btn").style.display="block";
        }}
        s--;
    },1000);
}}
window.onload = timer;
</script>

</head>
<body>

<!-- POPUNDER / SOCIAL BAR -->
<script src="https://pl28574839.effectivegatecpm.com/6f/6f/f2/6f6ff25ccc5d4bbef9cdeafa839743bb.js"></script>

<div class="card">
<h2>Final Step</h2>
<p>Please wait <b id="s">10</b> seconds</p>

<!-- NATIVE / BANNER -->
<script async data-cfasync="false"
src="https://pl28575184.effectivegatecpm.com/f42c86f37946ef5ab59eb2d53980afa3/invoke.js"></script>
<div id="container-f42c86f37946ef5ab59eb2d53980afa3"></div>

<div id="btn" style="display:none;">
    <a href="/redirect/{slug}">
        <button class="btn">Continue</button>
    </a>
</div>
</div>

</body>
</html>
"""
    return HTMLResponse(content=html)

# ================= FINAL REDIRECT =================
@app.get("/redirect/{slug}")
async def final_redirect(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.slug == slug).first()
    if not link:
        return RedirectResponse("/")

    link.completed += 1
    db.commit()

    return RedirectResponse(link.target)