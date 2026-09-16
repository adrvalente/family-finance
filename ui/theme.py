from __future__ import annotations
import base64
from pathlib import Path
import streamlit as st

COLORS = {
    "Primary": "#0B4F9C",
    "Success": "#159A78",
    "Warning": "#E6A23C",
    "Danger": "#D9534F",
    "Info": "#2798C7",
    "Background": "#F5F8FB",
    "Surface": "#FFFFFF",
    "Text": "#17324D",
    "Muted": "#6B7C8F",
    "Border": "#DDE6EE",
    "Teal": "#0E8F84",
    "Green": "#22A879",
}

APP_VERSION = "3.3.1"

def _asset_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / filename

def _img_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"

def logo_uri() -> str:
    path = _asset_path("family_finance_logo.png")
    return _img_data_uri(path) if path.exists() else ""

def apply_family_finance_theme():
    st.markdown(f'''
    <style>
    :root {{
      --ff-primary:{COLORS["Primary"]};
      --ff-success:{COLORS["Success"]};
      --ff-warning:{COLORS["Warning"]};
      --ff-danger:{COLORS["Danger"]};
      --ff-info:{COLORS["Info"]};
      --ff-bg:{COLORS["Background"]};
      --ff-surface:{COLORS["Surface"]};
      --ff-text:{COLORS["Text"]};
      --ff-muted:{COLORS["Muted"]};
      --ff-border:{COLORS["Border"]};
      --ff-teal:{COLORS["Teal"]};
      --ff-green:{COLORS["Green"]};
    }}

    html, body, [class*="css"] {{
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    /* V3.3.2 - manter controlos nativos do Streamlit */
    header[data-testid="stHeader"] {{
      background: rgba(245,248,251,.96) !important;
      border-bottom: 1px solid rgba(221,230,238,.82) !important;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
    }}

    [data-testid="stToolbar"],
    [data-testid="stHeaderActionElements"],
    [data-testid="stSidebarCollapsedControl"] {{
      display: flex !important;
      visibility: visible !important;
      opacity: 1 !important;
    }}

    [data-testid="stSidebarCollapsedControl"] {{
      z-index: 1000000 !important;
    }}

    button[kind="header"],
    button[data-testid="stBaseButton-header"],
    button[data-testid="baseButton-header"] {{
      visibility: visible !important;
      opacity: 1 !important;
    }}

    [data-testid="stDecoration"] {{
      display: none !important;
    }}

    .stApp {{
      background:
        radial-gradient(circle at 92% 0%, rgba(21,154,120,.055), transparent 26rem),
        radial-gradient(circle at 14% 0%, rgba(11,79,156,.055), transparent 30rem),
        var(--ff-bg);
      color:var(--ff-text);
    }}

    [data-testid="stMainBlockContainer"] {{
      max-width:1450px;
      padding-top:1.15rem;
      padding-bottom:3rem;
    }}

    h1,h2,h3,h4 {{
      color:var(--ff-text);
      letter-spacing:-0.025em;
    }}
    h1 {{font-size:clamp(2rem,3vw,2.8rem)!important;line-height:1.1!important;}}
    h2 {{font-size:1.55rem!important;}}
    h3 {{font-size:1.22rem!important;}}

    p,label,[data-testid="stCaptionContainer"] {{color:var(--ff-muted);}}

    [data-testid="stSidebar"] {{
      background:linear-gradient(180deg,#0A4F96 0%,#087D87 64%,#0A9A82 100%);
      border-right:0!important;
    }}
    [data-testid="stSidebar"] * {{color:rgba(255,255,255,.96);}}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
      color:rgba(255,255,255,.76)!important;
    }}
    [data-testid="stSidebar"] hr {{border-color:rgba(255,255,255,.18)!important;}}

    [data-testid="stSidebar"] [role="radiogroup"] label {{
      padding:.46rem .55rem;
      border-radius:10px;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
      background:rgba(255,255,255,.09);
    }}

    .ff-sidebar-brand {{
      text-align:center;
      padding:.1rem .35rem .95rem;
    }}
    .ff-sidebar-brand img {{
      display:block;
      width:185px;
      max-width:92%;
      margin:0 auto -.15rem;
      object-fit:contain;
      filter:drop-shadow(0 7px 16px rgba(0,0,0,.14)) brightness(1.10) saturate(1.06);
    }}
    .ff-sidebar-name {{
      margin-top:0;
      color:#fff;
      font-size:1.25rem;
      font-weight:800;
    }}
    .ff-sidebar-tagline {{
      margin:.18rem auto 0;
      max-width:180px;
      color:rgba(255,255,255,.84);
      font-size:.77rem;
      line-height:1.25;
    }}
    .ff-sidebar-version {{
      margin-top:.58rem;
      font-size:.67rem;
      letter-spacing:.10em;
      text-transform:uppercase;
      color:rgba(255,255,255,.62);
    }}

    .stButton>button,.stFormSubmitButton>button,.stDownloadButton>button {{
      border-radius:10px;
      min-height:2.65rem;
      font-weight:700;
      border:1px solid var(--ff-primary);
    }}
    .stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"] {{
      background:linear-gradient(135deg,var(--ff-primary),#0B74B7);
      color:white;
      border:0;
    }}

    [data-testid="stMetric"] {{
      background:var(--ff-surface);
      border:1px solid var(--ff-border);
      border-radius:14px;
      box-shadow:0 8px 24px rgba(23,50,77,.065);
      padding:.9rem 1rem;
    }}
    [data-testid="stMetricLabel"] {{
      color:var(--ff-muted);
      font-size:.82rem!important;
      font-weight:650;
    }}
    [data-testid="stMetricValue"] {{
      color:var(--ff-text);
      font-size:clamp(1.3rem,2vw,1.8rem)!important;
      font-weight:800;
      line-height:1.15!important;
      white-space:normal!important;
      overflow:visible!important;
      text-overflow:clip!important;
    }}

    .ff-score-card {{
      display:flex;
      align-items:flex-start;
      gap:.78rem;
      min-height:128px;
      background:var(--ff-surface);
      border:1px solid var(--ff-border);
      border-radius:14px;
      padding:1rem;
      box-shadow:0 8px 24px rgba(23,50,77,.065);
    }}
    .ff-score-icon {{
      width:42px;height:42px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      flex:0 0 42px;font-size:1.2rem;background:#EAF3FB;
    }}
    .ff-score-label {{color:var(--ff-muted);font-size:.80rem;font-weight:700;}}
    .ff-score-value {{
      color:var(--ff-text);
      font-size:1.55rem;
      line-height:1.05;
      font-weight:850;
      margin-top:.25rem;
    }}
    .ff-score-note {{color:var(--ff-muted);font-size:.76rem;line-height:1.25;margin-top:.38rem;}}
    .ff-score-card.warning .ff-score-icon {{background:#FFF3D8;}}
    .ff-score-card.warning .ff-score-value {{color:#D98B00;}}
    .ff-score-card.success .ff-score-icon {{background:#E5F7F1;}}

    .ff-section-subtitle {{
      color:var(--ff-muted);
      margin-top:-.55rem;
      margin-bottom:1rem;
      font-size:.94rem;
    }}

    .ff-component-card {{
      min-height:145px;
      background:var(--ff-surface);
      border:1px solid var(--ff-border);
      border-radius:14px;
      padding:.95rem 1rem;
      box-shadow:0 8px 24px rgba(23,50,77,.065);
    }}
    .ff-component-title {{
      color:var(--ff-muted);
      font-size:.78rem;
      font-weight:700;
      min-height:2.1rem;
    }}
    .ff-component-value {{
      color:var(--ff-text);
      font-size:1.45rem;
      font-weight:850;
      margin:.18rem 0 .55rem;
    }}
    .ff-mini-track {{
      width:100%;height:8px;background:#E7EEF5;border-radius:999px;overflow:hidden;
    }}
    .ff-mini-fill {{height:100%;border-radius:inherit;}}
    .ff-component-meta {{
      display:flex;justify-content:space-between;gap:.5rem;
      color:var(--ff-muted);font-size:.72rem;margin-top:.55rem;
    }}

    [data-testid="stAlert"] {{border-radius:12px;}}
    [data-testid="stProgress"]>div>div {{
      background:linear-gradient(90deg,#188FE8,var(--ff-green));
    }}
    [data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {{
      background:#fff!important;
      border:1px solid var(--ff-border)!important;
      border-radius:14px!important;
      padding:.75rem!important;
      box-shadow:0 8px 24px rgba(23,50,77,.055)!important;
    }}
    </style>
    ''', unsafe_allow_html=True)


