from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text, URL

st.set_page_config(page_title="PKO Shipping", page_icon="🚚", layout="wide")


# ---- Look & feel: sky banner, optional background photo, optional logo ----
import base64
from pathlib import Path

HERE = Path(__file__).parent


def img_to_base64(path):
    return base64.b64encode(path.read_bytes()).decode()


SKY_BANNER = """
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 220' preserveAspectRatio='xMidYMid slice'>
  <defs>
    <linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0' stop-color='#0D0D0D'/><stop offset='1' stop-color='#2B2B2B'/>
    </linearGradient>
    <linearGradient id='trail' x1='0' x2='1'>
      <stop offset='0' stop-color='#DA2829' stop-opacity='0'/><stop offset='1' stop-color='#DA2829' stop-opacity='0.95'/>
    </linearGradient>
  </defs>
  <rect width='1200' height='220' fill='url(#bg)'/>
  <path d='M0 220 L0 200 C 300 150, 700 230, 1200 120 L1200 220 Z' fill='#DA2829' opacity='0.9'/>
  <path d='M0 220 C 320 185, 760 245, 1200 165 L1200 220 Z' fill='#B71C1C'/>
  <rect x='700' y='92' width='210' height='4' rx='2' fill='url(#trail)'/>
  <rect x='740' y='104' width='170' height='3' rx='1.5' fill='url(#trail)'/>
  <g transform='translate(900 70) rotate(-8)' fill='#fff'>
    <path d='M0 30 C 0 18, 20 14, 40 14 L 190 14 C 215 14, 235 22, 240 30 C 235 38, 215 44, 190 44 L 40 44 C 20 44, 0 40, 0 30 Z'/>
    <path d='M30 16 L 10 -22 L 32 -22 L 62 16 Z' fill='#DA2829'/>
    <path d='M8 30 L -16 18 L -8 30 L -16 42 Z' opacity='0.9'/>
    <path d='M95 30 L 150 30 L 110 86 L 88 86 Z'/>
    <path d='M100 16 L 135 16 L 115 -14 L 102 -14 Z' opacity='0.85'/>
    <rect x='120' y='44' width='22' height='9' rx='4' opacity='0.9'/>
    <g fill='#0D0D0D' opacity='0.6'>
      <rect x='70' y='22' width='6' height='6' rx='2'/><rect x='84' y='22' width='6' height='6' rx='2'/>
      <rect x='98' y='22' width='6' height='6' rx='2'/><rect x='155' y='22' width='6' height='6' rx='2'/>
      <rect x='169' y='22' width='6' height='6' rx='2'/><path d='M212 20 L 228 24 L 230 30 L 212 30 Z'/>
    </g>
    <rect x='40' y='33' width='150' height='3' fill='#DA2829'/>
  </g>
</svg>
"""
banner_b64 = base64.b64encode(SKY_BANNER.encode()).decode()

css = f"""
<style>
.pko-banner {{
    background: url("data:image/svg+xml;base64,{banner_b64}") center / cover no-repeat;
    border-radius: 16px; padding: 38px 32px 48px; margin-bottom: 1rem; color: white;
}}
.pko-banner h1 {{ color: white; margin: 0; font-size: 2.2rem; }}
.pko-banner p  {{ color: #F2F2F2; margin: 4px 0 0; font-size: 1.05rem; }}
[data-testid="stSidebar"] {{ border-right: 4px solid #DA2829; }}
[data-testid="stMetric"] {{
    background: #FFFFFF; border: 1px solid #E6E6E6; border-left: 6px solid #DA2829;
    border-radius: 12px; padding: 14px 18px; box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}}
[data-testid="stMetricValue"] {{ color: #0D0D0D; font-weight: 700; }}
h2, h3 {{ color: #0D0D0D; }}
hr {{ border-color: #DA2829 !important; opacity: 0.4; }}
"""

# Optional: put a photo called background.jpg in the folder to use it as the page background
bg = HERE / "background.jpg"
if bg.exists():
    css += f"""
.stApp {{
    background: linear-gradient(rgba(255,255,255,0.92), rgba(255,255,255,0.92)),
                url("data:image/jpeg;base64,{img_to_base64(bg)}") center / cover fixed;
}}
"""
css += "</style>"
st.markdown(css, unsafe_allow_html=True)

