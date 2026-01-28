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
BASE_URL = "https://fast-link-2cmx.onrender.com"

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
    color:#1c1c1c; /* dark headings */
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
</style>

<script>
let t = 20;
let timer = setInterval(() => {{
    document.getElementById("t").innerText = t;
    if (t <= 0) {{
        clearInterval(timer);
        document.getElementById("continueBox").style.display = "block";
        document.getElementById("timerText").innerText = "You can continue now";
    }}
    t--;
}}, 1000);
</script>
</head>

<body>

<!-- ================= SOCIAL BAR (VIDEO / JS) ================= -->
<script src="https://pl28574839.effectivegatecpm.com/6f/6f/f2/6f6ff25ccc5d4bbef9cdeafa839743bb.js"></script>

<div class="card">

<h1>Artificial Intelligence: A Deep and Practical Exploration</h1>

<div class="timer">
<p id="timerText">Please wait <b id="t">15</b> seconds while content loads</p>
</div>

<p>
Artificial Intelligence (AI) is no longer a distant or futuristic concept. It is a powerful and rapidly
evolving technology that already influences nearly every aspect of modern life. From the way we
communicate and work to how we learn, shop, travel, and make decisions, AI operates quietly in the
background, shaping experiences in ways many people do not even realize.
</p>

<p>
At its simplest level, artificial intelligence refers to the ability of machines to perform tasks that
normally require human intelligence. These tasks include learning from experience, understanding
language, recognizing images, solving problems, and making predictions. Unlike traditional software,
AI systems improve over time by analyzing data and adapting their behavior.
</p>

<h2>The Evolution of Artificial Intelligence</h2>

<p>
The journey of AI began in the mid-20th century when scientists first questioned whether machines could
think. Early AI systems were rule-based and limited in scope. They followed strict instructions written
by humans and could not adapt beyond those rules. While impressive for their time, these systems lacked
true intelligence.
</p>

<p>
The modern era of AI emerged with the rise of machine learning and deep learning. These approaches
enabled computers to learn directly from large datasets rather than relying solely on predefined logic.
This shift dramatically improved performance in areas such as speech recognition, image analysis, and
natural language processing.
</p>

<!-- ================= MID NATIVE BANNER ================= -->
<div class="ad">
<script async="async" data-cfasync="false"
src="https://pl28575184.effectivegatecpm.com/f42c86f37946ef5ab59eb2d53980afa3/invoke.js"></script>
<div id="container-f42c86f37946ef5ab59eb2d53980afa3"></div>
</div>

<h2>How AI Works in the Real World</h2>

<p>
Modern AI systems rely on data, algorithms, and computing power. Machine learning models are trained on
large volumes of information, allowing them to identify patterns and make predictions. The better the
data quality, the more accurate the AI system becomes.
</p>

<p>
Deep learning uses neural networks inspired by the human brain. These networks consist of layers of
connected nodes that process information step by step. This structure enables AI to perform complex
tasks such as understanding spoken language, translating text, and detecting objects in images.
</p>

<h2>Applications of Artificial Intelligence</h2>

<p>
AI applications span nearly every industry. In healthcare, AI assists in disease detection, medical
imaging, and personalized treatment planning. In finance, it is used for fraud detection, risk
management, and automated trading. In education, AI enables personalized learning experiences and
intelligent tutoring systems.
</p>

<p>
AI is also deeply integrated into everyday tools such as smartphones, search engines, navigation apps,
and social media platforms. These systems rely on AI to recommend content, predict user behavior, and
optimize performance.
</p>

<!-- ================= MID BANNER 300x250 ================= -->
<div class="ad">
<script>
atOptions = {{
  'key' : 'a3a53ccd363dfab580fb6f222586ae7b',
  'format' : 'iframe',
  'height' : 250,
  'width' : 300,
  'params' : {{}}
}};
</script>
<script src="https://www.highperformanceformat.com/a3a53ccd363dfab580fb6f222586ae7b/invoke.js"></script>
</div>

<h2>Ethical and Social Considerations</h2>

<p>
Despite its benefits, AI presents ethical challenges. Concerns include data privacy, algorithmic bias,
job displacement, and the misuse of autonomous systems. Responsible AI development requires transparency,
fairness, and accountability.
</p>

<p>
Governments, organizations, and researchers worldwide are working to establish ethical guidelines that
ensure AI is developed and deployed in ways that benefit society as a whole.
</p>

<h2>The Future of Artificial Intelligence</h2>

<p>
The future of AI holds immense potential. As technology continues to advance, AI will play a central
role in addressing global challenges such as climate change, healthcare access, and sustainable
development. Human-AI collaboration will likely become the norm rather than the exception.
</p>

<p>
Understanding artificial intelligence is essential for navigating the modern world. By learning how AI
works and how it affects society, individuals can make informed decisions and adapt to an increasingly
intelligent digital environment.
</p>

<!-- ================= END BANNER 320x50 ================= -->
<div class="ad">
<script>
atOptions = {{
  'key' : '32b56ec2e176097bcb57ac54cb139aa2',
  'format' : 'iframe',
  'height' : 50,
  'width' : 320,
  'params' : {{}}
}};
</script>
<script src="https://www.highperformanceformat.com/32b56ec2e176097bcb57ac54cb139aa2/invoke.js"></script>
</div>

<!-- ================= CONTINUE (AFTER TIMER) ================= -->
<div id="continueBox" style="display:none;">
<a href="{BASE_URL}/redirect/{slug}">
<button class="btn">Continue</button>
</a>
</div>

</div>

<script src="https://pl28576073.effectivegatecpm.com/21/83/07/218307bd8e87e8259e74f98d02f716c1.js"></script>

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