import streamlit as st
import pandas as pd
import math
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict

# ------------------ Basisconfig ------------------
st.set_page_config(page_title="SKC • Shift Kalender Calculator", page_icon="🗓️", layout="wide")

# ------------------ Thema / CSS ------------------
st.markdown("""
<style>
:root{
  --bg:#ffffff;
  --panel: rgba(240,242,246,0.7);
  --ink:#111111;
  --muted:#666;
  --accent:#ffd84d;
  --redbg:#fde8e8;
  --bluebg:#e8f0ff;
  --greenbg:#e6f6ee;
  --purplebg:#f1e6fa;
  --tableHeader:#f3f5f9;
  --border:#e1e5ef;
}
.stApp, .stApp header, .block-container { background-color: var(--bg) !important; color: var(--ink) !important; }
[data-testid="stHeader"] { background-color: var(--bg) !important; }
h1,h2,h3,h4 { color: var(--ink) !important; }

.skc-logo { font-size:64px; font-weight:900; letter-spacing:2px; line-height:0.9;
  color:#d80000; -webkit-text-stroke: 2px #ffffff; text-shadow: 0 0 1px #fff; margin:0;}
.skc-sub { font-size: 12px; text-align:center; margin-top:2px; 
  color:#111; opacity:.85; font-weight:500; white-space:nowrap; display:block;}
.skc-band{height:4px;background:var(--accent);margin:10px 0 16px;border-radius:2px;}

.panel{ background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 12px 14px; backdrop-filter: blur(2px); }
.weekwrap{ position: relative; }
.weeknr{ position:absolute; right:8px; top:8px; font-size:12px; color:var(--muted); }

.card{ background:#fff; border:1px solid var(--border); border-radius: 10px; padding:10px 12px; }
.card strong{ display:block; font-size: 18px; }

@media print {
  .no-print { display:none !important; }
  .print-only { display:block !important; }
}
.print-only { display:none; }
</style>
""", unsafe_allow_html=True)

# ------------------ Kleuren ------------------
COLORS = {
    "bg_shift": "#fde8e8",
    "bg_bijs": "#e8f0ff",
    "bg_free": "#e6f6ee",
    "bg_night": "#f1e6fa",
    "text": "#111111",
}

# ------------------ Helpers ------------------
DUTCH_DAYNAMES = {0:"maandag",1:"dinsdag",2:"woensdag",3:"donderdag",4:"vrijdag",5:"zaterdag",6:"zondag"}
MONTH_NL = {1:"januari",2:"februari",3:"maart",4:"april",5:"mei",6:"juni",7:"juli",8:"augustus",9:"september",10:"oktober",11:"november",12:"december"}

def fmt_dutch_range(dmin, dmax):
    dmin = dmin.date() if isinstance(dmin, pd.Timestamp) else dmin
    dmax = dmax.date() if isinstance(dmax, pd.Timestamp) else dmax
    if dmin.month == dmax.month:
        return f"{dmin.day}–{dmax.day} {MONTH_NL[dmin.month]}"
    return f"{dmin.day} {MONTH_NL[dmin.month]} – {dmax.day} {MONTH_NL[dmax.month]}"

def parse_hhmm(s: str) -> time:
    if not s: return None
    h,m = s.split(":"); return time(int(h), int(m))

def hours_between(start: time, end: time) -> float:
    dt0 = datetime.combine(date.today(), start)
    dt1 = datetime.combine(date.today(), end)
    if dt1 <= dt0: dt1 += timedelta(days=1)
    return (dt1 - dt0).total_seconds()/3600.0

def ceil_to_min(hours: float) -> float:
    if hours is None: return 0.0
    return math.ceil(hours * 60.0) / 60.0

def month_dates(year: int, month: int):
    d0 = date(year, month, 1); d1 = d0 + relativedelta(months=1); d = d0
    while d < d1:
        yield d; d += timedelta(days=1)

def fmt_date(d, fmt="%d-%m-%Y") -> str:
    if isinstance(d, pd.Timestamp): d = d.date()
    return d.strftime(fmt)

def month_key(y: int, m: int) -> str: return f"{y}-{m:02d}"

def normalize_codes(s: str) -> str:
    if not s: return ""
    s = s.strip().lower().replace(" ", "").replace(",", "+")
    while "++" in s: s = s.replace("++", "+")
    return s.strip("+")

def split_codes(s: str): return [c for c in normalize_codes(s).split("+") if c] if s else []

def ensure_session():
    if "shiftcodes" not in st.session_state:
        st.session_state.shiftcodes = {
            "bijs":{"start":None,"end":None,"pauze":0,"label":"Bijscholing"},
            "fdrecup":{"start":None,"end":None,"pauze":0,"label":"Betaalde feestdag"},
        }
    if "months" not in st.session_state: st.session_state.months = {}
    if "calc" not in st.session_state: st.session_state.calc = {}
    if "nav" not in st.session_state: st.session_state.nav = {}
