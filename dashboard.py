"""Portfolio view of verified, frozen research outputs; not a safety decision tool."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'dashboard_data'
st.set_page_config(page_title='Crossing risk | Pipeline & evidence', page_icon='🚦', layout='wide')
st.title('Crossing risk: pipeline & evidence')
st.caption('FRA grade crossings · September 2026 frozen research release · dbt + DuckDB engineering rebuild')
if not (DATA / 'facts.json').exists():
    st.error('Verified dashboard data is missing. Complete full parity and evaluation, then run scripts/export_dashboard.py.')
    st.stop()

facts = json.loads((DATA / 'facts.json').read_text())
panel = pd.read_csv(DATA / 'panel.csv')
capture = pd.read_csv(DATA / 'capture.csv', dtype={'year': str})
metrics = pd.read_csv(DATA / 'metrics.csv').set_index('model')
a, b, c, d = st.columns(4)
a.metric('Crossing-years · 2014–2025', f"{facts['crossing_years']:,}")
b.metric('Distinct crossings', f"{facts['crossings']:,}")
c.metric('AP · without history', f"{metrics.loc['hgb_exposure', 'average_precision']:.4f}")
d.metric('AP · with history', f"{metrics.loc['hgb_history', 'average_precision']:.4f}")
st.info('Engineering reproduction, not a new finding. The dbt panel matches every reference value. The dashboard uses a checked full-data snapshot, not the synthetic CI fixture.')

st.subheader('What is in the panel?')
state = st.selectbox('State', ['All'] + sorted(panel.state.dropna().unique().tolist()))
filtered = panel if state == 'All' else panel[panel.state == state]
annual = filtered.groupby('year', as_index=False)[['crossing_years', 'positive_crossing_years']].sum()
st.bar_chart(annual, x='year', y='crossing_years', color='#187C80')
st.dataframe(annual, hide_index=True, width='stretch')

st.subheader('How many positive crossing-years fall in the highest-scored 10%?')
year = st.selectbox('Evaluation year', ['All', '2024', '2025'])
selected = capture[(capture.state == state) & (capture.year == year)]
if selected.empty:
    st.warning('No evaluated crossing-years for this selection. Panel coverage and test coverage differ.')
else:
    display = selected[['model', 'crossing_years', 'positive_crossing_years',
                        'selected_crossing_years', 'captured_positive_years', 'capture']].copy()
    display['capture_percent'] = display.pop('capture') * 100
    st.dataframe(display, hide_index=True, width='stretch', column_config={
        'capture_percent': st.column_config.NumberColumn('Capture (%)', format='%.1f%%')})
    st.bar_chart(display, x='model', y='capture_percent', color='#187C80')
st.caption('Rank independently within each year and selected state using raw scores; select ceil(10% × annual rows), breaking ties by crossing ID. All years combines those annual selections, not one pooled ranking. Denominator: all positive crossing-years in the selection. Null capture means zero positives. State results are not shares of a national allocation.')

with st.expander('Definitions, verification and limits'):
    st.markdown('A crossing-year is one crossing observed for one prediction year. Positive means at least one Form 57 report, not a deduplicated accident. No report is not proof of no incident. Inventory revisions precede January 1; history excludes the prediction year. Revision dates do not establish historical public availability. State comparisons are descriptive, not geographic validation. This is not a deployed safety-ranking system.')
    st.warning('Exact reproduction preserves a legacy compact-date parsing quirk affecting warning-device masks in 1,158 crossing-years. Correcting the research baseline requires a separate version and evaluation; see docs/legacy-date-parsing.md.')
    st.json(facts)
st.download_button('Download displayed panel summary', annual.to_csv(index=False), 'panel_summary.csv', 'text/csv')
