from flask import Flask, render_template, jsonify, request
import threading
import time
import datetime
import requests
from msal import PublicClientApplication
import pygame
import os
import collections
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import sys
import ipaddress
from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# === CONFIGURATION ===
def _require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}. Copy .env.example to .env and fill it in.")
    return value

CLIENT_ID = _require_env("CLIENT_ID")
TENANT_ID = _require_env("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Read"]
ABUSEIPDB_API_KEY = _require_env("ABUSEIPDB_API_KEY")
METADEFENDER_API_KEY = _require_env("METADEFENDER_API_KEY")
VIRUSTOTAL_API_KEY = _require_env("VIRUSTOTAL_API_KEY")
IS_ON_RENDER = os.environ.get('RENDER') == 'true'

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- INITIALIZATIONS & GLOBAL STATE ---
template_dir = resource_path('templates')
app = Flask(__name__, template_folder=template_dir)
msal_app = PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
if not IS_ON_RENDER: pygame.mixer.init()

SOUND_FILE_PATHS = {
    "time_alert": resource_path("sounds/time_alert.mp3"),
    "mail_general": resource_path("sounds/mail_general.mp3"),
    "log_inspection_rule": resource_path("sounds/Log Inspection Rule.mp3"),
    "servicedesk_mail": resource_path("sounds/servicedesk.mp3"),
    "disk_space_mail": resource_path("sounds/disk space.mp3"),
    "workbench_mail": resource_path("sounds/Workbench.mp3"),
    "severity_mail": resource_path("sounds/ticket.mp3"),
    "o365_mail": resource_path("O365.mp3"),
    "scheduled_scan_alert": resource_path("sounds/scheduled_scan.mp3"),
    "helpdesk_mail": resource_path("sounds/Helpdesk.mp3"),
    "email_security_mail": resource_path("sounds/Emailsecurity.mp3"),
    "threat_prevention_mail": resource_path("sounds/Threat Prevention.mp3")
}