# Optional: put PKO's logo as logo.png in the folder to show it in the sidebar
logo = HERE / "logo.png"
if logo.exists():
    st.sidebar.image(str(logo), width=180)


def banner(title, subtitle="Another day, another package 📦"):
    st.markdown(f'<div class="pko-banner"><h1>{title}</h1><p>{subtitle}</p></div>',
                unsafe_allow_html=True)


# ---- Connect to MySQL (once, then reuse) ----
@st.cache_resource
def get_engine():
    cfg = st.secrets["mysql"]
    # Cloud databases (like Aiven) need an encrypted (SSL) connection
    connect_args = {}
    if "ssl_ca" in cfg:
        connect_args["ssl"] = {"ca": str(Path(__file__).parent / cfg["ssl_ca"])}
    return create_engine(URL.create(
        "mysql+pymysql",
        username=cfg["user"], password=cfg["password"],
        host=cfg["host"], port=int(cfg["port"]), database=cfg["database"],
    ), connect_args=connect_args, pool_pre_ping=True)


# PKO brand colours for charts
RED, BLACK, GREY = "#DA2829", "#0D0D0D", "#9E9E9E"
STATUS_COLORS = {
    "Delivered": BLACK, "In Transit": RED, "Out for Delivery": "#F28B82",
    "Picked Up": "#6B6B6B", "Booked": "#C9C9C9", "Cancelled": "#7A0C0C",
}


def style(fig):
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                      font_color=BLACK, margin=dict(t=10, l=10, r=10, b=10))
    return fig


def sql(query, params=None):
    return pd.read_sql(text(query), get_engine(), params=params)


# ---- Login ----
import hashlib
import hmac


def check_password(password, stored_hash):
    """Hash the typed password with the same salt and compare it to the stored hash."""
    salt_hex, digest_hex = stored_hash.split("$")
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(test.hex(), digest_hex)


if "user" not in st.session_state:
    banner("🔐 Staff login", "PKO Shipping staff only")

    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("Log in", type="primary")

    if login:
        found = sql("""
            SELECT username, full_name, role, password_hash
            FROM users
            WHERE username = :u AND active = TRUE
        """, {"u": username.strip().lower()})

        if not found.empty and check_password(password, found.iloc[0]["password_hash"]):
            u = found.iloc[0]
            st.session_state["user"] = {"username": u["username"], "name": u["full_name"], "role": u["role"]}
            st.rerun()
        else:
            st.error("Wrong username or password.")   # never say WHICH one was wrong

    st.stop()   # nothing below this line runs until someone logs in

user = st.session_state["user"]


# ---- Sidebar menu (depends on the user's role) ----
st.sidebar.title("🚚 PKO Shipping")
st.sidebar.caption(f"Signed in as **{user['name']}** ({user['role']})")

if user["role"] == "admin":
    pages = ["Dashboard", "New Shipment", "Update Status", "Track Shipment", "All Shipments"]
else:
    pages = ["New Shipment", "Update Status", "Track Shipment"]

page = st.sidebar.radio("Menu", pages)

if st.sidebar.button("Log out"):
    del st.session_state["user"]
    st.rerun()


