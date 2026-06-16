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
HTML_FILE = "index.html"

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

def load_last_state():
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading state: {e}")
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")

def save_to_csv(data, timestamp):
    file_exists = os.path.isfile(CSV_FILE)
    last_state = load_last_state()
    new_state = {}
    
    rows_to_write = []
    for project in data:
        p_id = project.get("id", "")
        name = project.get("name", "")
        curr_votes = project.get("vote_count", 0)
        curr_views = project.get("view_count", 0)
        
        if p_id in last_state:
            last_votes = last_state[p_id].get("votes", curr_votes)
            last_views = last_state[p_id].get("views", curr_views)
            delta_votes = max(0, curr_votes - last_votes)
            delta_views = max(0, curr_views - last_views)
        else:
            delta_votes = 0
            delta_views = 0
            
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
        
    save_state(new_state)
    print(f"Saved delta values for {len(data)} items to CSV at {timestamp}")

def generate_static_charts():
    if not os.path.isfile(CSV_FILE):
        return

    try:
        df = pd.read_csv(CSV_FILE)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(by='timestamp')
        
        initiatives = df['project_name'].unique()
        
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
        
        # 1. Votes Delta Chart
        fig, ax = plt.subplots(figsize=(12, 7), layout='constrained')
        for name in initiatives:
            sub_df = df[df['project_name'] == name]
            ax.plot(sub_df['timestamp'], sub_df['delta_votes'], marker='o', markersize=3, label=name)
        
        ax.set_title("Initiative Vote Growth (Deltas) Over Time", fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel("Time", fontsize=11, labelpad=10)
        ax.set_ylabel("Vote Delta (Growth)", fontsize=11, labelpad=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=30)
        ax.legend(title="Initiatives", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)
        fig.savefig(os.path.join(CHARTS_DIR, "votes_over_time.png"), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # 2. Views Delta Chart
        fig, ax = plt.subplots(figsize=(12, 7), layout='constrained')
        for name in initiatives:
            sub_df = df[df['project_name'] == name]
            ax.plot(sub_df['timestamp'], sub_df['delta_views'], marker='s', markersize=3, label=name)
            
        ax.set_title("Initiative View Growth (Deltas) Over Time", fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel("Time", fontsize=11, labelpad=10)
        ax.set_ylabel("View Delta (Growth)", fontsize=11, labelpad=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=30)
        ax.legend(title="Initiatives", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)
        fig.savefig(os.path.join(CHARTS_DIR, "views_over_time.png"), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        print("Generated static delta-based PNG charts successfully.")
    except Exception as e:
        print(f"Error generating static charts: {e}")

def generate_interactive_dashboard():
    if not os.path.isfile(CSV_FILE):
        return

    try:
        df = pd.read_csv(CSV_FILE)
        df_list = df.to_dict(orient='records')
        
        latest_timestamp = df['timestamp'].max()
        last_state = load_last_state()
        
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
            padding: 2rem;
            min-height: 100vh;
            background-image: radial-gradient(circle at 10% 20%, rgba(56, 189, 248, 0.05) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(52, 211, 153, 0.05) 0%, transparent 40%);
        }}

        header {{
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        h1 {{
            font-size: 2.2rem;
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
            transition: transform 0.2s, border-color 0.2s;
        }}

        .card:hover {{
            border-color: rgba(56, 189, 248, 0.2);
        }}

        .card h2 {{
            font-size: 1.25rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-weight: 600;
        }}

        .card h2 span {{
            font-size: 0.8rem;
            background: rgba(56, 189, 248, 0.1);
            color: var(--accent);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}

        .chart-container {{
            position: relative;
            height: 400px;
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
            <p style="color: var(--text-secondary); margin-top: 0.25rem;">Monitoring delta changes (growth rate) for 2026 initiatives</p>
        </div>
        <div class="last-update">
            Last Checked: <strong id="lastChecked">{latest_timestamp}</strong>
        </div>
    </header>

    <div class="grid">
        <div class="card">
            <h2>Votes Delta <span>Hourly/Interval Growth</span></h2>
            <div class="chart-container">
                <canvas id="votesChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>Views Delta <span>Hourly/Interval Growth</span></h2>
            <div class="chart-container">
                <canvas id="viewsChart"></canvas>
            </div>
        </div>

        <div class="card stats-table-card">
            <h2>Current Initiatives Standings & Latest Deltas</h2>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Initiative Name</th>
                            <th>Status</th>
                            <th>Total Votes (Latest Growth)</th>
                            <th>Total Views (Latest Growth)</th>
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

        const formatTime = (isoString) => {{
            const d = new Date(isoString);
            return `${{String(d.getMonth() + 1).padStart(2, '0')}}-${{String(d.getDate()).padStart(2, '0')}} ${{String(d.getHours()).padStart(2, '0')}}:${{String(d.getMinutes()).padStart(2, '0')}}`;
        }};

        const timestamps = [...new Set(rawHistoryData.map(d => d.timestamp))].sort();
        const labels = timestamps.map(formatTime);
        
        const initiatives = [...new Set(rawHistoryData.map(d => d.project_name))];

        const colors = [
            '#38bdf8', '#34d399', '#fb7185', '#f472b6', '#c084fc', 
            '#a78bfa', '#818cf8', '#60a5fa', '#34d399', '#fbbf24', 
            '#fb923c', '#f87171', '#a3e635'
        ];

        const createDatasets = (key) => {{
            return initiatives.map((name, index) => {{
                const dataPoints = timestamps.map(ts => {{
                    const entry = rawHistoryData.find(d => d.project_name === name && d.timestamp === ts);
                    return entry ? entry[key] : null;
                }});

                return {{
                    label: name,
                    data: dataPoints,
                    borderColor: colors[index % colors.length],
                    backgroundColor: colors[index % colors.length] + '22',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: timestamps.length > 1 ? 2 : 5,
                    pointHoverRadius: 6
                }};
            }});
        }};

        const chartOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    display: true,
                    position: 'bottom',
                    labels: {{
                        color: '#94a3b8',
                        font: {{ family: 'Outfit', size: 10 }},
                        boxWidth: 12
                    }}
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

        new Chart(document.getElementById('votesChart'), {{
            type: 'line',
            data: {{ labels, datasets: createDatasets('delta_votes') }},
            options: chartOptions
        }});

        new Chart(document.getElementById('viewsChart'), {{
            type: 'line',
            data: {{ labels, datasets: createDatasets('delta_views') }},
            options: chartOptions
        }});

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
        # Check if remote is configured
        check_remote = subprocess.run(
            ["git", "remote"],
            capture_output=True, text=True, check=True
        )
        if not check_remote.stdout.strip():
            print("No git remote configured. Skipping push.")
            return
            
        # Add files
        subprocess.run(["git", "add", CSV_FILE, STATE_FILE, HTML_FILE, os.path.join(CHARTS_DIR, "*.png")], check=True)
        
        # Commit
        subprocess.run(["git", "commit", "-m", f"Auto-update: {datetime.datetime.now().isoformat(timespec='minutes')}"], capture_output=True)
        
        # Push
        print("Pushing updates to GitHub...")
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Successfully pushed updates to GitHub.")
    except Exception as e:
        print(f"Git auto-push skipped or failed: {e}")

def run_once():
    ensure_directories()
    timestamp = datetime.datetime.now().isoformat(timespec='minutes')
    print(f"Polling API at {timestamp}...")
    data = fetch_data()
    if data:
        save_to_csv(data, timestamp)
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
        while True:
            run_once()
            print("Sleeping for 10 minutes...")
            time.sleep(600)
    else:
        run_once()
