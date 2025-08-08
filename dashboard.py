import dash
from dash import dcc, html
import plotly.graph_objs as go
import pandas as pd
import sqlite3
from dash.dependencies import Input, Output

DB_NAME = 'halo_heartbeats.db'
TABLE_NAME = 'heartbeats'

# Load data from SQLite
def load_data():
    conn = sqlite3.connect(DB_NAME)
    query = f"SELECT timestamp, name, site, C, RH, [P-hPa], CO2cal, TVOC, [PM2.5], PM10, CO, AQI FROM {TABLE_NAME} ORDER BY timestamp"
    df = pd.read_sql_query(query, conn)
    conn.close()
    # Convert to float if possible
    df['C'] = pd.to_numeric(df['C'], errors='coerce')
    df['RH'] = pd.to_numeric(df['RH'], errors='coerce')
    df['P-hPa'] = pd.to_numeric(df['P-hPa'], errors='coerce')
    df['CO2cal'] = pd.to_numeric(df['CO2cal'], errors='coerce')
    df['TVOC'] = pd.to_numeric(df['TVOC'], errors='coerce')
    df['PM2.5'] = pd.to_numeric(df['PM2.5'], errors='coerce')
    df['PM10'] = pd.to_numeric(df['PM10'], errors='coerce')
    df['CO'] = pd.to_numeric(df['CO'], errors='coerce')
    df['AQI'] = pd.to_numeric(df['AQI'], errors='coerce')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def make_traces(df, value_col):
    traces = []
    for name, group in df.groupby('name'):
        traces.append(go.Scatter(
            x=group['timestamp'],
            y=group[value_col],
            mode='lines+markers',
            name=name
        ))
    return traces

app = dash.Dash(__name__)

# Custom CSS for vertical sidebar (collapsible on hover)
app.css.append_css({
    'external_url': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css'
})

app.layout = html.Div([
    html.Div([
        html.Div(id='site-sidebar', children=[], style={
            'position': 'fixed',
            'top': '0',
            'left': '0',
            'height': '100%',
            'width': '60px',
            'backgroundColor': '#222',
            'overflowX': 'hidden',
            'transition': '0.3s',
            'zIndex': '1000',
        }),
        html.Div([
            html.H1('Halo Sensor Dashboard'),
            dcc.Dropdown(
                id='time-range',
                options=[
                    {'label': 'Last hour', 'value': '1H'},
                    {'label': 'Last 4 Hours', 'value': '4H'},
                    {'label': 'Last 12 Hours', 'value': '12H'},
                    {'label': 'Last 1 Day', 'value': '1D'},
                    {'label': 'Last 7 Days', 'value': '7D'}
                ],
                value='1D',
                clearable=False,
                style={'width': '300px', 'margin': '20px'}
            ),
            dcc.Interval(
                id='interval-refresh',
                interval=60*1000, # 60 seconds
                n_intervals=0
            ),
            dcc.Store(id='site-list-store'),
            dcc.Store(id='selected-site', data=None),
            dcc.Tabs([
                dcc.Tab(label='Temperature (C)', children=[
                    dcc.Graph(id='temp-graph')
                ]),
                dcc.Tab(label='Relative Humidity (%)', children=[
                    dcc.Graph(id='rh-graph')
                ]),
                dcc.Tab(label='P-hPa', children=[
                    dcc.Graph(id='phpa-graph')
                ]),
                dcc.Tab(label='CO2cal', children=[
                    dcc.Graph(id='co2cal-graph')
                ]),
                dcc.Tab(label='TVOC', children=[
                    dcc.Graph(id='tvoc-graph')
                ]),
                dcc.Tab(label='PM2.5', children=[
                    dcc.Graph(id='pm25-graph')
                ]),
                dcc.Tab(label='PM10', children=[
                    dcc.Graph(id='pm10-graph')
                ]),
                dcc.Tab(label='CO', children=[
                    dcc.Graph(id='co-graph')
                ]),
                dcc.Tab(label='AQI', children=[
                    dcc.Graph(id='aqi-graph')
                ])
            ])
        ], style={'marginLeft': '70px'})
    ], style={'display': 'flex'})
])

from dash.dependencies import State