# ---- Dashboard page ----
if page == "Dashboard":
    banner("✈️ PKO Shipping Dashboard")

    # KPI cards
    kpi = sql("""
        SELECT COUNT(*)                                                AS total,
               SUM(status = 'Delivered')                               AS delivered,
               SUM(status NOT IN ('Delivered', 'Cancelled'))           AS active,
               SUM(CASE WHEN status <> 'Cancelled' THEN cost_ghs END)  AS revenue
        FROM shipments
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total shipments", int(kpi["total"]))
    c2.metric("Active", int(kpi["active"]))
    c3.metric("Delivered", int(kpi["delivered"]), f"{kpi['delivered'] / kpi['total']:.0%} of total")
    c4.metric("Revenue (GH₵)", f"{float(kpi['revenue']):,.2f}")

    st.divider()

    # Row 1: revenue by service + status breakdown
    left, right = st.columns(2)

    with left:
        st.subheader("Revenue by service")
        rev = sql("""
            SELECT service, SUM(cost_ghs) AS revenue
            FROM shipments
            WHERE status <> 'Cancelled'
            GROUP BY service
            ORDER BY revenue DESC
        """)
        fig = px.bar(rev, x="service", y="revenue", text_auto=",.0f",
                     labels={"service": "", "revenue": "Revenue (GH₵)"},
                     color_discrete_sequence=[RED])
        st.plotly_chart(style(fig))

    with right:
        st.subheader("Shipments by status")
        stat = sql("SELECT status, COUNT(*) AS shipments FROM shipments GROUP BY status")
        fig = px.pie(stat, names="status", values="shipments", hole=0.45,
                     color="status", color_discrete_map=STATUS_COLORS)
        st.plotly_chart(style(fig))

    # Row 2: monthly bookings + busiest routes
    left, right = st.columns(2)

    with left:
        st.subheader("Bookings per month")
        monthly = sql("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') AS month, COUNT(*) AS bookings
            FROM shipments
            GROUP BY month
            ORDER BY month
        """)
        fig = px.line(monthly, x="month", y="bookings", markers=True,
                      labels={"month": "", "bookings": "Bookings"},
                      color_discrete_sequence=[RED])
        fig.update_traces(line_width=3, marker_size=9, marker_color=BLACK)
        st.plotly_chart(style(fig))

    with right:
        st.subheader("Top 5 busiest routes")
        routes = sql("""
            SELECT CONCAT(origin, ' → ', destination) AS route, COUNT(*) AS shipments
            FROM shipments
            GROUP BY route
            ORDER BY shipments DESC
            LIMIT 5
        """)
        fig = px.bar(routes, x="shipments", y="route", orientation="h", text_auto=True,
                     labels={"route": "", "shipments": "Shipments"},
                     color_discrete_sequence=[BLACK])
        fig.update_yaxes(categoryorder="total ascending")
        st.plotly_chart(style(fig))


