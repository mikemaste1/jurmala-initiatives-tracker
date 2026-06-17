#!/usr/bin/env python3
import os
import csv
import json
import requests
import datetime
import subprocess
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

API_URL = (
    "https://geolatvija.lv/api/v1/tapis/projects?"
    "search%5Batvk_id%5D=0004000&"
    "search%5Byear%5D%5B0%5D=2026&"
    "search%5Bstate%5D%5B0%5D=in_voting&"
    "search%5Bstate%5D%5B1%5D=voting_is_closed&"
    "search%5Bstate%5D%5B2%5D=supported&"
    "search%5Bstate%5D%5B3%5D=being_implemented&"
    "search%5Bstate%5D%5B4%5D=realized&"
    "search%5Bstate%5D%5B5%5D=not_supported&"
    "search%5Bcount_of_votes%5D=true&"
    "search%5Bshow_winners%5D=true"
)

DATA_DIR = "data"
CHARTS_DIR = "charts"
CSV_FILE = os.path.join(DATA_DIR, "initiatives_history.csv")
STATE_FILE = os.path.join(DATA_DIR, "last_absolute_values.json")
BASELINE_FILE = os.path.join(DATA_DIR, "launch_baseline.json")
HTML_FILE = "index.html"

# Define 13 distinguishable styles for the initiatives
STYLES = [
    # (color, matplotlib_linestyle, matplotlib_marker, chartjs_borderDash, chartjs_pointStyle)
    ('#38bdf8', '-', 'o', [], 'circle'),
    ('#34d399', '--', 's', [6, 4], 'rect'),
    ('#fb7185', ':', '^', [2, 3], 'triangle'),
    ('#f472b6', '-.', 'D', [8, 3, 2, 3], 'rectRot'),
    ('#c084fc', '-', 'v', [], 'triangle'),
    ('#a78bfa', '--', 'o', [6, 4], 'circle'),
    ('#818cf8', ':', 's', [2, 3], 'rect'),
    ('#60a5fa', '-.', '^', [8, 3, 2, 3], 'triangle'),
    ('#fbbf24', '-', 'D', [], 'rectRot'),
    ('#fb923c', '--', 'v', [6, 4], 'triangle'),
    ('#f87171', ':', 'o', [2, 3], 'circle'),
    ('#a3e635', '-.', 's', [8, 3, 2, 3], 'rect'),
    ('#2dd4bf', '-', '^', [], 'triangle')
]

def ensure_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHARTS_DIR, exist_ok=True)

