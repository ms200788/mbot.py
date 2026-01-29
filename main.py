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
BASE_URL =os.getenv("BASE_URL",  "https://fast-link-2cmx.onrender.com") 

# ================= APP =================
app = FastAPI()
REQUEST_LOG = {}
ADMIN_COOKIE = "admin_session"

# ================= SECURITY HEADERS =================
from fastapi import Response

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)

    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    response.headers["Content-Security-Policy"] = (
        "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
    )

    return response


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
    response.set_cookie(
    key=ADMIN_COOKIE,
    value="true",
    max_age=86400,
    httponly=True,
    secure=True,
    samesite="Lax"
)
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
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Artificial Intelligence – A Complete Guide</title>

<style>
body {{
    background:#0f2027;
    color:#eaeaea;
    font-family:system-ui;
    margin:0;
}}
.card {{
    background:#ffffff;
    color:#000000;
    border-radius:16px;
    padding:20px;
    margin:16px;
}}
h1,h2,h3 {{
    color:#1c1c1c;
}}
p {{
    line-height:1.8;
    margin:14px 0;
    font-size:15px;
}}
.btn {{
    background:#ff4b2b;
    color:#fff;
    border:none;
    padding:14px;
    width:100%;
    border-radius:30px;
    font-size:16px;
}}
.timer {{
    text-align:center;
    font-size:16px;
    margin:20px 0;
}}
.ad {{
    margin:24px 0;
    text-align:center;
}}
.section {{
    margin-bottom:32px;
}}
.conclusion {{
    background:#f0f3ff;
    padding:20px;
    border-left:5px solid #4a63ff;
    border-radius:12px;
}}
</style>

<script>
let t = 20;
let timer = setInterval(() => {
    document.getElementById("t").innerText = t;
    if (t <= 0) {
        clearInterval(timer);
        document.getElementById("continueBox").style.display = "block";
        document.getElementById("timerText").innerText = "You can continue now";
    }
    t--;
}, 1000);
</script>
</head>

<body>

<div class="card">

<h1>Artificial Intelligence (AI) – A Simple and Complete Guide</h1>

<div class="timer">
<p id="timerText">Please wait <b id="t">20</b> seconds while content loads</p>
</div>

<div class="section">
<h2>What is Artificial Intelligence?</h2>
<p>
Artificial Intelligence, commonly known as <b>AI</b>, is a branch of computer science that focuses on
creating machines capable of performing tasks that normally require human intelligence.
These tasks include learning, reasoning, problem-solving, understanding language, and recognizing images.
</p>

<p>
AI is not science fiction anymore. It is already a part of our daily life. From unlocking your phone
with your face to getting movie recommendations online, AI works quietly in the background.
</p>
</div>

<div class="section">
<h2>How Does Artificial Intelligence Work?</h2>
<p>
AI systems work using three main components:
</p>

<ul>
<li><b>Data</b> – Large amounts of information used for learning</li>
<li><b>Algorithms</b> – Mathematical rules that help machines learn patterns</li>
<li><b>Computing Power</b> – Strong processors that handle complex calculations</li>
</ul>

<p>
Instead of giving a computer thousands of fixed rules, we train it using data.
For example, to teach a computer to recognize birds, we show it thousands of bird images.
Over time, it learns the patterns by itself.
</p>
</div>

<div class="section">
<h2>Main Areas of Artificial Intelligence</h2>

<h3>1. Machine Learning (ML)</h3>
<p>
Machine Learning allows computers to learn from data without being directly programmed.
It helps systems make predictions and decisions based on previous experiences.
</p>

<h3>2. Deep Learning (DL)</h3>
<p>
Deep Learning is a part of Machine Learning that uses neural networks inspired by the human brain.
It is especially useful for image recognition, speech recognition, and language translation.
</p>

<h3>3. Natural Language Processing (NLP)</h3>
<p>
NLP helps computers understand and generate human language.
Chatbots, voice assistants, and translation tools use NLP.
</p>