# ---- New Shipment page ----
elif page == "New Shipment":
    banner("📦 New Shipment", "Book a parcel in under a minute")

    CITIES = ["Accra", "Kumasi", "Takoradi", "Tamale", "Cape Coast", "Ho", "Sunyani"]
    RATES = {"Express": 25, "Standard": 15, "Economy": 10}   # GH₵ per kg
    BASE_FEE = 20

    with st.form("new_shipment", clear_on_submit=True):
        st.subheader("Customer")
        c1, c2 = st.columns(2)
        name = c1.text_input("Customer name *")
        phone = c2.text_input("Phone number", placeholder="e.g. 0241234567")

        st.subheader("Parcel")
        c1, c2 = st.columns(2)
        origin = c1.selectbox("From *", CITIES)
        destination = c2.selectbox("To *", CITIES, index=1)
        service = c1.selectbox("Service *", list(RATES))
        weight = c2.number_input("Weight (kg) *", min_value=0.1, value=1.0, step=0.5)

        submitted = st.form_submit_button("Book shipment", type="primary")

    if submitted:
        # 1. Clean the inputs (same rules as the cleaning notebook)
        name = " ".join(name.split()).title()   # remove extra spaces, Capitalise Each Word
        phone = phone.replace(" ", "").replace("+233", "0")

        # 2. Check them before touching the database
        errors = []
        if not name:
            errors.append("Customer name is required.")
        if origin == destination:
            errors.append("'From' and 'To' must be different cities.")
        if phone and not (phone.isdigit() and len(phone) == 10 and phone.startswith("0")):
            errors.append("Phone number must be 10 digits and start with 0, e.g. 0241234567.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            # 3. Work out the price with PKO's pricing rule
            cost = round(BASE_FEE + weight * RATES[service], 2)
            now = datetime.now()

            # 4. Save the shipment AND its first history row together
            with get_engine().begin() as conn:
                next_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM shipments")).scalar()
                tracking = f"PKO{now:%y}{next_id:06d}"

                result = conn.execute(text("""
                    INSERT INTO shipments
                        (tracking_no, customer_name, customer_phone, origin, destination,
                         service, weight_kg, cost_ghs, status, created_at, updated_at)
                    VALUES
                        (:tracking, :name, :phone, :origin, :destination,
                         :service, :weight, :cost, 'Booked', :now, :now)
                """), {"tracking": tracking, "name": name, "phone": phone or None,
                       "origin": origin, "destination": destination, "service": service,
                       "weight": weight, "cost": cost, "now": now})

                conn.execute(text("""
                    INSERT INTO status_history (shipment_id, status, note, changed_at)
                    VALUES (:sid, 'Booked', 'Shipment booked', :now)
                """), {"sid": result.lastrowid, "now": now})

            st.success(f"✅ Shipment booked! Tracking number: **{tracking}**")
            st.info(f"{origin} → {destination} · {service} · {weight} kg · **GH₵ {cost:,.2f}**")
            st.balloons()


# ---- Update Status page ----
elif page == "Update Status":
    banner("🔄 Update Status", "Move a parcel along its journey")

    FLOW = ["Booked", "Picked Up", "In Transit", "Out for Delivery", "Delivered"]

    # Show the message from the last update (it survives the page refresh)
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    active = sql("""
        SELECT id, tracking_no, customer_name, origin, destination, status
        FROM shipments
        WHERE status NOT IN ('Delivered', 'Cancelled')
        ORDER BY created_at DESC
    """)

    if active.empty:
        st.info("No active shipments. Everything has been delivered! 🎉")
    else:
        labels = {
            row.tracking_no: f"{row.tracking_no} — {row.customer_name} ({row.origin} → {row.destination}) · {row.status}"
            for row in active.itertuples()
        }
        tracking = st.selectbox("Choose a shipment (type to search)", list(labels), format_func=labels.get)
        shipment = active[active["tracking_no"] == tracking].iloc[0]
        current = shipment["status"]

        # Business rule: only the NEXT step is allowed, and you can only cancel before it is in transit
        options = [FLOW[FLOW.index(current) + 1]]
        if current in ("Booked", "Picked Up"):
            options.append("Cancelled")

        st.write(f"Current status: **{current}**")

        with st.form("update_status"):
            new_status = st.radio("Move to", options, horizontal=True)
            note = st.text_input("Note (optional)", placeholder="e.g. Driver: Kofi, left Accra depot")
            submitted = st.form_submit_button("Update status", type="primary")

        if submitted:
            now = datetime.now()
            with get_engine().begin() as conn:
                # "AND status = :current" stops two staff updating the same parcel at the same time
                result = conn.execute(text("""
                    UPDATE shipments
                    SET status = :new_status, updated_at = :now
                    WHERE id = :sid AND status = :current
                """), {"new_status": new_status, "now": now,
                       "sid": int(shipment["id"]), "current": current})

                if result.rowcount == 1:
                    conn.execute(text("""
                        INSERT INTO status_history (shipment_id, status, note, changed_at)
                        VALUES (:sid, :status, :note, :now)
                    """), {"sid": int(shipment["id"]), "status": new_status,
                           "note": note.strip() or None, "now": now})

            if result.rowcount == 1:
                st.session_state["flash"] = f"✅ {tracking} is now **{new_status}**"
                st.rerun()
            else:
                st.warning("Someone else just updated this shipment. Please choose it again.")


# ---- Track Shipment page ----
elif page == "Track Shipment":
    banner("🔎 Track Shipment", "Where is my parcel?")

    FLOW = ["Booked", "Picked Up", "In Transit", "Out for Delivery", "Delivered"]
    ICONS = {"Booked": "📝", "Picked Up": "📦", "In Transit": "✈️",
             "Out for Delivery": "🚚", "Delivered": "✅", "Cancelled": "❌"}

    tracking = st.text_input("Tracking number", placeholder="e.g. PKO26000501").strip().upper()

    if tracking:
        found = sql("SELECT * FROM shipments WHERE tracking_no = :t", {"t": tracking})

        if found.empty:
            st.error(f"No shipment found with tracking number **{tracking}**. Please check and try again.")
        else:
            s = found.iloc[0]

            c1, c2, c3 = st.columns(3)
            c1.metric("Status", f"{ICONS.get(s['status'], '')} {s['status']}")
            c2.metric("Route", f"{s['origin']} → {s['destination']}")
            c3.metric("Service", s["service"])

            st.write(f"**Customer:** {s['customer_name']}  ·  **Weight:** {float(s['weight_kg'])} kg  ·  "
                     f"**Cost:** GH₵ {float(s['cost_ghs']):,.2f}  ·  **Booked:** {s['created_at']:%d %b %Y, %H:%M}")

            # Progress bar
            if s["status"] == "Cancelled":
                st.error("This shipment was cancelled.")
            else:
                step = FLOW.index(s["status"]) + 1
                st.progress(step / len(FLOW), text=f"Step {step} of {len(FLOW)}: {s['status']}")

            # Journey timeline
            st.subheader("Journey")
            history = sql("""
                SELECT status, note, changed_at
                FROM status_history
                WHERE shipment_id = :sid
                ORDER BY changed_at
            """, {"sid": int(s["id"])})

            for h in history.itertuples():
                note = f" — {h.note}" if h.note else ""
                st.markdown(f"{ICONS.get(h.status, '•')} **{h.status}** · {h.changed_at:%d %b %Y, %H:%M}{note}")


# ---- All Shipments page ----
elif page == "All Shipments":
    banner("📋 All Shipments", "Search, filter and export")

    STATUSES = ["Booked", "Picked Up", "In Transit", "Out for Delivery", "Delivered", "Cancelled"]
    SERVICES = ["Express", "Standard", "Economy"]

    # ---- Filters ----
    c1, c2, c3 = st.columns([2, 2, 3])
    pick_status = c1.multiselect("Status", STATUSES)
    pick_service = c2.multiselect("Service", SERVICES)
    search = c3.text_input("Search name, phone or tracking no.")

    c1, c2 = st.columns(2)
    date_from = c1.date_input("Booked from", value=datetime(2026, 1, 1))
    date_to = c2.date_input("Booked to", value=datetime.now())

    # ---- Build the SQL step by step (always with :placeholders) ----
    query = """
        SELECT tracking_no, customer_name, customer_phone, origin, destination,
               service, weight_kg, cost_ghs, status, created_at, updated_at
        FROM shipments
        WHERE DATE(created_at) BETWEEN :date_from AND :date_to
    """
    params = {"date_from": date_from, "date_to": date_to}

    if pick_status:
        names = [f":st{i}" for i in range(len(pick_status))]
        query += f" AND status IN ({', '.join(names)})"
        params.update({f"st{i}": s for i, s in enumerate(pick_status)})

    if pick_service:
        names = [f":sv{i}" for i in range(len(pick_service))]
        query += f" AND service IN ({', '.join(names)})"
        params.update({f"sv{i}": s for i, s in enumerate(pick_service)})

    if search.strip():
        query += " AND (customer_name LIKE :q OR customer_phone LIKE :q OR tracking_no LIKE :q)"
        params["q"] = f"%{search.strip()}%"

    query += " ORDER BY created_at DESC"
    df = sql(query, params)

    # ---- Summary of what is showing ----
    c1, c2, c3 = st.columns(3)
    c1.metric("Shipments", f"{len(df):,}")
    c2.metric("Revenue (GH₵)", f"{df.loc[df['status'] != 'Cancelled', 'cost_ghs'].astype(float).sum():,.2f}")
    c3.metric("Total weight (kg)", f"{df['weight_kg'].astype(float).sum():,.1f}")

    # ---- The table ----
    st.dataframe(
        df,
        hide_index=True,
        column_config={
            "tracking_no": "Tracking no.",
            "customer_name": "Customer",
            "customer_phone": "Phone",
            "origin": "From",
            "destination": "To",
            "service": "Service",
            "weight_kg": st.column_config.NumberColumn("Weight (kg)", format="%.1f"),
            "cost_ghs": st.column_config.NumberColumn("Cost (GH₵)", format="%.2f"),
            "status": "Status",
            "created_at": st.column_config.DatetimeColumn("Booked", format="D MMM YYYY, HH:mm"),
            "updated_at": st.column_config.DatetimeColumn("Last update", format="D MMM YYYY, HH:mm"),
        },
    )

    # ---- Download to Excel ----
    import io
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Shipments")
    st.download_button(
        "⬇️ Download to Excel",
        data=buffer.getvalue(),
        file_name=f"PKO_shipments_{datetime.now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---- Other pages (coming in the next lessons) ----
else:
    banner(page)
    st.info("🚧 Coming soon — we'll build this page in the next lesson.")
