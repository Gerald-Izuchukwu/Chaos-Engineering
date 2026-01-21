import os
import time
import re
# import logging
from collections import deque
import requests
from datetime import datetime, timezone

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
ERROR_RATE_THRESHOLD = float(os.getenv("ERROR_RATE_THRESHOLD", 2.0))  # percentage
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", 200))  # number of log lines
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", 300))  # seconds

last_pool = None
request_window = deque(maxlen=WINDOW_SIZE)
last_alert_time = {}


def format_slack_message(title: str, details: str, severity: str = "error") -> dict:
    severity = (severity or "").lower()

    emoji = {
        "critical": "🚨",
        "warning": "⚠️",
        "info": "ℹ️",
        "error": "❌"
    }.get(severity, "🚨")

    color = {
        "critical": "#FF0000",
        "error": "#FF0000",
        "warning": "#FFA500",
        "info": "#439FE0"
    }.get(severity, "#FF0000")

    return {
        "text": f"{emoji} {title}",  # fallback
        "attachments": [
            {
                "color": color,
                "fields": [
                    {
                        "title": "Details",
                        "value": details,
                        "short": False
                    },
                    {
                        "title": "Timestamp",
                        "value": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "short": True
                    }
                ],
                "ts": int(time.time())
            }
        ]
    }
# attachemnts, fields, ts, text are all slack specific formatting options

def send_slack_alert(title: str, details: str, severity):
    if not SLACK_WEBHOOK_URL:
        print(f" No Slack webhook URL configured. Alert not sent: {details}")
        return
    try:

        payload = format_slack_message(title, details, severity)
        response = requests.post(
            SLACK_WEBHOOK_URL, 
            json=payload,
            timeout=5
        )
        if response.status_code == 200:
            print(f" Alert sent to Slack: {details}")
        else:
            print(f" Failed to send alert to Slack. Status code: {response.status_code}, Response: {response.text}")

    except Exception as e:
        print(f" Exception occurred while sending alert to Slack: {e}")

def parse_log_line(line: str):
    fields = {}
    pattern = r'(\w+)=([^\s]+)'
    matches = re.findall(pattern, line)

    for key, value in matches:
        fields[key] = value

    return fields 

def check_failover(current_pool):
    '''Detect if pool has changed'''

    global last_pool
    if last_pool is None:
        last_pool = current_pool
        return False
    
    if current_pool != last_pool:
        print(f" Failover Detected Pool changed from {last_pool} to {current_pool}")
        last_pool = current_pool
        return True
    
    return False

def check_error_rate():
    #calculate error rate over sliding window
    if len(request_window) < 10:
        return False  # Not enough data yet
    
    error_count = sum(1 for status in request_window if status >= 500)
    error_rate = (error_count / len(request_window)) * 100

    if error_rate >= ERROR_RATE_THRESHOLD:
        print(f" High Error Rate Detected: {error_rate:.2f}% over last {len(request_window)} requests. Threshold: {ERROR_RATE_THRESHOLD}%")
        return True
    return False

def should_send_alert(alert_type):
    #check if enough time has passed since last alert (cooldown)
    current_time = time.time()

    if alert_type not in last_alert_time:
        last_alert_time[alert_type] = current_time
        return True
    
    time_since_last_alert = current_time - last_alert_time[alert_type]

    if time_since_last_alert >= ALERT_COOLDOWN:
        last_alert_time[alert_type] = current_time
        return True
    print(f"⏳ Cooldown active for {alert_type} ({time_since_last_alert:.0f}s / {ALERT_COOLDOWN}s)")
    return False

def tail_logs(log_file):
    #continuously read new and process nginx log files
    print(f"👀 Watching logs: {log_file}")
    print(f"📊 Config: threshold={ERROR_RATE_THRESHOLD}%, window={WINDOW_SIZE}, cooldown={ALERT_COOLDOWN}s")
    print(log_file)

    with open(log_file, 'r') as f:
        f.seek(0, 2) # Move to end of file
        while True:
            line = f.readline()

            if not line:
                time.sleep(0.1) # Wait for new logs, Sleep briefly
                continue
            
            # Parse log line
            fields = parse_log_line(line.strip())

            if not fields:
                continue

            pool = fields.get('pool', 'unknown')
            # status = int(fields.get('status', '0'))

            upstream_status_str = fields.get('upstream_status', '0')
            first_upstream_status = upstream_status_str.split(',')[0].strip()

            try:
                upstream_status = int(first_upstream_status)
            except ValueError:
                upstream_status = 0

            request_window.append(upstream_status)

            # Check for failover
            if check_failover(pool):
                if should_send_alert('failover'):
                    if pool == "green":
                        details = f"⚠️ Failover detected! Pool changed to {pool} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        title = "Failover Alert"
                        send_slack_alert(title, details, severity="warning")
                    elif pool == "blue":
                        details = f"✅ Switched back to primary pool: {pool} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        title = "Recover Alert"
                        send_slack_alert(title, details, severity="info")

            # Check for high error rate
            if check_error_rate():
                if should_send_alert('high_error_rate'):
                    error_count = sum(1 for s in request_window if s >= 500)
                    error_rate = (error_count / len(request_window)) * 100
                    title = "High Error Rate Alert"
                    details = f"⚠️  *High Error Rate Alert!*\nError rate: *{error_rate:.2f}%* (threshold: {ERROR_RATE_THRESHOLD}%)\nErrors: {error_count}/{len(request_window)} requests\nCurrent pool: {pool}"
                    send_slack_alert(title, details, severity="critical")

if __name__ == "__main__":
    log_file = '/var/log/nginx/monitoring-access.log'  # Path to nginx access log

    while not os.path.exists(log_file):
        print(f"⏳ Waiting for log file to be available: {log_file}")
        time.sleep(2)

    print("🚀 Watcher started!")
    tail_logs(log_file)