<h3>4. Computer Vision</h3>
<p>
Computer Vision allows machines to understand images and videos.
It is used in face recognition, medical imaging, and self-driving cars.
</p>
</div>

<div class="section">
<h2>Types of Artificial Intelligence</h2>

<h3>Based on Capability</h3>
<ul>
<li><b>Artificial Narrow Intelligence (ANI)</b> – Performs one specific task (this is the only type that exists today)</li>
<li><b>Artificial General Intelligence (AGI)</b> – A future concept where AI can think like humans</li>
<li><b>Artificial Superintelligence (ASI)</b> – A theoretical AI far more intelligent than humans</li>
</ul>

<h3>Based on Functionality</h3>
<ul>
<li><b>Reactive Machines</b> – Do not learn from past experiences</li>
<li><b>Limited Memory</b> – Learn from recent data and past interactions</li>
<li><b>Theory of Mind</b> – A future AI that may understand human emotions</li>
</ul>
</div>

<div class="section">
<h2>Common Myths About AI</h2>

<ul>
<li><b>Myth:</b> AI has emotions and feelings<br>
<b>Reality:</b> AI can simulate emotions but does not truly feel anything</li>

<li><b>Myth:</b> AI is always unbiased<br>
<b>Reality:</b> AI can reflect human bias if trained on biased data</li>

<li><b>Myth:</b> AI will replace all human jobs<br>
<b>Reality:</b> AI will mostly assist humans and create new job opportunities</li>
</ul>
</div>

<div class="section">
<h2>Benefits of Artificial Intelligence</h2>

<ul>
<li>Automates repetitive tasks</li>
<li>Reduces human errors</li>
<li>Works continuously without breaks</li>
<li>Processes large amounts of data quickly</li>
<li>Helps in scientific research and innovation</li>
</ul>
</div>

<div class="section">
<h2>Applications of AI in Real Life</h2>

<ul>
<li><b>Healthcare:</b> Disease detection and medical imaging</li>
<li><b>Education:</b> Personalized learning systems</li>
<li><b>Transportation:</b> Self-driving and navigation systems</li>
<li><b>Business:</b> Fraud detection and customer support</li>
<li><b>Entertainment:</b> Content recommendation and game development</li>
</ul>
</div>

<div class="section">
<h2>A Brief History of Artificial Intelligence</h2>
<p>
The idea of intelligent machines began in the 1950s.
The field developed slowly due to limited technology, but major breakthroughs occurred
after 2010 with better computing power and large datasets.
Today, AI is growing faster than ever.
</p>
</div>

<div class="section">
<h2>Generative AI and Modern AI Systems</h2>
<p>
Generative AI can create new content such as text, images, music, and code.
These systems learn from large datasets and generate original outputs based on instructions.
</p>

<p>
Modern AI models are becoming smarter and more versatile, helping humans in creative,
technical, and analytical tasks.
</p>
</div>

<div class="conclusion">
<h2>Conclusion</h2>
<p>
Artificial Intelligence is one of the most important technologies of the modern world.
It is transforming how we learn, work, communicate, and solve problems.
</p>

<p>
For students, understanding AI is no longer optional—it is essential.
AI does not replace human intelligence; instead, it enhances it.
The future belongs to those who know how to work <b>with</b> AI, not against it.
</p>

<p>
With responsible use and ethical development, artificial intelligence has the potential
to improve lives, advance knowledge, and create a smarter and more efficient world.
</p>
</div>

</div>

<!-- ================= CONTINUE (AFTER TIMER) ================= -->
<div id="continueBox" style="display:none; margin:16px;">
<a href="{BASE_URL}/redirect/{slug}">
<button class="btn">Continue</button>
</a>
</div>

</body>
</html>
"""

# ================= FINAL REDIRECT =================
@app.get("/redirect/{slug}")
async def final_redirect(slug: str, db=Depends(get_db)):
    link = db.query(Link).filter(Link.slug == slug).first()
    if not link:
        return RedirectResponse("/")
    link.completed += 1
    db.commit()
    return RedirectResponse(link.target)