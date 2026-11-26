import html
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from anomaly.detector import load_model, model_warnings
from anomaly.features import to_ts
from anomaly.rules import is_blank
from app import auth, db, portal, present, service
from app.search import filter_items
from app.seed_demo import ensure_default_users, seed
from config import DB_PATH, MODEL_PATH

BRAND = "#5258CF"
BRAND_SOFT = "#F4F5FD"
BRAND_BORDER = "#E0E2F7"
PAGE_BG = "#F3F4F9"
PANEL = "#FAFBFE"
FIELD = "#F8F9FD"
BORDER = "#E8EBF3"
TEXT = "#1E293B"
TEXT_SOFT = "#4B5470"
MUTED = "#8E96AA"
SIDEBAR_WIDTH = "clamp(250px, 24.5vw, 400px)"

PAGE_ENTRY = "Nhập và chấm điểm"
PAGE_LIST = "Danh sách cảnh báo"
PAGE_LOG = "Nhật ký"
PAGE_MODEL = "Mô hình và dữ liệu"
PAGES = [PAGE_ENTRY, PAGE_LIST, PAGE_LOG, PAGE_MODEL]

ICONS = {
    "Nhập và chấm điểm": '<path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.5L19 7.5V19a2 2 0 01-2 2z"/>',
    "Danh sách cảnh báo": '<path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>',
    "Nhật ký": '<path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>',
    "Mô hình và dữ liệu": '<path d="M4 7v10c0 2 1.5 3 3.5 3h9c2 0 3.5-1 3.5-3V7c0-2-1.5-3-3.5-3h-9C5.5 4 4 5 4 7zM9 4v16"/>',
}

CLASS_LABELS = present.CLASS_LABELS

STATUS_STYLE = {
    "bình thường": ("#E3F7EF", "#127A55"),
    "bất thường": ("#FDE7E9", "#B3263A"),
    "thiếu thông tin": ("#FFF4D6", "#8A5A00"),
    "trùng lặp": ("#FFF4D6", "#8A5A00"),
    "chờ xử lý": ("#FFF4D6", "#8A5A00"),
    "đang xử lý": (BRAND_SOFT, BRAND),
    "đã xử lý": ("#E3F7EF", "#127A55"),
}
NEUTRAL_STYLE = (BRAND_SOFT, BRAND)
PENDING_STYLE = ("#F0F1F7", MUTED)

CAL_ICON = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
            "fill='none' stroke='%238E96AA' stroke-width='2' stroke-linecap='round'%3E"
            "%3Crect x='3' y='4' width='18' height='18' rx='2'/%3E%3Cpath d='M16 2v4M8 2v4M3 10h18'/%3E"
            "%3C/svg%3E\")")
USER_ICON = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
             "fill='none' stroke='%238E96AA' stroke-width='2' stroke-linecap='round'%3E"
             "%3Ccircle cx='12' cy='8' r='4'/%3E%3Cpath d='M4 21c0-4 4-6 8-6s8 2 8 6'/%3E"
             "%3C/svg%3E\")")

CSS_TEMPLATE = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

