import os
import time
import random
import string
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

# ================= CONFIG =================
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL", "https://example.com")

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
async def ad_page(slug: str, request: Request, db=Depends(get_db)):
    link = db.query(Link).filter(Link.slug == slug).first()
    if not link:
        return HTMLResponse("Invalid link", status_code=404)

    link.clicks += 1
    db.commit()

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Exclusive Psychological Insight</title>

<style>
body {{
    font-family: Arial, sans-serif;
    background: #ffffff;
    color: #222;
    line-height: 1.6;
    padding: 15px;
    max-width: 800px;
    margin: auto;
}}

h1, h2 {{
    color: #111;
}}

.timer {{
    background: #f5f5f5;
    padding: 12px;
    border-left: 5px solid #ff3d00;
    margin: 20px 0;
    font-size: 16px;
}}

.ad {{
    margin: 25px 0;
    text-align: center;
}}

#continue {{
    display: none;
    margin: 30px 0;
    text-align: center;
}}

.btn {{
    background: #ff3d00;
    color: #fff;
    border: none;
    padding: 14px 22px;
    font-size: 18px;
    border-radius: 5px;
    cursor: pointer;
}}

.btn:hover {{
    background: #e03500;
}}
</style>

<!-- ================= POPUNDER (PAGE 1 – 1x) ================= -->
<script type="text/javascript" src="https://plXXXXXXX.effectivegatecpm.com/XXXXXX/invoke.js"></script>

</head>
<body>

<h1>The Hidden Psychology of Attraction Most People Never Learn</h1>

<div class="timer">
    <p id="timerText">
        Please wait <b id="t">20</b> seconds while exclusive content loads
    </p>
</div>

<p>
Attraction is not accidental. Psychological triggers shape desire long before logic enters the picture.
People often believe attraction is about appearance, but studies repeatedly show emotional perception,
confidence, and behavioral timing matter far more.
</p>

<p>
Most relationship failures begin because people misunderstand how attraction actually forms.
</p>

<h2>Why Desire and Love Are Not the Same</h2>

<p>
Desire is fast, emotional, and instinct-driven. Love is slow, rational, and built over time.
</p>

<!-- ================= NATIVE BANNER ================= -->
<div class="ad">
<script async="async" data-cfasync="false"
src="https://plXXXXXXXX.effectivegatecpm.com/XXXXXXXX/invoke.js"></script>
<div id="container-XXXXXXXX"></div>
</div>

<h2>Confidence Signals the Brain Instantly</h2>

<p>
Confidence is emotional stability. Calm speech and controlled body language send powerful signals.
</p>

<!-- ================= BANNER 300x250 ================= -->
<div class="ad">
<script>
atOptions = {{
  'key' : 'XXXXXXXXXXXX',
  'format' : 'iframe',
  'height' : 250,
  'width' : 300,
  'params' : {{}}
}};
</script>
<script src="https://www.highperformanceformat.com/XXXXXXXXXXXX/invoke.js"></script>
</div>

<h2>Emotional vs Physical Intimacy</h2>

<p>
Healthy relationships balance emotional and physical connection.
</p>

<!-- ================= BANNER 320x50 ================= -->
<div class="ad">
<script>
atOptions = {{
  'key' : 'XXXXXXXXXXXX',
  'format' : 'iframe',
  'height' : 50,
  'width' : 320,
  'params' : {{}}
}};
</script>
<script src="https://www.highperformanceformat.com/XXXXXXXXXXXX/invoke.js"></script>
</div>

<h2>What Happens Next</h2>

<p>
The next page reveals deeper psychological patterns. Adults only.
</p>

<div id="continue">
    <a href="/step2/{slug}">
        <button class="btn">Continue</button>
    </a>
</div>

<!-- ================= TIMER SCRIPT ================= -->
<script>
let t = 20;
let timerInterval;

function startTimer() {{
    timerInterval = setInterval(() => {{
        document.getElementById("t").innerText = t;
        if (t <= 0) {{
            clearInterval(timerInterval);
            document.getElementById("timerText").innerText =
                "Scroll down and click Continue";
            document.getElementById("continue").style.display = "block";
        }}
        t--;
    }}, 1000);
}}

startTimer();

document.addEventListener("visibilitychange", function () {{
    if (document.hidden) {{
        clearInterval(timerInterval);
    }} else {{
        startTimer();
    }}
}});
</script>

</body>
</html>
"""


@app.get("/step2/{slug}", response_class=HTMLResponse)
async def step2(slug: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.slug == slug).first()
    if not link:
        return HTMLResponse("Invalid link", status_code=404)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Final Step</title>
        <style>
            body {{
                background:#111;
                color:#fff;
                font-family:system-ui;
                padding:20px;
            }}
            .btn {{
                background:#4caf50;
                color:#fff;
                padding:15px;
                width:100%;
                border-radius:30px;
                border:none;
                font-size:18px;
            }}
        </style>
        <script>
            setTimeout(() => {{
                document.getElementById("go").style.display = "block";
            }}, 7000);
        </script>
    </head>
    <body>

        <h2>Almost done</h2>
        <p>Please wait a few seconds…</p>

        <!-- POPUNDER / SMARTLINK CODE HERE -->

        <div id="go" style="display:none;">
            <a href="/redirect/{slug}">
                <button class="btn">Open Link</button>
            </a>
        </div>

    </body>
    </html>
    """
    return HTMLResponse(html)

# ================= FINAL REDIRECT =================
@app.get("/redirect/{slug}")
async def final_redirect(slug: str, db=Depends(get_db)):
    link = db.query(Link).filter(Link.slug == slug).first()
    if not link:
        return RedirectResponse("/")
    link.completed += 1
    db.commit()
    return RedirectResponse(link.target)