def fetch_data():
    try:
        response = requests.get(API_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def load_json_file(filepath):
    if os.path.isfile(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    return {}

def save_json_file(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")

def save_to_csv(data, timestamp, reset_baseline=False):
    ensure_directories()
    
    baseline = {}
    if not reset_baseline:
        baseline = load_json_file(BASELINE_FILE)
        
    if not baseline:
        for project in data:
            p_id = project.get("id", "")
            baseline[p_id] = {
                "name": project.get("name", ""),
                "votes": project.get("vote_count", 0),
                "views": project.get("view_count", 0)
            }
        save_json_file(BASELINE_FILE, baseline)
        print("Established new launch baseline.")
        if os.path.isfile(CSV_FILE):
            os.remove(CSV_FILE)
            
    file_exists = os.path.isfile(CSV_FILE)
    new_state = {}
    rows_to_write = []
    
    for project in data:
        p_id = project.get("id", "")
        name = project.get("name", "")
        curr_votes = project.get("vote_count", 0)
        curr_views = project.get("view_count", 0)
        
        proj_baseline = baseline.get(p_id, {"votes": curr_votes, "views": curr_views})
        base_votes = proj_baseline.get("votes", curr_votes)
        base_views = proj_baseline.get("views", curr_views)
        
        delta_votes = max(0, curr_votes - base_votes)
        delta_views = max(0, curr_views - base_views)
        
        new_state[p_id] = {
            "name": name,
            "votes": curr_votes,
            "views": curr_views
        }
        
        rows_to_write.append([
            timestamp,
            p_id,
            name,
            delta_votes,
            delta_views,
            project.get("state", ""),
            project.get("is_winner", False)
        ])
        
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "project_id", "project_name", "delta_votes", "delta_views", "state", "is_winner"])
        writer.writerows(rows_to_write)
        
    save_json_file(STATE_FILE, new_state)
    print(f"Saved delta-from-launch values for {len(data)} items to CSV at {timestamp}")

def generate_static_charts():
    if not os.path.isfile(CSV_FILE):
        return

    try:
        df = pd.read_csv(CSV_FILE)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(by='timestamp')
        
        initiatives = list(df['project_name'].unique())
        
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
        
        # 1. Votes Delta Chart
        fig, ax = plt.subplots(figsize=(14, 8), layout='constrained')
        for i, name in enumerate(initiatives):
            style = STYLES[i % len(STYLES)]
            sub_df = df[df['project_name'] == name]
            ax.plot(
                sub_df['timestamp'], sub_df['delta_votes'], 
                linestyle=style[1], marker=style[2], color=style[0],
                markersize=4, linewidth=1.5, label=name
            )
        
        ax.set_title("Initiative Vote Increments Since Launch", fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel("Time", fontsize=11, labelpad=10)
        ax.set_ylabel("Vote Delta (Growth from Launch)", fontsize=11, labelpad=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=30)
        ax.legend(title="Initiatives", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)
        fig.savefig(os.path.join(CHARTS_DIR, "votes_over_time.png"), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # 2. Views Delta Chart
        fig, ax = plt.subplots(figsize=(14, 8), layout='constrained')
        for i, name in enumerate(initiatives):
            style = STYLES[i % len(STYLES)]
            sub_df = df[df['project_name'] == name]
            ax.plot(
                sub_df['timestamp'], sub_df['delta_views'], 
                linestyle=style[1], marker=style[2], color=style[0],
                markersize=4, linewidth=1.5, label=name
            )
            
        ax.set_title("Initiative View Increments Since Launch", fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel("Time", fontsize=11, labelpad=10)
        ax.set_ylabel("View Delta (Growth from Launch)", fontsize=11, labelpad=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=30)
        ax.legend(title="Initiatives", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)
        fig.savefig(os.path.join(CHARTS_DIR, "views_over_time.png"), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        print("Generated static texture-distinct PNG charts successfully.")
    except Exception as e:
        print(f"Error generating static charts: {e}")

def generate_interactive_dashboard():
    if not os.path.isfile(CSV_FILE):
        return

    try:
        df = pd.read_csv(CSV_FILE)
        df_list = df.to_dict(orient='records')
        
        latest_timestamp = df['timestamp'].max()
        last_state = load_json_file(STATE_FILE)
        
        table_stats = []
        for p_id, info in last_state.items():
            project_deltas = df[df['project_id'] == p_id]
            latest_delta_votes = 0
            latest_delta_views = 0
            state = "in_voting"
            is_winner = False
            
            if not project_deltas.empty:
                latest_row = project_deltas[project_deltas['timestamp'] == latest_timestamp]
                if not latest_row.empty:
                    latest_delta_votes = int(latest_row.iloc[0]['delta_votes'])
                    latest_delta_views = int(latest_row.iloc[0]['delta_views'])
                    state = latest_row.iloc[0]['state']
                    is_winner = bool(latest_row.iloc[0]['is_winner'])
                    
            table_stats.append({
                "project_name": info["name"],
                "votes": info["votes"],
                "views": info["views"],
                "delta_votes": latest_delta_votes,
                "delta_views": latest_delta_views,
                "state": state,
                "is_winner": is_winner
            })
            
        js_styles = []
        for style in STYLES:
            js_styles.append({
                "color": style[0],
                "borderDash": style[3],
                "pointStyle": style[4]
            })
            
        dashboard_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jūrmala Initiatives Growth Dashboard (2026)</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.03);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --accent-green: #34d399;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            padding: 1rem;
            min-height: 100vh;
            background-image: radial-gradient(circle at 10% 20%, rgba(56, 189, 248, 0.05) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(52, 211, 153, 0.05) 0%, transparent 40%);
        }}

        @media (min-width: 640px) {{
            body {{
                padding: 2rem;
            }}
        }}

        header {{
            margin-bottom: 2rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        @media (min-width: 768px) {{
            header {{
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            }}
        }}

        h1 {{
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .last-update {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }}

        @media (min-width: 1024px) {{
            .grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
            transition: border-color 0.2s;
        }}

        .card:hover {{
            border-color: rgba(56, 189, 248, 0.2);
        }}

        .card h2, .card h3 {{
            font-weight: 600;
        }}

        .card h2 {{
            font-size: 1.25rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .card h2 span {{
            font-size: 0.8rem;
            background: rgba(56, 189, 248, 0.1);
            color: var(--accent);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}

        /* Controls Panel styling */
        .controls-card {{
            margin-bottom: 2rem;
        }}

        .controls-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
        }}

        @media (min-width: 768px) {{
            .controls-grid {{
                grid-template-columns: 1fr 2fr;
            }}
        }}

        .control-group h3 {{
            font-size: 1rem;
            color: var(--text-secondary);
            margin-bottom: 0.75rem;
        }}

        .btn-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.85rem;
            transition: all 0.2s;
        }}

        .btn:hover {{
            background: rgba(56, 189, 248, 0.1);
            border-color: rgba(56, 189, 248, 0.3);
        }}

        .btn.active {{
            background: var(--accent);
            border-color: var(--accent);
            color: var(--bg-color);
            font-weight: 600;
        }}

        .btn-small {{
            background: transparent;
            border: none;
            color: var(--accent);
            cursor: pointer;
            font-size: 0.8rem;
            font-family: inherit;
            margin-left: 0.5rem;
            text-decoration: underline;
        }}

        .btn-small:hover {{
            color: var(--text-primary);
        }}

        .checkboxes-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 0.5rem;
            max-height: 150px;
            overflow-y: auto;
            padding-right: 0.5rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.75rem;
            background: rgba(0, 0, 0, 0.2);
        }}

        /* Custom scrollbar for checklist container */
        .checkboxes-grid::-webkit-scrollbar {{
            width: 6px;
        }}
        .checkboxes-grid::-webkit-scrollbar-track {{
            background: transparent;
        }}
        .checkboxes-grid::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 99px;
        }}

        .checkbox-label {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            color: var(--text-secondary);
            cursor: pointer;
            user-select: none;
            padding: 0.25rem;
            border-radius: 4px;
            transition: background 0.15s, color 0.15s;
        }}

        .checkbox-label:hover {{
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-primary);
        }}

        .checkbox-label input {{
            accent-color: var(--accent);
            cursor: pointer;
        }}

        .chart-container {{
            position: relative;
            height: 380px;
            width: 100%;
        }}

        .stats-table-card {{
            grid-column: 1 / -1;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.95rem;
        }}

        th, td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
        }}

        tbody tr:hover {{
            background: rgba(255, 255, 255, 0.01);
        }}

        .winner-badge {{
            background: rgba(52, 211, 153, 0.15);
            color: var(--accent-green);
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid rgba(52, 211, 153, 0.2);
        }}

        .delta-badge {{
            font-size: 0.8rem;
            font-weight: bold;
            margin-left: 0.5rem;
        }}
        .delta-up {{
            color: var(--accent-green);
        }}
    </style>
