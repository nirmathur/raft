# dash.py
import requests
import streamlit as st


@st.cache(ttl=5)
def fetch_metrics():
    # Scrape the Prometheus /metrics endpoint
    resp = requests.get("http://localhost:8002/metrics")
    resp.raise_for_status()
    lines = [l for l in resp.text.splitlines() if l.startswith("raft_")]
    data = {}
    for line in lines:
        # each line is: metric_name value
        name, val = line.split(maxsplit=1)
        try:
            data[name] = float(val)
        except ValueError:
            data[name] = val
    return data


st.set_page_config(page_title="RAFT Live Metrics", layout="wide")
st.title("🔍 RAFT Live Metrics")

metrics = fetch_metrics()

# Display key metrics in columns
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Cycles Completed", metrics.get("raft_cycles_total", 0))
    st.metric("Proof Successes", metrics.get("raft_proof_pass_total", 0))

with col2:
    st.metric("Spectral Radius (ρ)", f"{metrics.get('raft_spectral_radius', 0):.3f}")
    st.metric("Energy Rate (J/s)", f"{metrics.get('raft_energy_rate_j_s', 0):.2e}")

with col3:
    st.metric("Proof Failures", metrics.get("raft_proof_fail_total", 0))
    st.metric("Median Cycle Latency (s)", f"{metrics.get('histogram_quantile',0):.3f}")

st.markdown("---")
st.write("### All Available Metrics")
st.dataframe(metrics, use_container_width=True)