folder_configs = [ 
    {"name": "servicedesk", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAANL7i0AAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, 
    {"name": "helpdesk", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAArWs_nAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None},
    {"name": "New Allow", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAArWs-BAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None},
    {"name": "inbox", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('Inbox')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, 
    {"name": "Log Inspection Rule", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAZiWJlAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, 
    {"name": "Workbench", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAY1FmpAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, 
    {"name": "no-reply-cloudone@trendmicro.com", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAFgPaUAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, 
    {"name": "Severity", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAANL7i1AAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, 
    {"name": "O365", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAiOMdRAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, 
    {"name": "Threat Prevention", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAv3oh_AAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}
]
ABUSEIPDB_CATEGORIES = {
    3: "Fraud Orders", 4: "DDoS Attack", 5: "FTP Brute-Force", 6: "Ping of Death",
    7: "Phishing", 8: "Fraud VoIP", 9: "Open Proxy", 10: "Web Spam", 11: "Email Spam",
    12: "Blog Spam", 13: "VPN IP", 14: "Port Scan", 15: "Hacking", 16: "SQL Injection",
    17: "Spoofing", 18: "Brute-Force", 19: "Bad Web Bot", 20: "Exploited Host",
    21: "Web App Attack", 22: "SSH", 23: "IoT Targeted",
}

def _get_ip_notes(ip_address, abuse_data):
    notes = []
    try:
        ip_obj = ipaddress.ip_address(ip_address)
        if ip_obj.is_loopback:
            notes.append("Loopback address")
        elif ip_obj.is_link_local:
            notes.append("Link-local address")
        elif ip_obj.is_private:
            notes.append("Private/Internal IP address")
        elif ip_obj.is_reserved:
            notes.append("Reserved address")
    except ValueError:
        pass
    if abuse_data.get('isPublic') is False and "Private/Internal IP address" not in notes:
        notes.append("Private/Internal IP address")
    if abuse_data.get('isWhitelisted'):
        notes.append("Whitelisted by AbuseIPDB")
    if abuse_data.get('isTor'):
        notes.append("Tor exit node")
    return notes

mail_logs, current_access_token = [], None
processed_email_ids = collections.deque(maxlen=50)
completed_scheduled_scans = collections.deque(maxlen=20)
scheduler = BackgroundScheduler(daemon=True)

# --- HELPER FUNCTIONS ---
def get_access_token():
    accounts = msal_app.get_accounts()
    result = None
    if accounts: result = msal_app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result:
        print("Opening browser for interactive authentication...")
        result = msal_app.acquire_token_interactive(scopes=SCOPES)
        if "access_token" not in result: raise Exception(f"Failed to acquire access token: {result.get('error_description', 'Unknown error')}")
    return result['access_token']

def play_sound(sound_file_key):
    if IS_ON_RENDER: return
    file_path = SOUND_FILE_PATHS.get(sound_file_key)
    if file_path and os.path.exists(file_path):
        try: pygame.mixer.music.stop(); pygame.mixer.music.load(file_path); pygame.mixer.music.play()
        except Exception as e: print(f"Error playing sound {file_path}: {e}")
    else: print(f"Warning: Sound file not found for key '{sound_file_key}'.")

def _perform_ip_scan(ip_address):
    abuse_results, metadefender_results, notes = {}, {}, []
    try:
        abuse_url = 'https://api.abuseipdb.com/api/v2/check'
        abuse_querystring = {'ipAddress': ip_address, 'maxAgeInDays': '90', 'verbose': True}
        abuse_headers = {'Accept': 'application/json', 'Key': ABUSEIPDB_API_KEY}
        response = requests.get(url=abuse_url, headers=abuse_headers, params=abuse_querystring, timeout=10)
        response.raise_for_status()
        data = response.json().get('data', {})
        recent_reports = [{
            'reportedAt': r.get('reportedAt'),
            'comment': (r.get('comment') or '')[:300],
            'categories': [ABUSEIPDB_CATEGORIES.get(c, f"Category {c}") for c in r.get('categories', [])],
            'reporterCountryName': r.get('reporterCountryName'),
        } for r in data.get('reports', [])[:5]]
        abuse_results = {'ipAddress': data.get('ipAddress', ip_address),
                         'score': data.get('abuseConfidenceScore', 0),
                         'reports': data.get('totalReports', 0),
                         'numDistinctUsers': data.get('numDistinctUsers', 0),
                         'lastReportedAt': data.get('lastReportedAt'),
                         'isPublic': data.get('isPublic'),
                         'isWhitelisted': data.get('isWhitelisted', False),
                         'isTor': data.get('isTor', False),
                         'isp': data.get('isp', 'N/A'), 'usageType': data.get('usageType', 'N/A'),
                         'domain': data.get('domain', 'N/A'),
                         'countryName': data.get('countryName', 'N/A'),
                         'countryCode': data.get('countryCode', 'N/A'),
                         'asn': data.get('asn', 'N/A'),
                         'recentReports': recent_reports}
        notes = _get_ip_notes(ip_address, abuse_results)
    except Exception as e:
        abuse_results = {'error': 'Failed to get data from AbuseIPDB.'}
        notes = _get_ip_notes(ip_address, {})
    try:
        md_url = f"https://api.metadefender.com/v4/ip/{ip_address}"
        md_headers = {'apikey': METADEFENDER_API_KEY}
        response = requests.get(url=md_url, headers=md_headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and data.get('lookup_results') and data['lookup_results'].get('sources'):
            lookup = data.get('lookup_results', {}); detected_by, total_engines = lookup.get('detected_by', 0), len(lookup.get('sources', []))
            geo = data.get('geo_info', {}) or {}
            sources = [{
                'provider': s.get('provider'),
                'assessment': s.get('assessment'),
                'updateTime': s.get('update_time'),
            } for s in lookup.get('sources', []) if s.get('assessment')]
            metadefender_results = {
                'detection_rate': f"{detected_by} / {total_engines} engines",
                'country': (geo.get('country') or {}).get('name'),
                'city': (geo.get('city') or {}).get('name'),
                'organization': geo.get('organization'),
                'carrier': geo.get('carrier'),
                'asn': geo.get('asn'),
                'sources': sources,
            }
        else:
            metadefender_results = {'error': 'No data found for this IP.'}
    except Exception as e:
        metadefender_results = {'error': 'Failed to get data from MetaDefender.'}
    return {'abuseipdb': abuse_results, 'metadefender': metadefender_results, 'notes': notes}

def _perform_virustotal_scan(sha1_hash):
    """Performs a file hash scan using the VirusTotal API."""
    vt_url = f"https://www.virustotal.com/api/v3/files/{sha1_hash}"
    vt_headers = {"x-apikey": VIRUSTOTAL_API_KEY}
    
    try:
        response = requests.get(url=vt_url, headers=vt_headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json().get('data', {}).get('attributes', {})
            stats = data.get('last_analysis_stats', {})
            positives = stats.get('malicious', 0) + stats.get('suspicious', 0)
            total = sum(stats.values())
            return {
                "status": "found",
                "positives": positives,
                "total": total,
                "sha1": sha1_hash
            }
        elif response.status_code == 404:
            return {"status": "not_found", "sha1": sha1_hash}
        else:
            return {"status": "error", "message": f"API returned status {response.status_code}"}
            
    except Exception as e:
        print(f"Error scanning with VirusTotal: {e}")
        return {"status": "error", "message": "Could not connect to VirusTotal."}

def run_scheduled_scan(ip):
    print(f"Running scheduled scan for {ip} via APScheduler...")
    scan_results = _perform_ip_scan(ip)
    scan_results['completed_at'] = datetime.datetime.now().strftime("%H:%M:%S")
    completed_scheduled_scans.appendleft(scan_results)
    play_sound("scheduled_scan_alert")

def time_based_alert(alert_name):
    mail_logs.append(f"⏰ [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fixed Time Alert: {alert_name}")
    play_sound("time_alert")

def check_mail_loop():
    global current_access_token
    if current_access_token is None:
        try: current_access_token = get_access_token()
        except Exception as e: print(f"Initial token acquisition failed: {e}")
    print("📬 Email checking loop started.")
    while True:
        if not current_access_token:
            try: current_access_token = get_access_token()
            except Exception: time.sleep(30); continue
        
        headers = {'Authorization': f'Bearer {current_access_token}'}
        for folder in folder_configs:
            try:
                url_to_fetch = f"{folder['url']}&$select=id,subject,from,body"
                response = requests.get(url_to_fetch, headers=headers, timeout=10)
                if response.status_code == 401:
                    current_access_token = None; print(f"Token expired. Will refresh on next cycle."); break
                response.raise_for_status()
                messages = response.json().get('value', [])
                if not messages: continue
                
                latest, latest_mail_id = messages[0], messages[0]['id']
                if latest_mail_id in processed_email_ids: continue
                
                if latest_mail_id != folder.get("last_id"):
                    subject = latest.get('subject', 'No Subject').lower()
                    sender = latest.get('from', {}).get('emailAddress', {}).get('address', 'N/A').lower()
                    body = latest.get('body', {}).get('content', '').lower()
                    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_message, sound_key_to_play = None, None

                    if "resolve" in subject or "resolved" in subject:
                        log_message = f"⚠️ [{now_str}] [{folder['name']}] ข้าม (Resolve/Resolved): {subject}"
                    else:
                        if folder['name'] == 'servicedesk':
                            required_keywords = [
                                "<risk alert> low",
                                "<risk alert> medium",
                                "<risk alert> high",
                                "<risk alert> critical"
                            ]
                            if any(keyword in subject for keyword in required_keywords):
                                log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject} | {sender}", "servicedesk_mail"
                            else:
                                log_message = f"⚠️ [{now_str}] [{folder['name']}] ข้าม (Servicedesk Skip): {subject}"
                        
                        elif folder['name'] == 'helpdesk':
                            log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject} | {sender}", "helpdesk_mail"
                        elif folder['name'] == 'New Allow':
                            log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject} | {sender}", "email_security_mail"

                        elif folder['name'] == 'Workbench':
                            log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject}", "workbench_mail"

                        # ✨ เพิ่มเงื่อนไขนี้เข้ามา ✨
                        elif folder['name'] == 'Threat Prevention':
                            log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject}", "threat_prevention_mail"

                        # (เงื่อนไข elif อื่นๆ ที่คุณอาจจะมี สามารถใส่ไว้ก่อนหน้านี้)
                        
                        else:
                            # เงื่อนไขนี้จะทำงานกับโฟลเดอร์ที่เหลือ เช่น inbox, Workbench, O365 เป็นต้น
                            # หากคุณต้องการเสียงเฉพาะสำหรับโฟลเดอร์เหล่านั้น ก็สามารถเพิ่ม elif ได้อีก
                            log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject}", "mail_general"

                    if log_message: mail_logs.append(log_message); print(log_message)
                    if sound_key_to_play: play_sound(sound_key_to_play)
                    processed_email_ids.append(latest_mail_id); folder["last_id"] = latest_mail_id
            except Exception as e:
                print(f"❌ Error processing folder {folder['name']}: {e}")
        time.sleep(15)

# --- FLASK APP AND ROUTES ---
# (โค้ดส่วนนี้และส่วนที่เหลือถูกต้องแล้ว)
@app.route("/")
def index(): return render_template("index.html")
@app.route("/forensic")
def forensic(): return render_template("forensic.html")
@app.route("/elastic-queries")
def elastic_queries(): return render_template("elastic_queries.html")
@app.route("/logs")
def logs(): return jsonify(mail_logs[-50:])
@app.route('/get_completed_scans')
def get_completed_scans(): return jsonify(list(completed_scheduled_scans))
@app.route('/scan_ip', methods=['POST'])
def scan_ip_address():
    ip_address = request.json.get('ip')
    if not ip_address: return jsonify({'error': 'IP address is required'}), 400
    results = _perform_ip_scan(ip_address)
    return jsonify(results)
@app.route('/scan_sha1', methods=['POST'])
def scan_sha1_hash():
    sha1_hash = request.json.get('hash')
    if not sha1_hash or len(sha1_hash) != 40:
        return jsonify({'status': 'error', 'message': 'Valid SHA1 hash is required'}), 400
    results = _perform_virustotal_scan(sha1_hash)
    return jsonify(results)
@app.route('/schedule_scan', methods=['POST'])
def schedule_scan_ip():
    data = request.get_json(); ip, schedule_type = data.get('ip'), data.get('type')
    if not all([ip, schedule_type]): return jsonify({'status': 'error', 'message': 'Missing IP or schedule type'}), 400
    try:
        job_id = f"scan_{ip}_{schedule_type}_{time.time()}"
        if schedule_type == 'daily':
            hour, minute = int(data.get('hour', 0)), int(data.get('minute', 0))
            scheduler.add_job(run_scheduled_scan, trigger='cron', hour=hour, minute=minute, args=[ip], id=job_id, replace_existing=False)
        elif schedule_type == 'interval_minutes':
            minutes = int(data.get('value', 5))
            scheduler.add_job(run_scheduled_scan, trigger='interval', minutes=minutes, args=[ip], id=job_id, replace_existing=False)
        elif schedule_type == 'interval_hours':
            hours = int(data.get('value', 1))
            scheduler.add_job(run_scheduled_scan, trigger='interval', hours=hours, args=[ip], id=job_id, replace_existing=False)
        else: return jsonify({'status': 'error', 'message': 'Invalid schedule type'}), 400
        return jsonify({'status': 'success'})
    except (ValueError, TypeError): return jsonify({'status': 'error', 'message': 'Invalid data format'}), 400
@app.route('/get_scheduled_scans')
def get_scheduled_scans():
    jobs_list = []
    for job in scheduler.get_jobs():
        job_info = {'id': job.id, 'ip': job.args[0], 'schedule': 'Unknown'}
        if 'cron' in str(job.trigger): job_info['schedule'] = f"Daily at {job.trigger.fields[4]}:{job.trigger.fields[5]}"
        elif 'interval' in str(job.trigger): job_info['schedule'] = f"Every {job.trigger.interval}"
        jobs_list.append(job_info)
    return jsonify(jobs_list)
@app.route('/delete_schedule/<job_id>', methods=['DELETE'])
def delete_schedule(job_id):
    try: scheduler.remove_job(job_id); return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    special_times = [(8, 59), (11, 59), (15, 59)]
    for i, (h, m) in enumerate(special_times):
        scheduler.add_job(time_based_alert, trigger='cron', hour=h, minute=m, args=[f"Alert {i+1}"], id=f"time_alert_{i}")
    scheduler.start()
    print("⏰ APScheduler started for time-based tasks.")
    if os.environ.get("WERKZEUG_RUN_MAIN") != 'true':
        mail_thread = threading.Thread(target=check_mail_loop); mail_thread.daemon = True; mail_thread.start()
    atexit.register(lambda: scheduler.shutdown())
    app.run(debug=False, host='0.0.0.0')