def render_brand_header(title="Family Finance", subtitle="As finanças da família, num só lugar."):
    uri = logo_uri()
    img = (
        f'<img src="{uri}" alt="Family Finance" '
        f'style="width:85px;height:85px;object-fit:contain;'
        f'filter:drop-shadow(0 6px 14px rgba(23,50,77,.10));">'
        if uri else ""
    )

    st.markdown(
        f"""
        <div style="
            display:flex;
            align-items:center;
            gap:1rem;
            margin:.15rem 0 1.25rem;
        ">
            {img}
            <div>
                <div style="
                    font-size:2rem;
                    font-weight:800;
                    color:#17324D;
                    line-height:1.05;
                    letter-spacing:-0.025em;
                ">
                    {title}
                </div>
                <div style="
                    margin-top:.35rem;
                    font-size:.95rem;
                    color:#6B7C8F;
                ">
                    {subtitle}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_sidebar_brand():
    uri = logo_uri()
    img = f'<img src="{uri}" alt="Family Finance">' if uri else ""
    st.markdown(
        f'''
        <div class="ff-sidebar-brand">
          {img}
          <div class="ff-sidebar-name">Family Finance</div>
          <div class="ff-sidebar-tagline">As finanças da família,<br>num só lugar.</div>
          <div class="ff-sidebar-version">Family Finance V{APP_VERSION}</div>
        </div>
        ''',
        unsafe_allow_html=True
    )

def score_card(label, value, icon, note="", tone="info"):
    st.markdown(
        f'''
        <div class="ff-score-card {tone}">
          <div class="ff-score-icon">{icon}</div>
          <div>
            <div class="ff-score-label">{label}</div>
            <div class="ff-score-value">{value}</div>
            <div class="ff-score-note">{note}</div>
          </div>
        </div>
        ''',
        unsafe_allow_html=True
    )

def component_card(label, score, weight, color):
    score = max(0.0, min(100.0, float(score)))
    st.markdown(
        f'''
        <div class="ff-component-card">
          <div class="ff-component-title">{label}</div>
          <div class="ff-component-value">{score:.0f}/100</div>
          <div class="ff-mini-track">
            <div class="ff-mini-fill" style="width:{score:.0f}%;background:{color};"></div>
          </div>
          <div class="ff-component-meta">
            <span>{score:.0f}%</span>
            <span>Peso: {int(weight)}%</span>
          </div>
        </div>
        ''',
        unsafe_allow_html=True
    )