ensure_session()

# ------------------ Header ------------------
hc1,hc2 = st.columns([5,2])
with hc1:
    st.markdown('<div class="skc-logo">SKC</div>', unsafe_allow_html=True)
    st.markdown('<span class="skc-sub">Shift Kalender Calculator</span>', unsafe_allow_html=True)
with hc2:
    st.button("🖨️ Afdrukken", on_click=lambda: st.markdown("<script>window.print()</script>", unsafe_allow_html=True))
st.markdown('<div class="skc-band"></div>', unsafe_allow_html=True)

# ------------------ Maandkiezer ------------------
today = date.today()
c_prev,c_today,c_next,c_year,c_month = st.columns([1,1,1,2,2])
year = c_year.number_input("Jaar",min_value=2000,max_value=2100,value=st.session_state.nav.get("year",today.year))
month = c_month.selectbox("Maand", list(range(1,13)), index=(st.session_state.nav.get("month",today.month)-1),
                          format_func=lambda m: MONTH_NL[m])
if c_prev.button("←"): d=date(int(year),int(month),1)-relativedelta(months=1); year,month=d.year,d.month
if c_today.button("Vandaag"): year,month=today.year,today.month
if c_next.button("→"): d=date(int(year),int(month),1)+relativedelta(months=1); year,month=d.year,d.month
st.session_state.nav.update({"year":int(year),"month":int(month)})
mkey=month_key(int(year),int(month))

# ------------------ Init maanddata ------------------
def init_month_df(y:int,m:int):
    return pd.DataFrame([{"Datum":pd.to_datetime(d),"Dag":DUTCH_DAYNAMES[d.weekday()],"Codes":"","BIJSuren":0.0,"OverurenMin":0} for d in month_dates(y,m)])
if mkey not in st.session_state.months: st.session_state.months[mkey]=init_month_df(int(year),int(month))
df=st.session_state.months[mkey].copy()

# ------------------ Berekening ------------------
def calc_shift_hours_for_code(code:str)->float:
    if code=="bijs": return 0.0
    info=st.session_state.shiftcodes.get(code); 
    if not info: return 0.0
    if not info["start"] or not info["end"]: return 0.0
    bruto=hours_between(parse_hhmm(info["start"]),parse_hhmm(info["end"]))
    return ceil_to_min(max(0.0, bruto-(info["pauze"]/60.0)))

def calc_row_hours(codes:str)->float: return ceil_to_min(sum(calc_shift_hours_for_code(c) for c in split_codes(codes)))
def recompute(df_in:pd.DataFrame)->pd.DataFrame:
    out=df_in.copy()
    out["ShiftUren"]=out["Codes"].apply(calc_row_hours)
    out["BIJSuren"]=out["BIJSuren"].apply(lambda x:ceil_to_min(float(x)))
    out["OverurenUur"]=out["OverurenMin"].apply(lambda m:ceil_to_min(float(m)/60.0))
    out["TotaalUren"]=(out["ShiftUren"]+out["BIJSuren"]+out["OverurenUur"]).round(2)
    return out

if st.button("✅ Bereken / Update") or mkey not in st.session_state.calc:
    st.session_state.months[mkey]=df.copy()
    st.session_state.calc[mkey]=recompute(df)
calc_df=st.session_state.calc.get(mkey,recompute(df)).copy()

# ------------------ Overzicht per week ------------------
def row_style(row):
    codes=split_codes(row["Codes"])
    if "n10" in codes: bg=COLORS["bg_night"]
    elif float(row["TotaalUren"])==0.0: bg=COLORS["bg_free"]
    else: bg=COLORS["bg_shift"]
    return [f"background-color:{bg}; color:{COLORS['text']}"]*len(row)

iso=calc_df["Datum"].dt.isocalendar(); calc_df["Week"]=iso.week; calc_df["Jaar"]=iso.year
for (jaar,week),groep in calc_df.groupby(["Jaar","Week"]):
    dmin,dmax=groep["Datum"].min(),groep["Datum"].max()
    st.markdown(f"### Week {week} ({fmt_dutch_range(dmin,dmax)})")
    st.dataframe(groep[["Datum","Dag","Codes","ShiftUren","BIJSuren","OverurenUur","TotaalUren"]].style.apply(row_style,axis=1),
                 use_container_width=True,hide_index=True)

# ------------------ Samenvatting ------------------
st.markdown("## Samenvatting")
c1,c2,c3=st.columns(3)
c1.markdown(f'<div class="card"><span>Totaal</span><strong>{calc_df["TotaalUren"].sum():.2f} u</strong></div>',unsafe_allow_html=True)
c2.markdown(f'<div class="card"><span>Overuren</span><strong>{calc_df["OverurenUur"].sum():.2f} u</strong></div>',unsafe_allow_html=True)
c3.markdown(f'<div class="card"><span>BIJS</span><strong>{calc_df["BIJSuren"].sum():.2f} u</strong></div>',unsafe_allow_html=True)
