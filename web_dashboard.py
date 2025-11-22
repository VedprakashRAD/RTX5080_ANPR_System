import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DB_FILE = os.getenv("DB_FILE", "lpr_logs.db")
CAMERA_IP = os.getenv("CAMERA_IP", "10.1.2.201")

def get_dashboard_html():
    """
    Generate HTML for the dashboard
    """
    # Get recent logs
    conn = sqlite3.connect(DB_FILE)
    logs = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50").fetchall()
    logs = [{"timestamp": log[2], "plate": log[1], "type": log[3], "confidence": log[4]} for log in logs]
    
    # Get statistics
    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0],
        "cars": conn.execute("SELECT COUNT(*) FROM logs WHERE type LIKE '%CAR%'").fetchone()[0],
        "bikes": conn.execute("SELECT COUNT(*) FROM logs WHERE type LIKE '%BIKE%' OR type LIKE '%SCOOTER%'").fetchone()[0],
        "trucks": conn.execute("SELECT COUNT(*) FROM logs WHERE type LIKE '%TRUCK%' OR type LIKE '%BUS%'").fetchone()[0]
    }
    conn.close()
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>LPR Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat-box {{ background: #ecf0f1; padding: 15px; border-radius: 5px; flex: 1; text-align: center; }}
        .live-feed {{ margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #34495e; color: white; }}
        .vehicle-car {{ background: #e8f5e8; }}
        .vehicle-bike {{ background: #fff3cd; }}
        .vehicle-truck {{ background: #f8d7da; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚗 License Plate Recognition Dashboard</h1>
        <p>Real-time vehicle monitoring system</p>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <h3>{stats['total']}</h3>
            <p>Total Vehicles</p>
        </div>
        <div class="stat-box">
            <h3>{stats['cars']}</h3>
            <p>Cars</p>
        </div>
        <div class="stat-box">
            <h3>{stats['bikes']}</h3>
            <p>Bikes/Scooters</p>
        </div>
        <div class="stat-box">
            <h3>{stats['trucks']}</h3>
            <p>Trucks/Buses</p>
        </div>
    </div>
    
    <div class="live-feed">
        <h2>📹 Live Camera Feed</h2>
        <img src="/video_feed" width="800" style="border: 1px solid #ddd; border-radius: 5px;" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAwIiBoZWlnaHQ9IjQ1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjY2NjIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIyMCIgZmlsbD0iIzY2NiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkNhbWVyYSBTdHJlYW0gVW5hdmFpbGFibGU8L3RleHQ+PC9zdmc+'"
    </div>
    
    <div class="live-feed">
        <h2>📋 Recent Vehicle Entries</h2>
        <table>
            <tr>
                <th>Time</th>
                <th>License Plate</th>
                <th>Vehicle Type</th>
                <th>Confidence</th>
            </tr>
"""
    
    for log in logs:
        vehicle_class = log['type'].lower().split('/')[0]
        html_content += f"""            <tr class="vehicle-{vehicle_class}">
                <td>{log['timestamp']}</td>
                <td><strong>{log['plate']}</strong></td>
                <td>{log['type']}</td>
                <td>{log['confidence'] if log['confidence'] else "N/A"}</td>
            </tr>
"""
    
    html_content += f"""        </table>
    </div>
    
    <div id="liveDetections" style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px;">
        <h3>🔴 Live Detections</h3>
        <div id="detectionList">No recent detections...</div>
    </div>
    
    <div style="margin-top: 30px; text-align: center; color: #7f8c8d;">
        <p>Last updated: {current_time}</p>
        <p>System Status: <span style="color: green;">● Online</span></p>
    </div>
    
    <script>
        // Live detection updates
        function updateLiveDetections() {{
            fetch('/api/live-detections')
                .then(response => response.json())
                .then(data => {{
                    if (data.success && data.detections.length > 0) {{
                        const detectionList = document.getElementById('detectionList');
                        detectionList.innerHTML = data.detections.map(detection => {{
                            const imageName = detection.image_path ? detection.image_path.split('/').pop() : null;
                            const roiImageName = detection.roi_image_path ? detection.roi_image_path.split('/').pop() : null;
                            const apiResponse = detection.api_response ? JSON.parse(detection.api_response) : null;
                            
                            return `<div style="margin: 10px 0; padding: 12px; background: white; border-radius: 5px; border-left: 4px solid #27ae60;">
                                <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
                                    ${{imageName ? `<img src="/vehicle-image/${{imageName}}" style="width: 120px; height: 80px; object-fit: cover; border-radius: 3px;" title="Full Vehicle Image">` : ''}}
                                    ${{roiImageName ? `<img src="/roi-image/${{roiImageName}}" style="width: 80px; height: 60px; object-fit: cover; border-radius: 3px; border: 2px solid #e74c3c;" title="ROI Sent to API">` : ''}}
                                    <div style="flex: 1;">
                                        <div><strong style="font-size: 1.2em; color: #2c3e50;">${{detection.plate}}</strong></div>
                                        <div style="color: #34495e; margin: 2px 0;">Type: ${{detection.type}}</div>
                                        <div style="color: #7f8c8d; font-size: 0.9em;">${{detection.timestamp}}</div>
                                        ${{apiResponse ? `<div style="font-size: 0.8em; color: #27ae60; margin-top: 4px;">API: Success ✓ Internet: ${{apiResponse.internet ? '✓' : '✗'}}</div>` : ''}}
                                    </div>
                                </div>
                                <div style="font-size: 0.8em; color: #95a5a6;">
                                    📷 Full Image | 🔍 ROI → API ${{roiImageName ? '(Temp - Auto Delete)' : '(Synced)'}}
                                </div>
                            </div>`;
                        }}).join('');
                    }}
                }})
                .catch(error => console.log('Live update error:', error));
        }}
        
        // Update every 2 seconds
        setInterval(updateLiveDetections, 2000);
        updateLiveDetections(); // Initial load
    </script>
</body>
</html>"""
    
    return html_content

def get_root_html():
    """
    Generate HTML for the root page
    """
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Complete LPR System</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; text-align: center; }
        .endpoint { background: #ecf0f1; padding: 15px; margin: 15px 0; border-radius: 5px; }
        .endpoint h3 { margin-top: 0; color: #34495e; }
        .btn { display: inline-block; background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 10px 5px; }
        .btn:hover { background: #2980b9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚗 Complete License Plate Recognition System</h1>
        
        <div class="endpoint">
            <h3>📸 License Plate Extraction API</h3>
            <p>POST /extract-license-plate - Upload an image to extract license plate</p>
            <a href="/docs" class="btn">API Documentation</a>
        </div>
        
        <div class="endpoint">
            <h3>📹 LPR Camera System</h3>
            <p>GET /start-lpr - Start the real-time LPR camera system</p>
            <a href="/start-lpr" class="btn">Start LPR System</a>
        </div>
        
        <div class="endpoint">
            <h3>📊 Monitoring Dashboard</h3>
            <p>GET /dashboard - View real-time vehicle monitoring dashboard</p>
            <a href="/dashboard" class="btn">View Dashboard</a>
        </div>
        
        <div class="endpoint">
            <h3>⚙️ System Status</h3>
            <p>System is running and ready to process license plates</p>
        </div>
    </div>
</body>
</html>"""
    return html_content