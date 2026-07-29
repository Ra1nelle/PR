import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import requests
from streamlit_autorefresh import st_autorefresh

# -----------------------------------------------------------------------------
# Page Configuration & Radial Glow Background
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="IoT Energy Monitor",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
    <style>
    /* Radial Glow Background */
    .stApp {
        background: radial-gradient(circle at center, #1e293b 0%, #090d16 100%);
    }
    
    /* Sidebar Background */
    section[data-testid="stSidebar"] {
        background-color: rgba(9, 13, 22, 0.9);
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Firebase Realtime Database Functions (Central Shared Storage)
# -----------------------------------------------------------------------------
def read_firebase_data(url):
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, dict):
                return {
                    "connected": True,
                    "voltage": float(data.get("voltage", 0.0)),
                    "current": float(data.get("current", 0.0)),
                    "power": float(data.get("power", 0.0)),
                    "energy": float(data.get("energy", 0.0)),
                    "frequency": float(data.get("frequency", 0.0)),
                    "pf": float(data.get("pf", 0.0))
                }
    except Exception:
        pass

    return {
        "connected": False,
        "voltage": 0.0,
        "current": 0.0,
        "power": 0.0,
        "energy": 0.0,
        "frequency": 0.0,
        "pf": 0.0
    }

def get_shared_system_state(base_url):
    # Reads shared timer, baseline, and bill predictions from Firebase
    state_url = base_url.rsplit('/', 1)[0] + "/system_state.json"
    try:
        response = requests.get(state_url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, dict):
                return data
    except Exception:
        pass
    return None

def update_shared_system_state(base_url, start_ts, baseline_kwh, prediction=None):
    # Writes timer, baseline, and predictions directly to Firebase
    state_url = base_url.rsplit('/', 1)[0] + "/system_state.json"
    payload = {
        "start_timestamp": start_ts,
        "baseline_energy": baseline_kwh,
        "prediction": prediction
    }
    try:
        requests.put(state_url, json=payload, timeout=3)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Real-Time Auto Refresh Setup
# -----------------------------------------------------------------------------
st_autorefresh(interval=1000, limit=None, key="live_firebase_refresh")

# -----------------------------------------------------------------------------
# App Header
# -----------------------------------------------------------------------------
st.title("⚡ web ng mga kupal na og")
st.caption("ESP32 + FIREBASE MODE — Fully Synchronized Telemetry & Bill Predictor")

# -----------------------------------------------------------------------------
# Sidebar Controls & Cloud Configuration
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Cloud Database Endpoint")
firebase_url = st.sidebar.text_input(
    "Firebase Realtime DB URL", 
    value="https://prnamin-8823e-default-rtdb.asia-southeast1.firebasedatabase.app/sensor_data.json"
)
kwh_rate = st.sidebar.number_input("Electricity Rate (₱/kWh)", value=11.50, step=0.10)

# Fetch sensor telemetry from Firebase
pzem_data = read_firebase_data(firebase_url)

# Raw cloud values
voltage_val = pzem_data["voltage"]
current_val = pzem_data["current"]
power_val = pzem_data["power"]
raw_energy_val = pzem_data["energy"]
freq_val = pzem_data["frequency"]
pf_val = pzem_data["pf"]

# Fetch shared system state & shared predictions from Firebase
shared_state = get_shared_system_state(firebase_url)

if shared_state is not None:
    start_timestamp = float(shared_state.get("start_timestamp", time.time()))
    baseline_energy = float(shared_state.get("baseline_energy", 0.0))
    shared_prediction = shared_state.get("prediction", None)
else:
    # First-time fallback if state doesn't exist in Firebase yet
    start_timestamp = time.time()
    baseline_energy = raw_energy_val
    shared_prediction = None
    update_shared_system_state(firebase_url, start_timestamp, baseline_energy, None)

st.sidebar.markdown("---")
st.sidebar.subheader("🔄 System Controls")

# RESET BUTTON: Clears timers, baseline kWh, and predictions across ALL connected devices
if st.sidebar.button("🔄 Reset System, Timer & kWh", use_container_width=True):
    new_start_ts = time.time()
    new_baseline_kwh = raw_energy_val
    update_shared_system_state(firebase_url, new_start_ts, new_baseline_kwh, None)
    st.rerun()

# Total Elapsed Seconds calculation using Firebase shared timestamp
total_seconds = max(0.0, time.time() - start_timestamp)

# Formatted runtime
hrs = int(total_seconds // 3600)
mins = int((total_seconds % 3600) // 60)
secs = int(total_seconds % 60)
formatted_time = f"{hrs:02d}h {mins:02d}m {secs:02d}s"

# Calculate Session Energy (Adjusted relative to the Firebase baseline)
if raw_energy_val > 0.0:
    session_kwh = max(0.0, raw_energy_val - baseline_energy)
else:
    session_kwh = (power_val * (total_seconds / 3600.0)) / 1000.0

estimated_cost = session_kwh * kwh_rate

# -----------------------------------------------------------------------------
# Mock Historical Data Setup
# -----------------------------------------------------------------------------
hours = [f"{h:02d}:00" for h in range(24)]
np.random.seed(42)
mock_power_curve = np.random.randint(0, 30, size=24)
chart_df = pd.DataFrame({"Time": hours, "Power": mock_power_curve})

# -----------------------------------------------------------------------------
# Dashboard Navigation Tabs
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["⚡ Live Telemetry", "📈 Consumption Trends", "⚙️ Hardware & Settings"])

# --- TAB 1: LIVE TELEMETRY ---
with tab1:
    st.subheader("📊 Live Telemetry & Operating Time")
    
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Voltage", f"{voltage_val:.1f} V")
    m2.metric("Current", f"{current_val:.2f} A")
    m3.metric("Active Power", f"{power_val:.1f} W")
    m4.metric("Session Energy", f"{session_kwh:.4f} kWh")
    m5.metric("Active Time", formatted_time)
    m6.metric("Frequency", f"{freq_val:.1f} Hz")

    st.markdown("---")

    col_gauge, col_cards = st.columns([1, 1])

    with col_gauge:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=power_val,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Active Load (Watts)", 'font': {'size': 16}},
            gauge={
                'axis': {'range': [0, 2500]},
                'bar': {'color': "#2cc0e9"},
                'steps': [
                    {'range': [0, 500], 'color': "rgba(0, 255, 0, 0.15)"},
                    {'range': [500, 1500], 'color': "rgba(255, 255, 0, 0.15)"},
                    {'range': [1500, 2500], 'color': "rgba(255, 0, 0, 0.15)"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 2200
                }
            }
        ))
        fig_gauge.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font={'color': "white"},
            height=300,
            margin=dict(l=20, r=20, t=60, b=20)
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_cards:
        st.markdown("### Hardware Diagnostics & Automatic Monthly Predictor")
        
        with st.container(border=True):
            st.markdown(f"💰 **Live Session Energy Cost:** **₱{estimated_cost:.2f}**")
            st.caption(f"Calculated using ₱{kwh_rate:.2f}/kWh against session energy ({session_kwh:.4f} kWh)")

        with st.container(border=True):
            # PREDICT BUTTON: Calculates prediction and saves it to Firebase
            if st.button("⚡ Predict Monthly Bill from Live Load", use_container_width=True):
                daily_kwh = (power_val * 24.0) / 1000.0
                monthly_kwh = daily_kwh * 30.0
                monthly_cost = monthly_kwh * kwh_rate
                
                new_prediction = {
                    "power_w": power_val,
                    "daily_kwh": daily_kwh,
                    "monthly_kwh": monthly_kwh,
                    "monthly_cost": monthly_cost
                }
                
                # Push the new prediction to Firebase so phone updates immediately
                update_shared_system_state(firebase_url, start_timestamp, baseline_energy, new_prediction)
                st.rerun()

            # Display prediction fetched directly from shared Firebase state
            if shared_prediction is not None and isinstance(shared_prediction, dict):
                p_res = shared_prediction
                st.markdown(f"📅 **Predicted Monthly Bill:** **₱{float(p_res.get('monthly_cost', 0.0)):,.2f}**")
                st.caption(f"Based on live load ({float(p_res.get('power_w', 0.0)):.1f}W) running 24 hrs/day for 30 days @ ₱{kwh_rate:.2f}/kWh")
            else:
                st.markdown("📅 **Predicted Monthly Bill:** *Not calculated yet*")
                st.caption("Click the button above to generate a prediction based on existing live telemetry.")

        with st.container(border=True):
            if pzem_data["connected"]:
                st.success(f"🔌 **Firebase Telemetry:** CONNECTED & SYNCED")
            else:
                st.error(f"🔌 **Firebase Telemetry:** DISCONNECTED / SEARCHING")
            st.caption("Polling live JSON data directly from Firebase Realtime Database")

# --- TAB 2: CONSUMPTION TRENDS ---
with tab2:
    st.subheader("📉 Historical Trends over Time")
    
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=chart_df['Time'],
        y=chart_df['Power'],
        mode='lines+markers',
        name='Active Power (W)',
        line=dict(color='#38bdf8', width=2),
        marker=dict(size=6)
    ))
    
    fig_line.update_layout(
        title="24-Hour Active Power Curve",
        xaxis_title="Time",
        yaxis_title="Active Power (Watts)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8"),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#334155")
    )
    
    st.plotly_chart(fig_line, use_container_width=True)

# --- TAB 3: HARDWARE & SETTINGS ---
with tab3:
    st.subheader("⚙️ System Configuration & Cloud Info")
    st.write("Manage cloud endpoint URLs, polling interval rates, and calibration settings.")