.stApp, .stApp p, .stApp label, .stApp span, .stApp input, .stApp button, .stApp textarea, .stApp td {
  font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .page-head h2, .brand-title, .card h4 {
  font-family: 'Plus Jakarta Sans', system-ui, sans-serif !important; letter-spacing: -.02em;
}

.stApp { background: __PAGE_BG__; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
#MainMenu, footer { visibility: hidden; }

button[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] { display: none !important; }

[data-testid="stSidebar"] {
  width: __SIDEBAR_WIDTH__ !important; min-width: __SIDEBAR_WIDTH__ !important; max-width: __SIDEBAR_WIDTH__ !important;
  transform: none !important; transition: none !important; margin-left: 0 !important;
  background: #FFFFFF; border-right: 1px solid __BORDER__;
}
[data-testid="stSidebar"][aria-expanded="false"] { transform: none !important; margin-left: 0 !important; }
[data-testid="stSidebarHeader"] { display: none !important; }
[data-testid="stSidebarUserContent"] { padding: 1.25rem 1.1rem 1.5rem 1.1rem !important; }

[data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow-x: hidden; }
.block-container {
  background: #FFFFFF; border-radius: 28px; padding: 1.5rem 2rem 2rem 2rem;
  margin: .75rem .75rem .75rem .5rem; max-width: none !important; width: auto;
  box-shadow: 0 25px 70px rgba(40, 46, 110, .07); border: 1px solid #F0F1F7;
}
.block-container [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 1rem; }
.block-container [data-testid="stHorizontalBlock"] > div[data-testid="column"] { min-width: 0; }

h1, h2, h3, h4 { color: __TEXT__; font-weight: 700; letter-spacing: 0; }
p, label, span { color: __TEXT__; }

.brand { display: flex; gap: 12px; align-items: center; margin: 0 0 1.5rem 0; }
.brand-mark { width: 42px; height: 42px; border-radius: 14px; background: __BRAND_SOFT__;
  color: __BRAND__; border: 1px solid __BRAND_BORDER__; display: flex; align-items: center; justify-content: center; }
.brand-title { font-weight: 700; font-size: 1.05rem; color: __TEXT__; line-height: 1.2; }
.brand-sub { font-size: .72rem; color: __MUTED__; }

.st-key-newbtn button {
  width: 100%; justify-content: space-between; background: __BRAND_SOFT__; color: __TEXT__;
  border: 1px solid __BRAND_BORDER__; border-radius: 22px; padding: .7rem 1rem; font-weight: 700; box-shadow: none;
}
.st-key-newbtn button:hover { background: #EDEEFA; border-color: __BRAND_BORDER__; color: __TEXT__; }
.st-key-newbtn button::after {
  content: "+"; width: 32px; height: 32px; border-radius: 50%; background: __BRAND__; color: #FFFFFF;
  display: inline-flex; align-items: center; justify-content: center; font-size: 1.2rem; font-weight: 700;
  box-shadow: 0 6px 14px -4px rgba(82, 88, 207, .5);
}

[class*="st-key-navrow_"] { border-radius: 16px; margin: 2px 0; }
[class*="st-key-navrow_"][class*="_on"] { background: __BRAND_SOFT__; }
[class*="st-key-navrow_"] [data-testid="stHorizontalBlock"] { align-items: center; gap: .3rem; }
[class*="st-key-navrow_"] button {
  background: transparent; border: none; box-shadow: none; color: __TEXT_SOFT__;
  font-weight: 600; padding: .65rem .5rem; font-size: .95rem;
  justify-content: flex-start !important; text-align: left !important;
}
[class*="st-key-navrow_"] button > div { justify-content: flex-start !important; width: 100%; }
[class*="st-key-navrow_"] button p { text-align: left !important; width: 100%; margin: 0; }
[class*="st-key-navrow_"] button:hover { color: __BRAND__; background: transparent; }
[class*="st-key-navrow_"][class*="_on"] button { color: __BRAND__; font-weight: 700; }

.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin: .75rem 0 1.25rem; }
.page-head h2 { margin: 0; font-size: 1.5rem; }
.sub { color: __MUTED__; font-size: .88rem; margin: 4px 0 0 0; }
.pill { background: #FFFFFF; color: __TEXT_SOFT__; padding: 7px 14px; border-radius: 999px;
  font-size: .82rem; font-weight: 600; border: 1px solid __BORDER__; white-space: nowrap; }
.pill::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: __BRAND__; margin-right: 8px; vertical-align: middle; }

div[data-testid="stForm"] {
  background: __PANEL__; border: 1px solid __BORDER__; border-radius: 28px; padding: 1.5rem 1.5rem 1.25rem;
}
[class*="st-key-box_"] {
  background: #FFFFFF; border: 1px solid __BORDER__; border-radius: 16px; padding: .8rem .9rem .9rem;
  box-shadow: 0 1px 2px rgba(31, 35, 64, .04);
}
[class*="st-key-box_"] div[data-baseweb="input"],
[class*="st-key-box_"] div[data-baseweb="select"] > div {
  background: __FIELD__ !important; border: 1px solid __BORDER__ !important; border-radius: 10px !important;
  min-height: 38px; position: relative;
}
[class*="st-key-box_"] div[data-baseweb="input"]:focus-within,
[class*="st-key-box_"] div[data-baseweb="select"] > div:focus-within {
  border-color: __BRAND__ !important; box-shadow: 0 0 0 3px __BRAND_SOFT__;
}
[class*="st-key-box_"] input { font-size: .85rem; font-weight: 600; color: __TEXT__; }
[class*="st-key-box_f_total"] input, [class*="st-key-box_f_base"] input { text-align: right; }

[class*="st-key-box_f_birth"] div[data-baseweb="input"]::after {
  content: ""; position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
  width: 16px; height: 16px; background: __CAL__ no-repeat center / contain; pointer-events: none;
}
[class*="st-key-box_f_birth"] div[data-baseweb="input"]::after { background-image: __USER__; }

.flabel { display: flex; justify-content: space-between; align-items: center; gap: 8px;
  font-size: .8rem; font-weight: 700; color: __TEXT__; margin-bottom: .35rem; min-height: 20px; }
.req { color: #F43F5E; margin-left: 2px; }
.tag { font-size: .66rem; padding: 2px 8px; border-radius: 999px; font-weight: 700; white-space: nowrap; }
.tag-amber { background: #FFF4D6; color: #8A5A00; }
.tag-brand { background: __BRAND_SOFT__; color: __BRAND__; }
.tag-hint { color: __MUTED__; font-weight: 500; font-size: .72rem; background: transparent; }

.hr { border-top: 1px solid #EEF0F5; margin: 1.25rem 0 1rem; }

div[data-testid="stForm"] button[kind="primary"] {
  background: __BRAND__ !important; color: #FFFFFF !important; border: none !important;
  border-radius: 999px !important; padding: .6rem 1.6rem; font-weight: 700;
  box-shadow: 0 12px 26px -8px rgba(82, 88, 207, .55);
}
div[data-testid="stForm"] button[kind="primary"]:hover { background: #474DC2 !important; }
div[data-testid="stForm"] button[kind="secondary"] {
  background: #FFFFFF !important; color: __TEXT__ !important; border: 1px solid __BORDER__ !important;
  border-radius: 999px !important; font-weight: 600;
}

.card { background: #FFFFFF; border: 1px solid __BORDER__; border-radius: 20px; padding: 1.2rem 1.4rem;
  margin-bottom: 14px; box-shadow: 0 10px 30px -14px rgba(82, 88, 207, .12); }
.card h4 { margin: 0 0 10px 0; font-size: 1rem; }
.kv { width: 100%; border-collapse: collapse; }
.kv td { padding: 7px 4px; border-bottom: 1px solid #F0F1F7; vertical-align: top; font-size: .9rem; }
.kv td:first-child { color: __MUTED__; width: 42%; }
.badge { display: inline-block; padding: 5px 14px; border-radius: 999px; font-size: .78rem; font-weight: 700; }
.muted { color: __MUTED__; font-size: .85rem; margin: 6px 0 0 0; }

div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid __BORDER__; border-radius: 18px; padding: 14px 18px; }
div[data-testid="stMetricLabel"] p { color: __MUTED__ !important; font-size: .8rem; }
div[data-testid="stMetricValue"] { color: __TEXT__; font-weight: 700; }

.st-key-detail_tabs { border-bottom: 1px solid __BORDER__; margin: 0 0 1rem; }
.st-key-detail_tabs [data-testid="stHorizontalBlock"] { gap: 0; }
.st-key-detail_tabs button,
.st-key-detail_tabs button[kind="primary"] {
  height: 42px; border: none !important; border-radius: 0 !important;
  background: transparent !important; color: __TEXT_SOFT__ !important;
  box-shadow: none !important; font-weight: 600; padding: 0 1.1rem;
}
.st-key-detail_tabs button[kind="primary"] {
  color: __BRAND__ !important; border-bottom: 2px solid __BRAND__ !important;
  font-weight: 700;
}
.st-key-detail_tabs button p,
.st-key-detail_tabs button[kind="primary"] p { color: inherit !important; }
.st-key-detail_tabs button:hover { background: __BRAND_SOFT__ !important; color: __BRAND__ !important; }
div[data-testid="stDataFrame"] { border: 1px solid __BORDER__; border-radius: 18px; background: #FFFFFF; }
.stButton > button { border-radius: 999px; font-weight: 700; }
"""

CHEV = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23{c}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M9 6l6 6-6 6'/%3E%3C/svg%3E\")"
CHEV_OFF = CHEV.replace("{c}", "C3C8D6")
CHEV_ON = CHEV.replace("{c}", "5258CF")

EXTRA_CSS = """
[class*="st-key-box_"] [data-testid="stHorizontalBlock"] { gap: .5rem; flex-wrap: nowrap; }
[class*="st-key-box_"] [data-testid="stDateInput"] div[data-baseweb="input"],
[class*="st-key-box_"] [data-testid="stTextInput"] div[data-baseweb="input"] {
  background: __FIELD__ !important; border: 1px solid __BORDER__ !important; border-radius: 10px !important;
}
[class*="st-key-box_"] [data-testid="stDateInput"] div[data-baseweb="input"]::after {
  content: ""; position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
  width: 16px; height: 16px; background: __CAL__ no-repeat center / contain; pointer-events: none;
}
[class*="st-key-box_f_birth"] [data-testid="stDateInput"] div[data-baseweb="input"]::after { background-image: __USER__; }
[data-testid="stToolbar"], [data-testid="stAppDeployButton"], .stAppDeployButton { display: none !important; }
.page-head p.sub { font-size: .8rem !important; }
.flabel span { white-space: nowrap; }
.tag { font-size: .62rem; }
.st-key-newbtn button { display: flex; justify-content: space-between !important; text-align: left; }
.st-key-newbtn button > div { width: auto; }
.st-key-newbtn button p { text-align: left; }
button[kind="primary"], button[kind="primaryFormSubmit"], [data-testid^="stBaseButton-primary"] {
  background: __BRAND__ !important; color: #FFFFFF !important; border: none !important;
  border-radius: 999px !important; font-weight: 700; box-shadow: 0 12px 26px -8px rgba(82, 88, 207, .55) !important;
}
button[kind="primary"]:hover, [data-testid^="stBaseButton-primary"]:hover { background: #474DC2 !important; }
button[kind="primary"] p, [data-testid^="stBaseButton-primary"] p { color: #FFFFFF !important; }
button[kind="secondaryFormSubmit"], [data-testid="stBaseButton-secondaryFormSubmit"] {
  background: #FFFFFF !important; color: __TEXT__ !important; border: 1px solid __BORDER__ !important;
  border-radius: 999px !important; font-weight: 600;
}
*, *::before, *::after { animation: none !important; transition: none !important; }
.th { font-size: .74rem; font-weight: 700; color: __MUTED__; text-transform: uppercase; letter-spacing: .04em; padding: 4px 0; }
.td { font-size: .88rem; color: __TEXT__; padding: 0; min-height: 30px; display: flex; align-items: center; }
[class*="st-key-lrow_"] { border-top: 1px solid #EEF0F5; padding: 5px 0; gap: 0; }
[class*="st-key-lrow_"] [data-testid="stHorizontalBlock"] { align-items: center; flex-wrap: nowrap; }
[class*="st-key-lrow_"] button { border-radius: 999px; font-size: 12px; padding: 0 14px; min-height: 30px; white-space: nowrap; }
[class*="st-key-lrow_"] .td { padding: 0; min-height: 30px; }
.th { padding: 0 0 6px; }
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-lrow_"]) { margin-bottom: -10px; }
/* ===== Khung cố định: sidebar, header, vùng giữa ===== */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { height: 100vh !important; overflow: hidden !important; }
.stApp { background: #FFFFFF !important; }
[data-testid="stSidebar"] { border-right: 1px solid #F0F1F7 !important; }
[data-testid="stSidebarUserContent"] { padding: 22px 10px 0 24px !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 2px !important; }
.brand { margin: 0 0 24px 6px !important; }
.brand-mark { width: 38px; height: 38px; border-radius: 12px; }
.brand-title { font-size: 17px; }
.brand-sub { font-size: 10.5px; }
.st-key-newbtn { margin-bottom: 16px; }
.st-key-newbtn button { padding: 8px 14px; font-size: 13px; min-height: 44px; border-radius: 22px; }
.st-key-newbtn button::after { width: 28px; height: 28px; font-size: 1.1rem; }
[class*="st-key-navrow_"] { margin: 0; border-radius: 14px; }
[class*="st-key-navrow_"] [data-testid="stHorizontalBlock"] { gap: 0; padding-left: 10px; flex-wrap: nowrap; }
[class*="st-key-navrow_"] button { font-size: 13.5px; padding: 6px 6px; min-height: 38px; display: flex; justify-content: space-between !important; }
[class*="st-key-navrow_"] button > div { width: auto; flex: 1; }
[class*="st-key-navrow_"] button::after { content: ""; width: 15px; height: 15px; margin-right: 8px;
  background: __CHEV_OFF__ no-repeat center / contain; }
[class*="st-key-navrow_"][class*="_on"] button::after { background-image: __CHEV_ON__; }
.st-key-profile { position: fixed; bottom: 24px; left: 18px; width: calc(__SIDEBAR_WIDTH__ - 36px);
  background: #FFFFFF; border-top: 1px solid #EEF0F5; padding-top: 10px; z-index: 5; }
.profile { display: flex; align-items: center; gap: 10px; padding: 0 4px; }
.profile-av { width: 34px; height: 34px; border-radius: 50%; background: #FDE7EA; color: #E5486A;
  display: flex; align-items: center; justify-content: center; flex: none; }
.profile-name { font-size: 12.5px; font-weight: 700; color: __TEXT__; line-height: 1.25; }
.profile-role { font-size: 10.5px; color: __MUTED__; }

/* Vùng giữa cố định, cuộn bên trong khi nội dung dài */
.block-container { position: fixed !important; top: 0; left: __SIDEBAR_WIDTH__; right: 0; bottom: 0;
  width: auto !important; max-width: none !important; margin: 0 !important; padding: 0 4px 6px 21px !important;
  overflow-x: hidden; overflow-y: auto; background: transparent !important; border: 0 !important;
  box-shadow: none !important; border-radius: 0 !important; }
.page-head { margin: 0 0 6px; }
.page-head h2 { font-size: 20px; }
.page-head p.sub { font-size: 11.5px !important; margin: 2px 0 0; }
.pill { font-size: 11.5px; padding: 5px 12px; }
div[data-testid="stForm"] { height: calc(100vh - 20px) !important; box-sizing: border-box; overflow-y: auto;
  padding: 22px 20px 14px !important; border-radius: 26px; display: flex; flex-direction: column; }
div[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 9px; }
div[data-testid="stForm"] > div { flex: 1 0 auto; }
div[data-testid="stForm"] [data-testid="stVerticalBlock"] > * { flex-shrink: 0; }
.block-container > [data-testid="stVerticalBlock"] { gap: 14px; }
[data-testid="stMarkdownContainer"]:has(.page-head, .flabel, .th, .td, .hr, .card, .profile, .brand) { margin-bottom: 0 !important; }
.page-head h2 { margin: 0 !important; padding: 0 !important; line-height: 1.25; }
.page-head p.sub { margin: 4px 0 0 !important; line-height: 1.4; }
div[data-testid="stForm"] [data-testid="stHorizontalBlock"] { gap: 10px; }
.st-key-formbtns { margin-top: auto; }
[data-testid="stLayoutWrapper"]:has(> .st-key-formbtns) { margin-top: auto; }
[class*="st-key-box_"] [data-testid="stElementContainer"] { flex-shrink: 0 !important; height: auto !important; }
[class*="st-key-box_"] [data-testid="stMarkdown"], [class*="st-key-box_"] [data-testid="stMarkdown"] > div { height: auto !important; min-height: 18px; }
.st-key-formbtns button { min-height: 34px; font-size: 12.5px; padding: 0 16px; }
[class*="st-key-box_"] { padding: 10px 12px 11px !important; border-radius: 14px !important; gap: 4px !important; }
.flabel { font-size: 11.5px; min-height: 16px; margin: 0 0 2px; }
[class*="st-key-box_"] div[data-baseweb="input"], [class*="st-key-box_"] div[data-baseweb="select"] > div { min-height: 32px !important; }
[class*="st-key-box_"] input { font-size: 12.5px; }
.hr { margin: 4px 0 0; }
div[data-baseweb="popover"] { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }
"""


def build_css():
    css = CSS_TEMPLATE
    tokens = {
        "__PAGE_BG__": PAGE_BG, "__PANEL__": PANEL, "__FIELD__": FIELD, "__BORDER__": BORDER,
        "__TEXT__": TEXT, "__TEXT_SOFT__": TEXT_SOFT, "__MUTED__": MUTED,
        "__BRAND__": BRAND, "__BRAND_SOFT__": BRAND_SOFT, "__BRAND_BORDER__": BRAND_BORDER,
        "__CAL__": CAL_ICON, "__USER__": USER_ICON, "__SIDEBAR_WIDTH__": SIDEBAR_WIDTH, "__CHEV_OFF__": CHEV_OFF, "__CHEV_ON__": CHEV_ON,
    }
    for key, value in tokens.items():
        css = css.replace(key, value)
    css += EXTRA_CSS
    for key, value in tokens.items():
        css = css.replace(key, value)
    return f"<style>{css}</style>"


st.set_page_config(page_title="Giám sát dữ liệu", layout="wide", initial_sidebar_state="expanded")

if not MODEL_PATH.exists():
    st.error(f"Chưa có file mô hình {MODEL_PATH}. Hãy chạy pipeline (01 đến 03) trước.")
    st.stop()


@st.cache_resource
def get_model():
    return load_model(MODEL_PATH)

def _demo_passwords():
    try:
        return dict(st.secrets["demo_passwords"])
    except Exception:
        return {}

@st.cache_resource
def init_db():
    """Kiểm tra schema và tạo tài khoản demo một lần cho mỗi tiến trình."""
    c = db.connect(DB_PATH)
    try:
        ensure_default_users(c, _demo_passwords())
    finally:
        c.close()
    return True


def get_conn():
    """Mỗi phiên có kết nối riêng, không dùng chung một kết nối SQLite giữa các người dùng."""
    if "_conn" not in st.session_state:
        st.session_state["_conn"] = db.connect(DB_PATH)
    return st.session_state["_conn"]


model = get_model()
try:
    init_db()
    conn = get_conn()
except db.SchemaOutdated as e:
    st.error(str(e))
    st.stop()

FORM_KEYS = ["f_patient", "f_ma", "f_last", "f_first", "f_addr", "f_city", "f_state", "f_zip",
             "f_base", "f_total", "f_cov", "f_payer", "f_provider",
             "f_code", "f_desc", "f_reason", "f_diag", "f_dxcode"]
PICKER_KEYS = ["f_birth", "f_start_date", "f_start_time", "f_stop_date", "f_stop_time"]
SELECT_DEFAULTS = {"f_cls": service.ENCOUNTER_CLASSES[0], "f_gender": "", "f_phieu": "", "f_signed": ""}
GENDER_OPTIONS = [""] + service.GENDERS
DOC_OPTIONS = ["", "co", "khong"]

st.session_state.setdefault("page", PAGE_ENTRY)
for _k in FORM_KEYS:
    st.session_state.setdefault(_k, "")
for _k in PICKER_KEYS:
    st.session_state.setdefault(_k, "")
for _k, _v in SELECT_DEFAULTS.items():
    st.session_state.setdefault(_k, _v)


def open_detail(encounter_id):
    st.session_state["list_detail"] = encounter_id
    st.session_state["_logged_access"] = None


def set_page(name):
    st.session_state["page"] = name
    st.session_state["list_detail"] = None
    st.session_state["list_page"] = 1
    st.session_state["_logged_access"] = None
    st.session_state["entry_saved_id"] = None



def close_detail():
    st.session_state.update(list_detail=None, _logged_access=None)

def reset_list_page():
    st.session_state["list_page"] = 1

def reset_form():
    for key in FORM_KEYS:
        st.session_state[key] = ""
    for key in PICKER_KEYS:
        st.session_state[key] = ""
    for key, value in SELECT_DEFAULTS.items():
        st.session_state[key] = value
    st.session_state["entry_saved_id"] = None


def flash(kind, text):
    """Thông báo sống qua một lần chạy lại (ví dụ sau khi bấm nút rồi st.rerun)."""
    st.session_state["_flash"] = st.session_state.get("_flash", []) + [(kind, text)]


def show_flash():
    items = st.session_state.get("_flash", [])
    st.session_state["_flash"] = []
    for kind, text in items:
        getattr(st, kind)(text)


def badge(text, colors=None):
    bg, fg = colors or STATUS_STYLE.get(text, NEUTRAL_STYLE)
    return f'<span class="badge" style="background:{bg};color:{fg}">{html.escape(text.upper())}</span>'


def page_header(title, subtitle, pill=None):
    pill_html = f'<span class="pill">{html.escape(pill)}</span>' if pill else ""
    st.markdown(
        f'<div class="page-head"><div><h2>{html.escape(title)}</h2>'
        f'<p class="sub">{html.escape(subtitle)}</p></div>{pill_html}</div>',
        unsafe_allow_html=True)


def nav_icon(name, active):
    color = BRAND if active else MUTED
    return (f'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def field(col, display, widget_label, key, required=False, tag=None, tag_kind="amber"):
    star = '<span class="req">*</span>' if required else ""
    tag_html = f'<span class="tag tag-{tag_kind}">{html.escape(tag)}</span>' if tag else ""
    with col.container(key=f"box_{key}"):
        st.markdown(f'<div class="flabel"><span>{html.escape(display)}{star}</span>{tag_html}</div>',
                    unsafe_allow_html=True)
        return st.text_input(widget_label, key=key, label_visibility="collapsed")



def datetime_field(col, display, key, required=True):
    """Nhập ngày và giờ bằng văn bản, trả về YYYY-MM-DD HH:MM."""
    star = '<span class="req">*</span>' if required else ""

    with col.container(key=f"box_{key}"):
        st.markdown(
            f'<div class="flabel"><span>{html.escape(display)}{star}</span></div>',
            unsafe_allow_html=True
        )

        date_col, time_col = st.columns([1.2, 0.8])

        selected_date = date_col.text_input(
            "Ngày",
            key=f"{key}_date",
            placeholder="DD/MM/YYYY",
            label_visibility="collapsed"
        )

        selected_time = time_col.text_input(
            "Giờ",
            key=f"{key}_time",
            placeholder="HH:MM",
            label_visibility="collapsed"
        )

    if selected_date.strip() and selected_time.strip():
        return f"{selected_date.strip()} {selected_time.strip()}"

    return ""



def date_field(col, display, key, tag=None):
    """Nhập ngày bằng văn bản, định dạng YYYY-MM-DD."""
    tag_html = (
        f'<span class="tag tag-amber">{html.escape(tag)}</span>'
        if tag else ""
    )

    with col.container(key=f"box_{key}"):
        st.markdown(
            f'<div class="flabel"><span>{html.escape(display)}</span>{tag_html}</div>',
            unsafe_allow_html=True
        )

        d = st.text_input(
            display,
            key=key,
            placeholder="DD/MM/YYYY",
            label_visibility="collapsed"
        )

    return d.strip()

def select_field(col, display, widget_label, key, options, format_func, required=True, tag=None):
    star = '<span class="req">*</span>' if required else ""
    tag_html = f'<span class="tag tag-amber">{html.escape(tag)}</span>' if tag else ""
    with col.container(key=f"box_{key}"):
        st.markdown(f'<div class="flabel"><span>{html.escape(display)}{star}</span>{tag_html}</div>',
                    unsafe_allow_html=True)
        return st.selectbox(widget_label, options, key=key, format_func=format_func,
                            label_visibility="collapsed")


def alert_card(latest):
    """Lỗi bất thường (luật cứng, đặc trưng ngoài khoảng) và các mục cần xác nhận (cờ thông tin)."""
    if latest is None:
        st.info("Chưa có kết quả chấm điểm.")
        return
    info = present.info_flags(latest)
    if present.is_clean(latest):
        if info:
            body = ('<div class="muted"><b>Cần xác nhận</b></div>'
                    + present.bullet_list_html([f["message"] for f in info]))
            st.markdown(f'<div class="card"><h4>Thông tin cần xác nhận</h4>{body}</div>', unsafe_allow_html=True)
        else:
            st.success("Lượt khám này không có lỗi bất thường.")
        return
    body = ""
    hard = present.hard_flags(latest)
    if hard:
        body += '<div class="muted"><b>Luật bị vi phạm</b></div>'
        body += present.bullet_list_html([f["message"] for f in hard])
    if info:
        body += '<div class="muted" style="margin-top:8px"><b>Cần xác nhận</b></div>'
        body += present.bullet_list_html([f["message"] for f in info])
    if latest["reasons"]:
        body += '<div class="muted" style="margin-top:8px"><b>Đặc trưng ngoài khoảng tham chiếu của nhóm</b></div>'
        body += present.bullet_list_html(latest["reasons"])
    if present.model_only_flag(latest):
        body += f'<div class="muted">{html.escape(present.MODEL_ONLY_NOTE)}</div>'
    st.markdown(f'<div class="card"><h4>Lỗi bất thường trong bệnh án</h4>{body}</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Điểm bất thường", "chưa tính" if latest["anomaly_score"] is None
              else f"{latest['anomaly_score']:.3f}")
    c2.metric("Ngưỡng của nhóm", f"{latest['threshold']:.3f}")
    c3.metric("Nhóm mô hình", f"{latest['group'] or '-'} ({latest['model_used']})")


def section_card(title, rows_html, extra=""):
    st.markdown(f'<div class="card"><h4>{html.escape(title)}</h4><table class="kv">{rows_html}</table>{extra}</div>',
                unsafe_allow_html=True)


def summary_card(rec, latest, wf):
    status = latest["status"] if latest else "chưa chấm điểm"
    colors = STATUS_STYLE.get(status, NEUTRAL_STYLE) if latest else PENDING_STYLE
    wf_html = badge(wf["trang_thai"]) if wf else '<span class="muted">Không có cảnh báo</span>'
    st.markdown(
        '<div class="card"><div style="display:flex;gap:30px;flex-wrap:wrap;align-items:center">'
        f'<div><div class="muted">Bệnh nhân</div><div><b>{html.escape(present.full_name(rec["LAST"], rec["FIRST"]))}</b>'
        f' · {html.escape(rec["PATIENT"])}</div></div>'
        f'<div><div class="muted">Lượt khám</div><div>{html.escape(rec["Id"])}</div></div>'
        f'<div><div class="muted">Kết quả chấm điểm</div>{badge(status, colors)}</div>'
        f'<div><div class="muted">Xử lý cảnh báo</div>{wf_html}</div>'
        f'<div><div class="muted">Phiên bản hồ sơ</div>r{rec["revision"]}</div>'
        '</div></div>', unsafe_allow_html=True)


def _birth_text(conn, rec):
    """Ngày sinh của lượt khám; nếu lượt khám không lưu ngày sinh (bệnh nhân cũ) thì dùng ngày sinh tham chiếu."""
    if not is_blank(rec["BIRTHDATE"]):
        return present.fmt_date(rec["BIRTHDATE"])
    ref = db.reference_birthdate(conn, rec["PATIENT"])
    if ref is None:
        return present.NOT_AVAILABLE
    return f"{ref.strftime('%d/%m/%Y')} (theo lịch sử bệnh nhân)"


def render_record(conn, rec, wf):
    eid, pid = rec["Id"], rec["PATIENT"]
    prior = db.prior_conditions(conn, pid, eid, to_ts(rec["START"]))
    own = db.conditions_for_encounter(conn, eid)
    timeline = db.patient_encounters(conn, pid)[:10]

    # 1. Thông tin hành chính
    rows1 = (present.row("Mã bệnh nhân (PATIENT)", rec["PATIENT"])
             + present.row("Họ và tên", present.full_name(rec["LAST"], rec["FIRST"]))
             + present.row("Ngày sinh", _birth_text(conn, rec))
             + present.row("Giới tính", present.gender_label(rec["GENDER"]))
             + present.row("Địa chỉ", present.address_line(rec["ADDRESS"], rec["CITY"], rec["STATE"], rec["ZIP"]))
             + present.row("Mã lượt khám", rec["Id"])
             + present.row("Mã đơn vị thanh toán (PAYER)", present.value_or_dash(rec["PAYER"]))
             + present.row("Phần bảo hiểm chi trả", present.fmt_money(rec["PAYER_COVERAGE"])))

    # 2. Tiền sử và bệnh sử
    rows2 = present.row("Lý do khám", present.value_or_dash(rec["REASONDESCRIPTION"]))
    if prior:
        items = [present.condition_line(c) for c in prior[:15]]
        body = present.bullet_list_html(items)
        if len(prior) > 15:
            body += f'<div class="muted">… và {len(prior) - 15} bệnh khác</div>'
        rows2 += present.row_html("Tiền sử bệnh cá nhân", body)
    else:
        rows2 += present.row("Tiền sử bệnh cá nhân", "Chưa có tiền sử bệnh được ghi nhận trước lượt khám này")

    # 3. Thăm khám và chẩn đoán
    rows3 = present.row("Loại lượt khám", CLASS_LABELS.get(rec["ENCOUNTERCLASS"], rec["ENCOUNTERCLASS"]))
    rows3 += present.row("Thời gian khám",
                         f"{present.fmt_datetime(rec['START'])} → {present.fmt_datetime(rec['STOP'])}"
                         f" ({present.fmt_hours(rec['START'], rec['STOP'])})")
    if own:
        diag_items = [c["DESCRIPTION"] or c["CODE"] or present.NOT_AVAILABLE for c in own]
        rows3 += present.row_html("Chẩn đoán trong lượt khám", present.bullet_list_html(diag_items))
    else:
        rows3 += present.row("Chẩn đoán trong lượt khám", "Chưa có chẩn đoán được ghi nhận cho lượt khám này")

    # 4. Điều trị và theo dõi
    proc = " — ".join(str(p) for p in [rec["CODE"], rec["DESCRIPTION"]] if not is_blank(p))
    rows4 = present.row("Thủ thuật và thủ tục", proc or present.NOT_AVAILABLE)
    rows4 += present.row("Chi phí cơ bản", present.fmt_money(rec["BASE_ENCOUNTER_COST"]))
    rows4 += present.row("Tổng chi phí", present.fmt_money(rec["TOTAL_CLAIM_COST"]))

    # 5. Thông tin xác thực
    rows5 = present.row("Bác sĩ phụ trách (PROVIDER)", present.value_or_dash(rec["PROVIDER"]))
    rows5 += present.row("Phiếu và biểu mẫu", service.DOC_LABELS.get(rec.get("PHIEU_DAY_DU") or "", "Chưa khai báo"))
    rows5 += present.row("Tài liệu đã ký số", service.DOC_LABELS.get(rec.get("DA_KY_SO") or "", "Chưa khai báo"))
    rows5 += present.row("Nguồn dữ liệu", present.SOURCE_LABELS.get(rec["source"], rec["source"]))
    rows5 += present.row("Hồ sơ tạo lúc", present.fmt_datetime(rec["created_at"]))
    rows5 += present.row("Chỉnh sửa hồ sơ lần cuối",
                         present.fmt_datetime(rec["cap_nhat_emr_luc"]) if rec["cap_nhat_emr_luc"] else "Chưa chỉnh sửa")
    rows5 += present.row("Phiên bản hồ sơ", f"r{rec['revision']}")
    rows5 += present.row("Cập nhật xử lý lần cuối", present.fmt_datetime(wf["cap_nhat_luc"]) if wf else present.NOT_AVAILABLE)
    rows5 += present.row("Người hoàn tất xử lý", (wf or {}).get("nguoi_hoan_tat") or present.NOT_AVAILABLE)

    left, right = st.columns(2)
    with left:
        section_card("1. Thông tin hành chính", rows1)
        section_card("2. Tiền sử và bệnh sử", rows2)
    with right:
        section_card("3. Thăm khám và chẩn đoán", rows3)
        section_card("4. Điều trị và theo dõi", rows4)
        if timeline:
            st.caption("Diễn biến: 10 lượt khám gần nhất của bệnh nhân")
            tl = pd.DataFrame([{
                "Thời gian": present.fmt_datetime(t["START"]),
                "Loại khám": CLASS_LABELS.get(t["ENCOUNTERCLASS"], t["ENCOUNTERCLASS"]),
                "Thủ tục": t["DESCRIPTION"] or present.NOT_AVAILABLE,
                "Tổng chi phí": present.fmt_money(t["TOTAL_CLAIM_COST"]),
                "Lượt khám": t["Id"],
            } for t in timeline])
            st.dataframe(tl, use_container_width=True, hide_index=True)
        section_card("5. Thông tin xác thực", rows5)


def render_score_history(conn, eid):
    st.markdown("#### Lịch sử chấm điểm")
    hist = db.score_history(conn, eid)
    if not hist:
        st.info("Chưa có lịch sử chấm điểm.")
        return
    df = pd.DataFrame(hist).rename(columns={
        "model_version": "Mô hình", "emr_revision": "Phiên bản hồ sơ", "status": "Kết quả",
        "anomaly_score": "Điểm", "threshold": "Ngưỡng", "group_name": "Nhóm", "model_used": "Loại mô hình",
        "scored_at": "Chấm lúc"})
    st.dataframe(df, use_container_width=True, hide_index=True)


def edit_widget(col, field_name, label, kind, current, key):
    if kind == "gender":
        idx = GENDER_OPTIONS.index(current) if current in GENDER_OPTIONS else 0
        return col.selectbox(label, GENDER_OPTIONS, index=idx, key=key,
                             format_func=lambda g: service.GENDER_LABELS.get(g, ""))
    if kind == "class":
        cls_list = service.ENCOUNTER_CLASSES
        idx = cls_list.index(current) if current in cls_list else 0
        return col.selectbox(label, cls_list, index=idx, key=key, format_func=lambda c: CLASS_LABELS.get(c, c))
    if kind == "doc":
        idx = DOC_OPTIONS.index(current) if current in DOC_OPTIONS else 0
        return col.selectbox(label, DOC_OPTIONS, index=idx, key=key,
                             format_func=lambda v: service.DOC_LABELS.get(v, ""))
    if kind == "date":
        return col.text_input(label, value=present.edit_date(current), key=key, placeholder="DD/MM/YYYY")
    if kind == "datetime":
        return col.text_input(label, value=present.edit_datetime(current), key=key,
                              placeholder="YYYY-MM-DD HH:MM:SS")
    if kind == "money":
        return col.text_input(label, value=present.edit_money(current), key=key)
    return col.text_input(label, value="" if is_blank(current) else str(current), key=key)


def render_edit_form(conn, rec):
    eid, rev = rec["Id"], rec["revision"]
    st.markdown("#### 1. Cập nhật thông tin nếu dữ liệu sai")
    st.caption("Chỉ các trường thay đổi được lưu. Mỗi trường ghi giá trị cũ và mới vào lịch sử. "
               "Sau khi lưu, hệ thống chấm lại ngay với mô hình hiện tại.")
    values = {}
    with st.container(border=True):
        cols = st.columns(3)
        for i, (field_name, label, kind) in enumerate(service.EMR_FIELDS):
            values[field_name] = edit_widget(cols[i % 3], field_name, label, kind, rec.get(field_name),
                                             f"e_{eid}_{rev}_{field_name}")
    edit_note = st.text_area("Lý do cập nhật (bắt buộc)", key=f"enote_{eid}_{rev}")
    if st.button("Lưu cập nhật", key=f"save_{eid}_{rev}"):
        try:
            changed = service.update_emr(conn, model, eid, values, edit_note, actor=user)
        except service.EditError as e:
            for msg in e.errors:
                st.error(msg)
        else:
            names = ", ".join(service.EMR_LABELS.get(f, f) for f in changed)
            flash("success", f"Đã lưu {len(changed)} trường: {names}. Đã chấm lại với mô hình hiện tại.")
            st.rerun()


def render_finish_form(conn, rec):
    eid = rec["Id"]
    st.markdown("#### 2. Kết luận và hoàn tất xử lý")
    st.caption("Chọn 'Đã cập nhật dữ liệu' khi đã lưu cập nhật ở mục 1. Chọn 'Xác nhận cảnh báo' "
               "khi dữ liệu cần được xem xét thêm.")
    result = st.radio("Kết luận", service.RESULT_CHOICES, key=f"res_{eid}")
    note = st.text_area("Ghi chú kết luận (bắt buộc)", key=f"fnote_{eid}")
    if st.button("Hoàn tất xử lý", type="primary", key=f"finish_{eid}"):
        try:
            service.finish_processing(conn, eid, result, note, actor=user)
        except service.EditError as e:
            st.error(str(e))
        else:
            flash("success", "Đã hoàn tất xử lý. Lượt khám chuyển sang trạng thái đã xử lý.")
            st.rerun()


def render_workflow(conn, rec, wf):
    eid = rec["Id"]
    if wf is None:
        st.info("Lượt khám này không có cảnh báo nên không cần xử lý.")
        return
    state = wf["trang_thai"]
    st.markdown(f'<div class="card">Trạng thái: {badge(state)}'
                f'<p class="muted">Cập nhật lúc {html.escape(present.fmt_datetime(wf["cap_nhat_luc"]))}</p></div>',
                unsafe_allow_html=True)

    if state == db.PENDING:
        st.write("Lượt khám đang chờ xử lý. Bấm nhận xử lý để bắt đầu kiểm tra và cập nhật hồ sơ.")
        if st.button("Bắt đầu xử lý", type="primary", key=f"start_{eid}"):
            try:
                service.start_processing(conn, eid, actor=user)
            except service.EditError as e:
                st.error(str(e))
            else:
                flash("success", "Đã chuyển sang đang xử lý.")
                st.rerun()
    elif state == db.PROCESSING:
        render_edit_form(conn, rec)
        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
        render_finish_form(conn, rec)
    else:
        st.markdown(
            '<div class="card"><h4>Kết luận xử lý</h4><table class="kv">'
            f'<tr><td>Kết luận</td><td>{html.escape(wf["ket_qua"] or "—")}</td></tr>'
            f'<tr><td>Ghi chú</td><td>{html.escape(wf["ghi_chu_ket_qua"] or "—")}</td></tr>'
            f'<tr><td>Người hoàn tất</td><td>{html.escape(wf["nguoi_hoan_tat"] or "—")}</td></tr>'
            f'<tr><td>Hoàn tất lúc</td><td>{html.escape(present.fmt_datetime(wf["hoan_tat_luc"]))}</td></tr>'
            '</table></div>', unsafe_allow_html=True)
        reopen_note = st.text_area("Lý do mở lại xử lý (bắt buộc)", key=f"reopen_note_{eid}")
        if st.button("Mở lại xử lý", key=f"reopen_{eid}"):
            try:
                service.reopen_processing(conn, eid, reopen_note, actor=user)
            except service.EditError as e:
                st.error(str(e))
            else:
                flash("success", "Đã mở lại xử lý.")
                st.rerun()


def render_logs(conn, eid):
    st.markdown("#### Nhật ký xử lý")
    audit = db.audit_log(conn, eid)
    if audit:
        st.dataframe(pd.DataFrame(audit), use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có nhật ký xử lý.")

    st.markdown("#### Thay đổi hồ sơ (giá trị cũ và mới)")
    changes = db.edit_log(conn, eid)
    if changes:
        df = pd.DataFrame(changes)[["revision", "truong", "gia_tri_cu", "gia_tri_moi", "ghi_chu",
                                    "nguoi_thuc_hien", "thoi_gian"]]
        df = df.rename(columns={"revision": "Phiên bản", "truong": "Trường", "gia_tri_cu": "Giá trị cũ",
                                "gia_tri_moi": "Giá trị mới", "ghi_chu": "Lý do",
                                "nguoi_thuc_hien": "Người sửa", "thoi_gian": "Thời gian"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Hồ sơ chưa được chỉnh sửa.")

    st.markdown("#### Lịch sử truy xuất")
    access = db.access_log(conn, eid)
    if access:
        st.dataframe(pd.DataFrame(access)[["nguoi_truy_cap", "thoi_gian"]].rename(
            columns={"nguoi_truy_cap": "Người xem", "thoi_gian": "Thời gian"}),
            use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có lượt truy xuất.")


def render_detail(encounter_id):
    rec = db.get_encounter(conn, encounter_id)
    if rec is None:
        st.error("Không tìm thấy lượt khám.")
        return
    if st.session_state.get("_logged_access") != encounter_id:
        db.add_access(conn, encounter_id, user.name)
        st.session_state["_logged_access"] = encounter_id
    show_flash()
    latest = db.latest_score(conn, encounter_id)
    wf = db.get_workflow(conn, encounter_id)
    summary_card(rec, latest, wf)
    for note in db.copied_fields(conn, encounter_id):
        st.warning(note + ". Đối chiếu với giấy tờ trước khi xác nhận.")
    alert_card(latest)
    tab_key = f"detail_tab_{encounter_id}"
    # Chỉ hiện tab mà vai trò hiện tại được phép dùng
    tab_names = ["Hồ sơ bệnh án"]
    if user.can(auth.PERM_XU_LY):
        tab_names.append("Xử lý")
    if user.can(auth.PERM_XEM_NHAT_KY):
        tab_names.append("Lịch sử")
    default_tab = ("Xử lý" if wf and wf["trang_thai"] in (db.PENDING, db.PROCESSING) and "Xử lý" in tab_names
                   else "Hồ sơ bệnh án")
    if st.session_state.get(tab_key) not in tab_names:
        st.session_state[tab_key] = default_tab
    st.session_state.setdefault(tab_key, default_tab)
    with st.container(key="detail_tabs"):
        tab_cols = st.columns(len(tab_names), gap="small")
        for tab_col, tab_name in zip(tab_cols, tab_names):
            tab_col.button(
                tab_name,
                key=f"{tab_key}_{tab_name}",
                type="primary" if st.session_state[tab_key] == tab_name else "secondary",
                use_container_width=True,
                on_click=lambda name=tab_name: st.session_state.update({tab_key: name}),
            )
    selected_tab = st.session_state[tab_key]
    if selected_tab == "Hồ sơ bệnh án":
        render_record(conn, rec, wf)
    elif selected_tab == "Xử lý":
        render_workflow(conn, rec, wf)
    elif selected_tab == "Lịch sử":
        render_logs(conn, encounter_id)
        render_score_history(conn, encounter_id)


def _keep_conn():
    """Giữ kết nối của phiên khi xóa trạng thái đăng nhập."""
    return {k: v for k, v in st.session_state.items() if k == "_conn"}


def logout():
    keep = _keep_conn()
    st.session_state.clear()
    st.session_state.update(keep)
    st.session_state["page"] = PAGE_ENTRY


LOGIN_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

.stApp {
  font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
  background: linear-gradient(135deg, #EEF2FF 0%, #FFFFFF 60%, #F3F6FF 100%) !important;
}
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; background: transparent; }
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
[data-testid="stAppViewContainer"], [data-testid="stMain"] {
  height: auto !important; min-height: 100vh; overflow: auto !important;
}

/* Khối nội dung: căn giữa ngang và dọc, không cố định vị trí như giao diện chính */
.block-container {
  position: static !important; width: 100% !important; max-width: 460px !important;
  margin: 0 auto !important; padding: 8vh 1rem 2rem !important;
  background: transparent !important; border: 0 !important; box-shadow: none !important;
  overflow: visible !important;
}

.login-brand { display: flex; flex-direction: column; align-items: center; margin-bottom: 1.6rem; }
.login-mark {
  width: 56px; height: 56px; border-radius: 18px; background: #F4F5FD; color: #5258CF;
  border: 1px solid #E0E2F7; display: flex; align-items: center; justify-content: center; margin-bottom: 12px;
}
.login-app { font-size: 1.1rem; font-weight: 800; color: #1E293B; }
.login-app-sub { font-size: .78rem; color: #8E96AA; }
.login-title {
  font-size: 1.9rem; font-weight: 800; color: #1E293B; text-align: center;
  letter-spacing: -.02em; margin: 1.6rem 0 .3rem;
}
.login-subtitle { font-size: .95rem; color: #64748B; text-align: center; margin: 0 0 1.4rem; }

/* Thẻ đăng nhập */
div[data-testid="stForm"] {
  background: #FFFFFF; border: 1px solid #E3E8F5; border-radius: 24px;
  padding: 2rem 2rem 1.8rem; box-shadow: 0 24px 60px -20px rgba(82, 88, 207, .25);
}
div[data-testid="stForm"] [data-testid="stWidgetLabel"] p {
  font-size: .9rem; font-weight: 600; color: #344563;
}
div[data-testid="stForm"] div[data-baseweb="input"] {
  border: 1px solid #D9E0EE !important; border-radius: 12px !important; background: #FAFBFE !important;
  min-height: 48px;
}
div[data-testid="stForm"] div[data-baseweb="input"]:focus-within {
  border-color: #5258CF !important; box-shadow: 0 0 0 3px #E8EAFB;
}
div[data-testid="stForm"] input { font-size: 1rem; color: #1E293B; }
/* Ẩn nút hiện/ẩn mật khẩu để tránh hiển thị chữ thay cho icon khi font icon không tải được */
div[data-testid="stForm"] div[data-baseweb="input"] button { display: none !important; }

div[data-testid="stForm"] button[type="submit"] {
  width: 100%; min-height: 50px; margin-top: .6rem; border: none; border-radius: 12px;
  background: #5258CF; color: #FFFFFF; font-size: 1rem; font-weight: 700;
  box-shadow: 0 12px 26px -8px rgba(82, 88, 207, .55);
}
div[data-testid="stForm"] button[type="submit"]:hover { background: #474DC2; }
div[data-testid="stForm"] button[type="submit"] p { color: #FFFFFF !important; font-size: 1rem; }

@media (max-width: 600px) {
  .block-container { padding-top: 4vh !important; }
  div[data-testid="stForm"] { padding: 1.5rem 1.2rem; }
  .login-title { font-size: 1.6rem; }
}
"""


def render_login():
    st.markdown(f"<style>{LOGIN_CSS}</style>", unsafe_allow_html=True)
    st.markdown(
        '<div class="login-brand"><div class="login-mark">'
        '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"/><path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2"/>'
        '<path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"/>'
        '<path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>'
        '</svg></div>'
        '<div class="login-app">Giám sát dữ liệu</div>'
        '<div class="login-app-sub">Clinical Data System</div></div>'
        '<h1 class="login-title">Đăng nhập</h1>'
        '<p class="login-subtitle">Dùng tài khoản được cấp để truy cập hệ thống.</p>',
        unsafe_allow_html=True)

    with st.form("login", clear_on_submit=False, border=False):
        username = st.text_input("Tên đăng nhập", placeholder="Nhập tên đăng nhập", key="login_user")
        password = st.text_input("Mật khẩu", placeholder="Nhập mật khẩu", type="password", key="login_pass")
        submitted = st.form_submit_button("Đăng nhập", use_container_width=True)

    if submitted:
        found = auth.authenticate(conn, username, password)
        if found is None:
            st.error("Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã bị khóa.")
        else:
            keep = _keep_conn()
            st.session_state.clear()  # không để lại dữ liệu của phiên trước
            st.session_state.update(keep)
            st.session_state["user"] = found
            st.session_state["page"] = PAGE_ENTRY
            st.rerun()

user = st.session_state.get("user")
if user is None:
    render_login()
    st.stop()

st.markdown(build_css(), unsafe_allow_html=True)
PAGE_PERMISSION = {
    PAGE_ENTRY: auth.PERM_NHAP_BAN_GHI,
    PAGE_LIST: auth.PERM_XEM_DANH_SACH,
    PAGE_LOG: auth.PERM_XEM_NHAT_KY,
    PAGE_MODEL: auth.PERM_QUAN_LY_MO_HINH,
}
VISIBLE_PAGES = [p for p in PAGES if user.can(PAGE_PERMISSION[p])]
if st.session_state["page"] not in VISIBLE_PAGES:
    st.session_state["page"] = VISIBLE_PAGES[0]


with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">'
                '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"/><path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2"/>'
                '<path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"/>'
                '<path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>'
                '</svg></div><div>'
                '<div class="brand-title">Giám sát dữ liệu</div>'
                '<div class="brand-sub">Clinical Data System</div></div></div>', unsafe_allow_html=True)

    if user.can(auth.PERM_NHAP_BAN_GHI):
        with st.container(key="newbtn"):
            st.button("Nhập bản ghi mới", key="new_btn", on_click=set_page, args=(PAGE_ENTRY,),
                      use_container_width=True)

    for i, name in enumerate(VISIBLE_PAGES):
        active = st.session_state["page"] == name
        with st.container(key=f"navrow_{i}_{'on' if active else 'off'}"):
            icon_col, btn_col = st.columns([1, 6])
            icon_col.markdown(nav_icon(name, active), unsafe_allow_html=True)
            btn_col.button(name, key=f"nav_{i}", on_click=set_page, args=(name,), use_container_width=True)

    with st.container(key="profile"):
        st.markdown('<div class="profile"><div class="profile-av">'
                    '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="8" r="4"/>'
                    '<path d="M4 21c0-4 4-6 8-6s8 2 8 6z"/></svg></div>'
                    f'<div><div class="profile-name">{html.escape(user.name)}</div>'
                    f'<div class="profile-role">{html.escape(user.role_label)}'
                    f'{" · " + html.escape(user.khoa) if user.khoa else ""}</div></div></div>',
                    unsafe_allow_html=True)
    st.button("Đăng xuất", key="logout_btn", on_click=logout, use_container_width=True)

page = st.session_state["page"]

if page == PAGE_ENTRY:
    with st.form("entry", border=False):
        page_header("Nhập bản ghi khám bệnh mới",
                    "Chấm điểm bất thường và lưu vào hệ thống. Trường có dấu * là bắt buộc.",
                    pill="Sẵn sàng chấm điểm")
        st.markdown('<div class="hr" style="margin-bottom:8px"></div>', unsafe_allow_html=True)
        r1a, r1b = st.columns(2)
        patient = field(r1a, "Mã bệnh nhân", "Mã bệnh nhân (PATIENT) *", "f_patient", required=True)
        ma = field(r1b, "Mã lượt khám", "Mã lượt khám (để trống để hệ thống tạo)", "f_ma",
                   tag="Tự động khởi tạo nếu để trống", tag_kind="hint")

        r2a, r2b, r2c, r2d = st.columns([1, 1, 0.9, 1.1])
        last = field(r2a, "Họ", "Họ (LAST)", "f_last", tag="BN mới bắt buộc")
        first = field(r2b, "Tên", "Tên (FIRST)", "f_first", tag="BN mới bắt buộc")
        gender = select_field(r2c, "Giới tính", "Giới tính (GENDER)", "f_gender", GENDER_OPTIONS,
                              lambda g: service.GENDER_LABELS.get(g, ""), required=False, tag="BN mới bắt buộc")
        birth = date_field(r2d, "Ngày sinh", "f_birth", tag="BN mới bắt buộc")

        r3a, r3b, r3c = st.columns([2,1,1])
        addr = field(r3a, "Địa chỉ", "Địa chỉ (ADDRESS)", "f_addr")
        city = field(r3b, "Quận/Phường/Xã", "Quận/Phường/Xã", "f_city")
        state = field(r3c, "Tỉnh/Thành phố", "Tỉnh/Thành phố (STATE)", "f_state")


        r4a, r4b, r4c = st.columns(3)
        start = datetime_field(r4a, "Bắt đầu", "f_start")
        stop = datetime_field(r4b, "Kết thúc", "f_stop")
        cls = select_field(r4c, "Loại lượt khám", "Loại lượt khám (ENCOUNTERCLASS) *", "f_cls",
                           service.ENCOUNTER_CLASSES, lambda c: CLASS_LABELS.get(c, c))

        r5a, r5b, r5c = st.columns(3)
        total = field(r5a, "Tổng chi phí", "Tổng chi phí (TOTAL_CLAIM_COST) *", "f_total",
                      required=True, tag="VND", tag_kind="brand")
        base = field(r5b, "Chi phí cơ bản", "Chi phí cơ bản (BASE_ENCOUNTER_COST) *", "f_base",
                     required=True, tag="VND", tag_kind="brand")
        cov = field(r5c, "Phần BH chi trả", "Phần BH chi trả (PAYER_COVERAGE)", "f_cov",
                    tag="VND", tag_kind="brand")

        r6a, r6b = st.columns([1, 2])
        code = field(r6a, "Mã thủ tục", "Mã thủ tục (CODE)", "f_code")
        desc = field(r6b, "Mô tả thủ tục", "Mô tả thủ tục (DESCRIPTION)", "f_desc")

        r7a, r7b, r7c = st.columns([1.4, 1.6, 1])
        reason = field(r7a, "Lý do khám", "Lý do khám (REASONDESCRIPTION)", "f_reason")
        diag = field(r7b, "Chẩn đoán", "Chẩn đoán trong lượt khám", "f_diag",
                     tag="Không bắt buộc", tag_kind="hint")
        dxcode = field(r7c, "Mã ICD-10", "Mã ICD-10 của chẩn đoán", "f_dxcode",
                       tag="Nếu có chẩn đoán", tag_kind="hint")

        r8a, r8b = st.columns(2)
        payer = field(r8a, "Đơn vị thanh toán", "Đơn vị thanh toán (PAYER)", "f_payer")
        provider = field(r8b, "Bác sĩ phụ trách", "Bác sĩ phụ trách (PROVIDER)", "f_provider")

        r9a, r9b = st.columns(2)
        phieu = select_field(r9a, "Phiếu và biểu mẫu", "Phiếu và biểu mẫu (PHIEU_DAY_DU)", "f_phieu",
                             DOC_OPTIONS, lambda v: service.DOC_LABELS.get(v, ""), required=False,
                             tag="Để trống nếu chưa kiểm tra")
        signed = select_field(r9b, "Tài liệu đã ký số", "Tài liệu đã ký số (DA_KY_SO)", "f_signed",
                              DOC_OPTIONS, lambda v: service.DOC_LABELS.get(v, ""), required=False,
                              tag="Để trống nếu chưa kiểm tra")

        with st.container(key="formbtns"):
            st.markdown('<div class="hr" style="margin:0 0 10px"></div>', unsafe_allow_html=True)
            b1, b2, _ = st.columns([1.1, 2, 4])
            b1.form_submit_button("Nhập lại", on_click=reset_form, use_container_width=True)
            submitted = b2.form_submit_button("✓  Chấm điểm và lưu", type="primary", use_container_width=True)

    if submitted:
        components.html("<script>setTimeout(function(){var c=window.parent.document.querySelector('.block-container');"
                        "if(c){c.scrollTo({top:c.scrollHeight});}},250);</script>", height=0)
        raw = {"PATIENT": patient, "Id": ma, "ENCOUNTERCLASS": cls, "START": start, "STOP": stop,
               "BIRTHDATE": birth, "FIRST": first, "LAST": last, "GENDER": gender, "ADDRESS": addr,
               "CITY": city, "STATE": state, "BASE_ENCOUNTER_COST": base,
               "TOTAL_CLAIM_COST": total, "PAYER_COVERAGE": cov, "PAYER": payer, "PROVIDER": provider,
               "REASONDESCRIPTION": reason, "CODE": code, "DESCRIPTION": desc, "DIAGNOSIS": diag,
               "DIAGNOSIS_CODE": dxcode, "PHIEU_DAY_DU": phieu, "DA_KY_SO": signed}
        has_history = db.patient_has_records(conn, patient.strip()) if patient.strip() else False
        record, errors = service.validate_input(raw, has_history)
        if not start:
            errors = [e for e in errors if not e.startswith("Bắt đầu (START)")] + ["Hãy chọn ngày và giờ bắt đầu"]
        if not stop:
            errors = [e for e in errors if not e.startswith("Kết thúc (STOP)")] + ["Hãy chọn ngày và giờ kết thúc"]
        st.session_state["entry_saved_id"] = None
        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                service.score_and_store(conn, model, record, source="manual", actor=user)
                st.session_state["entry_saved_id"] = record["Id"]
                flash("success", f"Đã lưu lượt khám {record['Id']}")
            except db.EncounterExists:
                st.error("Mã lượt khám đã tồn tại. Hãy chọn mã khác hoặc để trống.")

    # Hồ sơ vừa lưu luôn hiển thị lại sau mỗi thao tác (chuyển trạng thái, chỉnh sửa, chấm lại).
    saved_id = st.session_state.get("entry_saved_id")
    if saved_id:
        st.markdown("### Hồ sơ lượt khám vừa lưu")
        render_detail(saved_id)

elif page == PAGE_LIST:
    PER_PAGE = 8
    detail_id = st.session_state.get("list_detail")
    if detail_id:
        page_header("Chi tiết lượt khám", "Kiểm tra lỗi bất thường, cập nhật hồ sơ và kết luận xử lý.")
        st.button("← Quay lại danh sách", key="back_list", on_click=close_detail)
        render_detail(detail_id)
    else:
        page_header("Danh sách cảnh báo", "Lượt khám bất thường cần theo dõi. Bấm Xem chi tiết để kiểm tra và xử lý.")
        SORT_OPTIONS = {"moi_nhat": "Mới nhất trước", "trang_thai": "Ưu tiên chờ xử lý"}
        c0, c1, c2, c3 = st.columns([2, 1, 1, 1])
        keyword = c0.text_input("Tìm theo tên, mã bệnh nhân hoặc mã lượt khám", key="f_search",
                                placeholder="Ví dụ: nguyen an, P-001, L123",
                                on_change=reset_list_page)
        status_filter = c1.selectbox("Lọc theo trạng thái xử lý", ["Tất cả"] + db.STATES, key="f_status",
                                     on_change=reset_list_page)
        cls_filter = c2.selectbox("Lọc theo loại lượt khám", ["Tất cả"] + service.ENCOUNTER_CLASSES,
                                  key="f_cls_list", on_change=reset_list_page,
                                  format_func=lambda c: c if c == "Tất cả" else CLASS_LABELS.get(c, c))
        sort_key = c3.selectbox("Sắp xếp", list(SORT_OPTIONS), key="f_sort", on_change=reset_list_page,
                                format_func=lambda k: SORT_OPTIONS[k])
        items = db.list_items(conn,
                              status=None if status_filter == "Tất cả" else status_filter,
                              encounter_class=None if cls_filter == "Tất cả" else cls_filter,
                              sort=sort_key)
        items = filter_items(items, keyword)
        if not items:
            if keyword.strip():
                st.info(f"Không tìm thấy hồ sơ nào khớp với '{keyword.strip()}' trong bộ lọc hiện tại.")
            else:
                st.info("Không có lượt khám nào khớp bộ lọc. Nếu chưa có dữ liệu, nạp dữ liệu demo ở mục "
                        "'Mô hình và dữ liệu'.")
        else:
            pages = max(1, -(-len(items) // PER_PAGE))
            cur = min(st.session_state.get("list_page", 1), pages)
            chunk = items[(cur - 1) * PER_PAGE: cur * PER_PAGE]
            widths = [1.2, 2.0, 1.6, 1.2, 1.4, 1.3, 1.2]
            head = st.columns(widths)
            for col, text in zip(head, ["Mã lượt khám", "Bệnh nhân", "Loại khám", "Tổng chi phí",
                                        "Kết quả chấm điểm", "Xử lý", ""]):
                col.markdown(f'<div class="th">{text}</div>', unsafe_allow_html=True)
            for i in chunk:
                with st.container(key=f"lrow_{i['Id']}"):
                    cols = st.columns(widths)
                    cols[0].markdown(f'<div class="td">{html.escape(str(i["Id"])[:8])}</div>', unsafe_allow_html=True)
                    full = present.full_name(i.get("LAST"), i.get("FIRST"))
                    shown = full if full != present.NOT_AVAILABLE else str(i["PATIENT"])[:12]
                    cols[1].markdown(f'<div class="td">{html.escape(shown[:24])}</div>', unsafe_allow_html=True)
                    cols[2].markdown(f'<div class="td">{html.escape(CLASS_LABELS.get(i["ENCOUNTERCLASS"], i["ENCOUNTERCLASS"]))}</div>',
                                     unsafe_allow_html=True)
                    cost = present.fmt_money(i["TOTAL_CLAIM_COST"]).replace(" VND", "")
                    cols[3].markdown(f'<div class="td">{cost}</div>', unsafe_allow_html=True)
                    cols[4].markdown(f'<div class="td">{badge(i["status"]) if i["status"] else "—"}</div>',
                                     unsafe_allow_html=True)
                    cols[5].markdown(f'<div class="td">{badge(i["trang_thai"]) if i["trang_thai"] else "—"}</div>',
                                     unsafe_allow_html=True)
                    cols[6].button("Xem chi tiết", key=f"view_{i['Id']}",
                                   on_click=lambda _id=i["Id"]: open_detail(_id))

            if pages > 1:
                st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
                p1, p2, p3 = st.columns([1, 8, 1])
                with p1:
                    st.button("‹ Trước", key="pg_prev", disabled=cur <= 1,
                              on_click=lambda: st.session_state.update(list_page=cur - 1),
                              use_container_width=True)
                with p2:
                    st.markdown(
                        f"""<div style="text-align:center;display:flex;justify-content:center;align-items:center;
                        height:38px;font-weight:500;">Trang {cur}/{pages} · {len(items)} lượt khám</div>""",
                        unsafe_allow_html=True)
                with p3:
                    st.button("Sau ›", key="pg_next", disabled=cur >= pages,
                              on_click=lambda: st.session_state.update(list_page=cur + 1),
                              use_container_width=True)

elif page == PAGE_LOG:
    page_header("Nhật ký thay đổi", "Ghi lại mọi thay đổi trạng thái và chỉnh sửa. Bảng này chỉ thêm, không sửa và không xóa được.")
    st.dataframe(pd.DataFrame(db.audit_log(conn, limit=300)), use_container_width=True, hide_index=True)

elif page == PAGE_MODEL:
    page_header("Mô hình và dữ liệu", "Thông tin mô hình đang dùng và dữ liệu demo trong hệ thống.")
    for w in model_warnings(model):
        st.warning(w)
    st.markdown(
        f'<div class="card">Phiên bản: <b>{html.escape(model["model_version"])}</b>, '
        f'tạo lúc {html.escape(model["created_at"])}, seed {model["seed"]}, '
        f'scikit-learn {html.escape(model["sklearn_version"])}</div>', unsafe_allow_html=True)
    rows = []
    for g, e in sorted(model["groups"].items()):
        rows.append({"nhóm": g, "loại": e["model_type"], "n_train": e["n_train"],
                     "contamination": e["contamination"], "ngưỡng": round(e["threshold"], 4),
                     "F1 huấn luyện": round(e["train_f1"], 3)})
    fb = model["fallback"]
    rows.append({"nhóm": "dự phòng", "loại": fb["model_type"], "n_train": fb["n_train"],
                 "contamination": fb["contamination"], "ngưỡng": round(fb["threshold"], 4),
                 "F1 huấn luyện": round(fb["train_f1"], 3)})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Số lượt khám trong CSDL", db.count_encounters(conn))
    c2.metric("Số dòng chẩn đoán và tiền sử", db.count_conditions(conn))
    c3.metric("Số bệnh nhân", len({r[0] for r in conn.execute("SELECT DISTINCT PATIENT FROM luot_kham")}))
    if db.count_encounters(conn) == 0:
        if st.button("Nạp dữ liệu demo (tập kiểm thử)", type="primary"):
            with st.spinner("Đang nạp và chấm điểm..."):
                n = seed(conn, model)
            st.success(f"Đã nạp {n} lượt khám.")
            st.rerun()

    st.markdown("#### Kiểm tra trước khi gửi lên cổng liên thông")
    st.caption("Hồ sơ cổng trong app/portal_profiles.json là giả định minh họa. Chỉ dùng kết quả này sau khi đã "
               "đối chiếu hồ sơ cổng với đặc tả chính thức. Hồ sơ đang có cảnh báo chưa xử lý sẽ không đạt.")
    profiles = portal.load_profiles()
    pick = st.selectbox("Hồ sơ cổng", sorted(profiles), format_func=lambda n: profiles[n]["ten"],
                        key="portal_profile")
    if st.button("Kiểm tra trước khi gửi", key="portal_check"):
        profile, rows, errors = portal.prepare(conn, pick)
        st.session_state["portal_result"] = (pick, profile, rows, errors)
    res = st.session_state.get("portal_result")
    if res and res[0] == pick:
        _, profile, rows, errors = res
        c1, c2 = st.columns(2)
        c1.metric("Lượt khám trong hồ sơ cổng", len(rows))
        c2.metric("Số lỗi", len(errors))
        if errors:
            st.dataframe(pd.DataFrame(errors).rename(columns={"Id": "Mã lượt khám", "truong": "Trường",
                                                             "loi": "Lỗi"}),
                         use_container_width=True, hide_index=True)
        else:
            st.success("Tất cả hồ sơ đạt kiểm tra của hồ sơ cổng này.")
            st.download_button("Tải file xuất CSV", data=portal.to_csv_text(rows, profile),
                               file_name=f"{pick}.csv", mime="text/csv")
