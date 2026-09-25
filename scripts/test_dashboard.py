"""Exercise displayed results and both filters without a running browser server."""
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=20).run()
assert not app.exception and not app.error
assert app.metric[0].value == '1,526,612'
assert app.metric[2].value == '0.0766'
assert app.metric[3].value == '0.1012'
app.selectbox[0].select('TEXAS').run()
app.selectbox[1].select('2024').run()
assert not app.exception and not app.error
expected = pd.read_csv(ROOT / 'dashboard_data/capture.csv', dtype={'year': str})
expected = expected[(expected.state == 'TEXAS') & (expected.year == '2024')]
assert app.dataframe[1].value.crossing_years.tolist() == expected.crossing_years.tolist()
assert app.dataframe[1].value.captured_positive_years.tolist() == expected.captured_positive_years.tolist()
print('Dashboard passed: headline values, state/year filters, displayed numerator and denominator.')

