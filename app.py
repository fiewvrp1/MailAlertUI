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
import sys # ✅ เพิ่มเข้ามา

# === CONFIGURATION (คงไว้ตามที่คุณต้องการ) ===
CLIENT_ID = "81a52509-4aa7-4060-ad96-4859d35701ba"
TENANT_ID = "b96cc57b-d146-48f5-a381-7cf474c23a9e"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Read"]
ABUSEIPDB_API_KEY = "5c1ce2c76b7fc57ddbf6f448707803c2d388d95cf9d96f7adcd8ac3d68f223795fb35de075a0e3c8"
METADEFENDER_API_KEY = "4ee3dbcf2b149b12764ae41d5cad9b50"

IS_ON_RENDER = os.environ.get('RENDER') == 'true'
# ✅ เพิ่มฟังก์ชันนี้เพื่อทำให้โปรแกรมหาไฟล์เจอเสมอ
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- INITIALIZATIONS & GLOBAL STATE ---
# ✅ แก้ไขการสร้าง app Flask ให้รู้จักโฟลเดอร์ templates
template_dir = resource_path('templates')
app = Flask(__name__, template_folder=template_dir)
msal_app = PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
if not IS_ON_RENDER: pygame.mixer.init()

# ✅ แก้ไข Path ของไฟล์เสียงทั้งหมดให้ถูกต้อง
SOUND_FILE_PATHS = {
    "time_alert": resource_path("sounds/Sound Mad Unicorn ED _ สงคราม สงดวน ตอนจบ #เพลงจบสงครามสงดวน #madunicorn #สงครามสงดวน.mp3"),
    "mail_general": resource_path("sounds/7-11-sound-thailand-VEED.mp3"),
    "log_inspection_rule": resource_path("sounds/Log Inspection Rule.mp3"),
    "servicedesk_mail": resource_path("sounds/servicedesk.mp3"),
    "disk_space_mail": resource_path("sounds/disk space.mp3"),
    "workbench_mail": resource_path("sounds/Workbench.mp3"),
    "severity_mail": resource_path("sounds/ticket.mp3"),
    "o365_mail": resource_path("O365.mp3"),
    "scheduled_scan_alert": resource_path("sounds/scheduled_scan.mp3")
}