# Callback to update the list of sites in the sidebar
@app.callback(
    Output('site-list-store', 'data'),
    [Input('interval-refresh', 'n_intervals')]
)
def update_site_list(n_intervals):
    df = load_data()
    sites = sorted(df['site'].dropna().unique())
    return sites

# Callback to render the sidebar with site buttons
@app.callback(
    Output('site-sidebar', 'children'),
    [Input('site-list-store', 'data'), Input('selected-site', 'data')]
)
def render_sidebar(sites, selected_site):
    if not sites:
        return []
    buttons = []
    for site in sites:
        style = {
            'display': 'block',
            'padding': '20px 10px',
            'color': '#fff',
            'backgroundColor': '#444' if site != selected_site else '#0074D9',
            'border': 'none',
            'width': '100%',
            'textAlign': 'left',
            'cursor': 'pointer',
            'fontWeight': 'bold' if site == selected_site else 'normal',
            'outline': 'none',
        }
        buttons.append(html.Button(site, id={'type': 'site-btn', 'index': site}, n_clicks=0, style=style))
    return buttons

# Callback to update selected site
@app.callback(
    Output('selected-site', 'data'),
    [Input({'type': 'site-btn', 'index': dash.dependencies.ALL}, 'n_clicks')],
    [State('site-list-store', 'data'), State('selected-site', 'data')]
)
def select_site(n_clicks_list, sites, selected_site):
    if not sites or not n_clicks_list:
        return selected_site
    changed = [i for i, n in enumerate(n_clicks_list) if n]
    if changed:
        return sites[changed[-1]]
    return selected_site

# Main graph update callback, now filters by selected site
@app.callback(
    [
        Output('temp-graph', 'figure'),
        Output('rh-graph', 'figure'),
        Output('phpa-graph', 'figure'),
        Output('co2cal-graph', 'figure'),
        Output('tvoc-graph', 'figure'),
        Output('pm25-graph', 'figure'),
        Output('pm10-graph', 'figure'),
        Output('co-graph', 'figure'),
        Output('aqi-graph', 'figure')
    ],
    [Input('time-range', 'value'), Input('interval-refresh', 'n_intervals'), Input('selected-site', 'data')]
)
def update_graphs(time_range, n_intervals, selected_site):
    df = load_data()
    now = pd.Timestamp.now()
    if time_range.endswith('H'):
        hours = int(time_range[:-1])
        start_time = now - pd.Timedelta(hours=hours)
    elif time_range.endswith('D'):
        days = int(time_range[:-1])
        start_time = now - pd.Timedelta(days=days)
    else:
        start_time = df['timestamp'].min()
    filtered = df[df['timestamp'] >= start_time]
    if selected_site:
        filtered = filtered[filtered['site'] == selected_site]
    temp_fig = {
        'data': make_traces(filtered, 'C'),
        'layout': go.Layout(title='Temperature (C) vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'Temperature (C)'})
    }
    rh_fig = {
        'data': make_traces(filtered, 'RH'),
        'layout': go.Layout(title='Relative Humidity (%) vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'Relative Humidity (%)'})
    }
    phpa_fig = {
        'data': make_traces(filtered, 'P-hPa'),
        'layout': go.Layout(title='P-hPa vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'P-hPa'})
    }
    co2_fig = {
        'data': make_traces(filtered, 'CO2cal'),
        'layout': go.Layout(title='CO2cal vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'CO2cal'})
    }
    tvoc_fig = {
        'data': make_traces(filtered, 'TVOC'),
        'layout': go.Layout(title='TVOC vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'TVOC'})
    }
    pm25_fig = {
        'data': make_traces(filtered, 'PM2.5'),
        'layout': go.Layout(title='PM2.5 vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'PM2.5'})
    }
    pm10_fig = {
        'data': make_traces(filtered, 'PM10'),
        'layout': go.Layout(title='PM10 vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'PM10'})
    }
    co_fig = {
        'data': make_traces(filtered, 'CO'),
        'layout': go.Layout(title='CO vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'CO'})
    }
    aqi_fig = {
        'data': make_traces(filtered, 'AQI'),
        'layout': go.Layout(title='AQI vs Time', xaxis={'title': 'Time'}, yaxis={'title': 'AQI'})
    }
    return temp_fig, rh_fig, phpa_fig, co2_fig, tvoc_fig, pm25_fig, pm10_fig, co_fig, aqi_fig

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0")