</head>
<body>
    <header>
        <div>
            <h1>Jūrmala Initiatives Growth Dashboard</h1>
            <p style="color: var(--text-secondary); margin-top: 0.25rem;">Cumulative growth since tracking session launch</p>
        </div>
        <div class="last-update">
            Last Checked: <strong id="lastChecked">{latest_timestamp}</strong>
        </div>
    </header>

    <!-- Controls Panel -->
    <div class="card controls-card">
        <div class="controls-grid">
            <div class="control-group">
                <h3>Time Interval</h3>
                <div class="btn-group">
                    <button class="btn active" onclick="setTimeWindow('all', this)">All Time</button>
                    <button class="btn" onclick="setTimeWindow('24h', this)">24 Hours</button>
                    <button class="btn" onclick="setTimeWindow('12h', this)">12 Hours</button>
                    <button class="btn" onclick="setTimeWindow('6h', this)">6 Hours</button>
                    <button class="btn" onclick="setTimeWindow('1h', this)">1 Hour</button>
                </div>
            </div>
            <div class="control-group">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <h3>Select Initiatives to Display</h3>
                    <div>
                        <button class="btn-small" onclick="toggleAllInitiatives(true)">Select All</button>
                        <button class="btn-small" onclick="toggleAllInitiatives(false)">Clear All</button>
                    </div>
                </div>
                <div class="checkboxes-grid" id="checkboxesGrid">
                    <!-- Populated dynamically -->
                </div>
            </div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Votes Delta <span>Cumulative Growth Since Launch</span></h2>
            <div class="chart-container">
                <canvas id="votesChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>Views Delta <span>Cumulative Growth Since Launch</span></h2>
            <div class="chart-container">
                <canvas id="viewsChart"></canvas>
            </div>
        </div>

        <div class="card stats-table-card">
            <h2>Current Standing & Growth Details</h2>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Initiative Name</th>
                            <th>Status</th>
                            <th>Total Votes (Growth Since Launch)</th>
                            <th>Total Views (Growth Since Launch)</th>
                            <th>Conversion Rate</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <!-- Filled by JS -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const rawHistoryData = {json.dumps(df_list)};
        const latestStats = {json.dumps(table_stats)};
        const styles = {json.dumps(js_styles)};

        const formatTime = (isoString) => {{
            const d = new Date(isoString);
            return `${{String(d.getMonth() + 1).padStart(2, '0')}}-${{String(d.getDate()).padStart(2, '0')}} ${{String(d.getHours()).padStart(2, '0')}}:${{String(d.getMinutes()).padStart(2, '0')}}`;
        }};

        // Extract datasets metadata
        const timestamps = [...new Set(rawHistoryData.map(d => d.timestamp))].sort();
        const initiatives = [...new Set(rawHistoryData.map(d => d.project_name))];

        // Global states for filters
        let selectedTimeWindow = 'all';
        const activeInitiatives = new Set(initiatives);

        // Populate checkboxes
        const checkboxContainer = document.getElementById('checkboxesGrid');
        initiatives.forEach((name, index) => {{
            const style = styles[index % styles.length];
            const label = document.createElement('label');
            label.className = 'checkbox-label';
            label.innerHTML = `
                <input type="checkbox" checked value="${{name}}" onchange="toggleInitiative('${{name}}', this.checked)">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background-color:${{style.color}};"></span>
                <span style="text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${{name}}</span>
            `;
            checkboxContainer.appendChild(label);
        }});

        const createDatasets = (key) => {{
            return initiatives.map((name, index) => {{
                const style = styles[index % styles.length];
                return {{
                    label: name,
                    data: [], // populated during update
                    borderColor: style.color,
                    backgroundColor: style.color + '11',
                    borderWidth: 2,
                    borderDash: style.borderDash,
                    pointStyle: style.pointStyle,
                    tension: 0.2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }};
            }});
        }};

        const chartOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    display: false // Turned off default legend because we have the filter checkbox list!
                }},
                tooltip: {{
                    mode: 'index',
                    intersect: false
                }}
            }},
            scales: {{
                x: {{
                    grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                    ticks: {{ color: '#94a3b8', font: {{ family: 'Outfit' }} }}
                }},
                y: {{
                    grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                    ticks: {{ color: '#94a3b8', font: {{ family: 'Outfit' }} }}
                }}
            }}
        }};

        // Render Votes Delta Chart
        const votesChart = new Chart(document.getElementById('votesChart'), {{
            type: 'line',
            data: {{ labels: [], datasets: createDatasets('delta_votes') }},
            options: chartOptions
        }});

        // Render Views Delta Chart
        const viewsChart = new Chart(document.getElementById('viewsChart'), {{
            type: 'line',
            data: {{ labels: [], datasets: createDatasets('delta_views') }},
            options: chartOptions
        }});

        // Update function for both charts
        function updateCharts() {{
            let filteredTimestamps = [...timestamps];
            
            if (selectedTimeWindow !== 'all') {{
                const now = new Date();
                let hoursLimit = 24;
                if (selectedTimeWindow === '1h') hoursLimit = 1;
                else if (selectedTimeWindow === '6h') hoursLimit = 6;
                else if (selectedTimeWindow === '12h') hoursLimit = 12;
                
                const cutoff = new Date(now.getTime() - hoursLimit * 60 * 60 * 1000);
                filteredTimestamps = timestamps.filter(ts => new Date(ts) >= cutoff);
            }}

            const newLabels = filteredTimestamps.map(formatTime);
            votesChart.data.labels = newLabels;
            viewsChart.data.labels = newLabels;

            initiatives.forEach((name, index) => {{
                // Get filtered values
                const dataPointsVotes = filteredTimestamps.map(ts => {{
                    const entry = rawHistoryData.find(d => d.project_name === name && d.timestamp === ts);
                    return entry ? entry.delta_votes : 0;
                }});

                const dataPointsViews = filteredTimestamps.map(ts => {{
                    const entry = rawHistoryData.find(d => d.project_name === name && d.timestamp === ts);
                    return entry ? entry.delta_views : 0;
                }});

                votesChart.data.datasets[index].data = dataPointsVotes;
                viewsChart.data.datasets[index].data = dataPointsViews;

                // Set visibility
                const isVisible = activeInitiatives.has(name);
                votesChart.setDatasetVisibility(index, isVisible);
                viewsChart.setDatasetVisibility(index, isVisible);
            }});

            votesChart.update();
            viewsChart.update();
        }}

        // Controls interactions
        function setTimeWindow(windowType, element) {{
            selectedTimeWindow = windowType;
            
            // Toggle active state classes
            const btns = element.parentElement.querySelectorAll('.btn');
            btns.forEach(b => b.classList.remove('active'));
            element.classList.add('active');
            
            updateCharts();
        }}

        function toggleInitiative(name, isChecked) {{
            if (isChecked) {{
                activeInitiatives.add(name);
            }} else {{
                activeInitiatives.delete(name);
            }}
            updateCharts();
        }}

        function toggleAllInitiatives(selectVal) {{
            const checkboxes = checkboxContainer.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => {{
                cb.checked = selectVal;
                if (selectVal) {{
                    activeInitiatives.add(cb.value);
                }} else {{
                    activeInitiatives.delete(cb.value);
                }}
            }});
            updateCharts();
        }}

        // Render standings table
        const tbody = document.getElementById('tableBody');
        latestStats.sort((a, b) => b.votes - a.votes);
        latestStats.forEach(item => {{
            const convRate = item.views > 0 ? ((item.votes / item.views) * 100).toFixed(1) + '%' : '0%';
            
            const deltaVotesText = item.delta_votes > 0 ? ` (+${{item.delta_votes}})` : ' (+0)';
            const deltaViewsText = item.delta_views > 0 ? ` (+${{item.delta_views}})` : ' (+0)';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight: 600;">${{item.project_name}} ${{item.is_winner ? '<span class="winner-badge">Winner</span>' : ''}}</td>
                <td><span style="color: var(--text-secondary); font-size: 0.85rem;">${{item.state}}</span></td>
                <td><span style="font-weight: 600; color: var(--accent-green);">${{item.votes.toLocaleString()}}</span><span class="delta-badge delta-up">${{deltaVotesText}}</span></td>
                <td><span style="color: var(--accent);">${{item.views.toLocaleString()}}</span><span class="delta-badge delta-up">${{deltaViewsText}}</span></td>
                <td>${{convRate}}</td>
            `;
            tbody.appendChild(tr);
        }});

        // Run initial render
        updateCharts();
    </script>
</body>
</html>
"""
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(dashboard_html)
        print("Generated interactive HTML dashboard successfully.")
    except Exception as e:
        print(f"Error generating interactive dashboard: {e}")

def git_push_updates():
    try:
        check_remote = subprocess.run(
            ["git", "remote"],
            capture_output=True, text=True, check=True
        )
        if not check_remote.stdout.strip():
            print("No git remote configured. Skipping push.")
            return
            
        subprocess.run(["git", "add", CSV_FILE, STATE_FILE, HTML_FILE, os.path.join(CHARTS_DIR, "*.png")], check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update: {datetime.datetime.now().isoformat(timespec='minutes')}"], capture_output=True)
        
        print("Pushing updates to GitHub...")
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Successfully pushed updates to GitHub.")
    except Exception as e:
        print(f"Git auto-push skipped or failed (Likely auth required): {e}")

def run_once(reset_baseline=False):
    ensure_directories()
    timestamp = datetime.datetime.now().isoformat(timespec='minutes')
    print(f"Polling API at {timestamp}...")
    data = fetch_data()
    if data:
        save_to_csv(data, timestamp, reset_baseline)
        generate_static_charts()
        generate_interactive_dashboard()
        git_push_updates()
        print("Cycle completed successfully.")
    else:
        print("Polling cycle failed.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        import time
        print("Starting municipal tracker in daemon mode (10-minute intervals)...")
        run_once(reset_baseline=True)
        while True:
            print("Sleeping for 10 minutes...")
            time.sleep(600)
            run_once(reset_baseline=False)
    else:
        reset = "--reset" in sys.argv
        run_once(reset_baseline=reset)