folder_configs = [ {"name": "servicedesk", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAANL7i0AAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, {"name": "inbox", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('Inbox')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, {"name": "Log Inspection Rule", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAZiWJlAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, {"name": "Workbench", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAY1FmpAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, {"name": "no-reply-cloudone@trendmicro.com", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAFgPaUAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, {"name": "Severity", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAANL7i1AAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None}, {"name": "O365", "url": "https://graph.microsoft.com/v1.0/me/mailFolders('AAMkAGVjNDMzMzkwLTI1NjQtNDZiYy1hYzEyLWMwM2I4MzYwMDNiZAAuAAAAAAB8s0HqQpjPSKVeQNxxiOr0AQByAnmCtsn9Rb-VfDqVF9xCAAAiOMdRAAA=')/messages?$top=1&$orderby=receivedDateTime desc", "last_id": None} ]
mail_logs = []
current_access_token = None
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
    # ✅ 3. เพิ่มเงื่อนไขเพื่อไม่ให้เล่นเสียงบน Render
    if IS_ON_RENDER:
        print(f"[SOUND DISABLED ON RENDER] Pretending to play: {sound_file_key}")
        return
    
    file_path = SOUND_FILE_PATHS.get(sound_file_key)
    if file_path and os.path.exists(file_path):
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Error playing sound {file_path}: {e}")
    else:
        print(f"Warning: Sound file not found for key '{sound_file_key}'.")

def _perform_ip_scan(ip_address):
    abuse_results, metadefender_results = {}, {}
    try:
        abuse_url = 'https://api.abuseipdb.com/api/v2/check'
        abuse_querystring = {'ipAddress': ip_address, 'maxAgeInDays': '90', 'verbose': True}
        abuse_headers = {'Accept': 'application/json', 'Key': ABUSEIPDB_API_KEY}
        response = requests.get(url=abuse_url, headers=abuse_headers, params=abuse_querystring, timeout=10)
        response.raise_for_status()
        data = response.json().get('data', {})
        abuse_results = {'ipAddress': data.get('ipAddress', 'N/A'), 'score': data.get('abuseConfidenceScore', 0), 'reports': data.get('totalReports', 0), 'isp': data.get('isp', 'N/A'), 'usageType': data.get('usageType', 'N/A'), 'domain': data.get('domain', 'N/A'), 'countryName': data.get('countryName', 'N/A'), 'countryCode': data.get('countryCode', 'N/A')}
    except Exception as e:
        abuse_results = {'error': 'Failed to get data from AbuseIPDB.'}
    try:
        md_url = f"https://api.metadefender.com/v4/ip/{ip_address}"
        md_headers = {'apikey': METADEFENDER_API_KEY}
        response = requests.get(url=md_url, headers=md_headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and data.get('lookup_results') and data['lookup_results'].get('sources'):
            lookup = data.get('lookup_results', {})
            detected_by, total_engines = lookup.get('detected_by', 0), len(lookup.get('sources', []))
            metadefender_results = {'detection_rate': f"{detected_by} / {total_engines} engines"}
        else:
            metadefender_results = {'error': 'No data found for this IP.'}
    except Exception as e:
        metadefender_results = {'error': 'Failed to get data from MetaDefender.'}
    return {'abuseipdb': abuse_results, 'metadefender': metadefender_results}

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
        try:
            current_access_token = get_access_token()
        except Exception as e:
            print(f"Initial token acquisition failed: {e}")
    
    print("📬 Email checking loop started.")
    
    while True:
        if not current_access_token:
            try:
                current_access_token = get_access_token()
            except Exception:
                time.sleep(30)
                continue
        
        headers = {'Authorization': f'Bearer {current_access_token}'}
        for folder in folder_configs:
            try:
                response = requests.get(folder["url"], headers=headers, timeout=10)
                if response.status_code == 401:
                    current_access_token = None
                    print(f"Token expired. Will refresh on next cycle.")
                    break 
                response.raise_for_status()
                messages = response.json().get('value', [])
                if not messages:
                    continue
                
                latest = messages[0]
                latest_mail_id = latest['id']

                # ✅✅✅ กลไกป้องกันการแจ้งเตือนซ้ำ อยู่ตรงนี้ ✅✅✅
                # 1. ตรวจสอบว่า ID ของอีเมลล่าสุดนี้ เคยถูกประมวลผลไปแล้วหรือยัง
                if latest_mail_id in processed_email_ids:
                    continue # ถ้าเคยแล้ว ให้ข้ามไปโฟลเดอร์ถัดไปทันที

                # ถ้าเป็นอีเมลใหม่ที่ไม่เคยเจอมาก่อน ให้เริ่มประมวลผล
                if latest_mail_id != folder.get("last_id"):
                    subject = latest.get('subject', 'No Subject').lower()
                    sender = latest.get('from', {}).get('emailAddress', {}).get('address', 'N/A').lower()
                    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    log_message, sound_key_to_play = None, None
                    
                    if "resolve" in subject or "resolved" in subject:
                        log_message = f"⚠️ [{now_str}] [{folder['name']}] ข้าม (Resolve/Resolved): {subject}"
                    else:
                        # (ส่วน if/elif ของแต่ละโฟลเดอร์เหมือนเดิม)
                        if folder['name'] == 'servicedesk':
                            skip_words = ["daily report", "kaspersky security", "<risk alert> information", "resolve information"]
                            if any(word in subject for word in skip_words):
                                log_message = f"⚠️ [{now_str}] [{folder['name']}] ข้าม (Servicedesk Skip): {subject}"
                            else:
                                log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject} | {sender}", "servicedesk_mail"
                        # ... (elif สำหรับโฟลเดอร์อื่นๆ)
                        else:
                            log_message, sound_key_to_play = f"📧 [{now_str}] [{folder['name']}] {subject}", "mail_general"
                    
                    # 2. หลังจากประมวลผลเสร็จ ให้จดจำ ID ของอีเมลนี้ไว้
                    if log_message:
                        mail_logs.append(log_message)
                        print(log_message)
                    if sound_key_to_play:
                        play_sound(sound_key_to_play)
                    
                    processed_email_ids.append(latest_mail_id)
                    folder["last_id"] = latest_mail_id
            except Exception as e:
                print(f"❌ Error processing folder {folder['name']}: {e}")
        time.sleep(15)
# --- FLASK APP AND ROUTES ---
app = Flask(__name__)
scheduler = BackgroundScheduler(daemon=True)
@app.route("/")
def index(): return render_template("index.html")
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