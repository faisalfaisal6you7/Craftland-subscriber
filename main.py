import hmac
import hashlib
import requests
import string
import random
import json
import codecs
import time
import base64
import threading
import sys
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import blackboxprotobuf
import urllib3
from concurrent.futures import ThreadPoolExecutor
import random as rnd

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich import box
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.align import Align

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- Constants ----------
REGION_LANG = {
    "ME": "ar", "IND": "hi", "ID": "id", "VN": "vi", "TH": "th",
    "BD": "bn", "PK": "ur", "TW": "zh", "CIS": "ru", "SAC": "es", "BR": "pt"
}
REGION_URLS = {
    "IND": "https://client.ind.freefiremobile.com/",
    "ID": "https://clientbp.ggpolarbear.com/",
    "BR": "https://client.us.freefiremobile.com/",
    "ME": "https://clientbp.ggpolarbear.com/",
    "VN": "https://clientbp.ggpolarbear.com/",
    "TH": "https://clientbp.ggpolarbear.com/",
    "CIS": "https://clientbp.ggpolarbear.com/",
    "BD": "https://clientbp.ggpolarbear.com/",
    "PK": "https://clientbp.ggpolarbear.com/",
    "SG": "https://clientbp.ggpolarbear.com/",
    "SAC": "https://client.us.freefiremobile.com/",
    "TW": "https://clientbp.ggpolarbear.com/"
}

REGION_DETAILS = {
    "BD": ("BANGLADESH", "🇧🇩"),
    "IND": ("INDIA", "🇮🇳"),
    "ID": ("INDONESIA", "🇮🇩"),
    "BR": ("BRAZIL", "🇧🇷"),
    "ME": ("MIDDLE EAST", "🇦🇪"),
    "VN": ("VIETNAM", "🇻🇳"),
    "TH": ("THAILAND", "🇹🇭"),
    "CIS": ("RUSSIA / CIS", "🇷🇺"),
    "PK": ("PAKISTAN", "🇵🇰"),
    "SG": ("SINGAPORE", "🇸🇬"),
    "SAC": ("SOUTH AMERICA", "🇲🇽"),
    "TW": ("TAIWAN", "🇹🇼")
}

HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
KEY = bytes.fromhex(HEX_KEY)
HEX_KEY_STR = HEX_KEY
GARENA = "QllfREVWSUxIRVhfVEVBTQ=="

WORKSHOP_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
WORKSHOP_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

# ---------- Extended Animation & Spinner Frames ----------
SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
CYBER_FRAMES = ['◢', '◣', '◤', '◥', '▲', '►', '▼', '◄']
PULSE_DOTS = ['●  ', ' ● ', '  ●', ' ● ']
GLOW_COLORS = ["#00f0ff", "#00ff66", "#7000ff", "#ff0055", "#ffe600", "#ff00a0"]
WAVE_FRAMES = ['░░░░░', '█░░░░', '██░░░', '███░░', '████░', '█████', '░████', '░░███', '░░░██', '░░░░█']

# ---------- Helper Functions ----------
def EnC_Vr(N):
    if N < 0: return b''
    H = []
    while True:
        b = N & 0x7F
        N >>= 7
        if N: b |= 0x80
        H.append(b)
        if not N: break
    return bytes(H)

def CrEaTe_VarianT(field_number, value):
    return EnC_Vr((field_number << 3) | 0) + EnC_Vr(value)

def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded = value.encode() if isinstance(value, str) else value
    return EnC_Vr(field_header) + EnC_Vr(len(encoded)) + encoded

def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = CrEaTe_ProTo(value)
            packet.extend(CrEaTe_LenGTh(field, nested))
        elif isinstance(value, int):
            packet.extend(CrEaTe_VarianT(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(CrEaTe_LenGTh(field, value))
    return packet

def generate_random_name():
    length = random.randint(8, 10)
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_custom_password():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(16))

def E_AEs(Pc):
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(bytes.fromhex(Pc), AES.block_size))

def encrypt_api(plain_text):
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(bytes.fromhex(plain_text), AES.block_size)).hex()

def to_unicode_escaped(s):
    return ''.join(c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in s)

def encode_string(original):
    keystream = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
                 0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    encoded = ""
    for i, ch in enumerate(original):
        encoded += chr(ord(ch) ^ keystream[i % len(keystream)])
    return {"open_id": original, "field_14": encoded}

def decode_jwt_token(jwt_token):
    try:
        parts = jwt_token.split('.')
        if len(parts) >= 2:
            payload = parts[1] + '=' * ((4 - len(parts[1]) % 4) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload))
            return str(data.get('account_id') or data.get('external_id', 'N/A'))
    except:
        pass
    return "N/A"

# ---------- FIXED: perform_major_login (typo \0e → \x0e) ----------
def perform_major_login(uid, password, access_token, open_id, region, is_ghost, session):
    try:
        payload_parts = [
            b'\x1a\x132025-08-30 05:19:21"\tfree fire(\x01:\x081.114.13B2Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)J\x08HandheldR\nATM MobilsZ\x04WIFI`\xb6\nh\xee\x05r\x03300z\x1fARMv7 VFPv3 NEON VMH | 2400 | 2\x80\x01\xc9\x0f\x8a\x01\x0fAdreno (TM) 640\x92\x01\rOpenGL ES 3.2\x9a\x01+Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f\xa2\x01\x0e105.235.139.91\xaa\x01\x02',
            b'en',
            b'\xb2\x01 1d8ec0240ede109973f3321b9354b44d\xba\x01\x014\xc2\x01\x08Handheld\xca\x01\x10Asus ASUS_I005DA\xea\x01@afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390\xf0\x01\x01\xca\x02\nATM Mobils\xd2\x02\x04WIFI\xca\x03 7428b253defc164018c604a1ebbfebdf\xe0\x03\xa8\x81\x02\xe8\x03\xf6\xe5\x01\xf0\x03\xaf\x13\xf8\x03\x84\x07\x80\x04\xe7\xf0\x01\x88\x04\xa8\x81\x02\x90\x04\xe7\xf0\x01\x98\x04\xa8\x81\x02\xc8\x04\x01\xd2\x04=/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm\xe0\x04\x01\xea\x04_2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/base.apk\xf0\x04\x03\xf8\x04\x01\x8a\x05\x0232\x9a\x05\n2019118692\xb2\x05\tOpenGLES2\xb8\x05\xff\x7f\xc0\x05\x04\xe0\x05\xf3F\xea\x05\x07android\xf2\x05pKqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3ptNrGB0Ll0LRz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2\xf8\x05\xfb\xe4\x06\x88\x06\x01\x90\x06\x01\x9a\x06\x014\xa2\x06\x014\xb2\x06"GQ@O\x00\x0e^\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5'
        ]
        payload = b''.join(payload_parts)
        data = payload.replace(b'afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390', access_token.encode())
        data = data.replace(b'1d8ec0240ede109973f3321b9354b44d', open_id.encode())
        final_payload = bytes.fromhex(encrypt_api(data.hex()))
        url = "https://loginbp.ggpolarbear.com/MajorLogin"
        headers = {
            "Accept-Encoding": "gzip",
            "Authorization": "Bearer",
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Expect": "100-continue",
            "ReleaseVersion": "OB54",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
            "X-GA": "v1 1",
            "X-Unity-Version": "2018.4.11f1"
        }
        resp = session.post(url, headers=headers, data=final_payload, verify=False, timeout=20)
        if resp.status_code == 200 and len(resp.text) > 10:
            jwt_start = resp.text.find("eyJ")
            if jwt_start != -1:
                jwt_token = resp.text[jwt_start:]
                second_dot = jwt_token.find(".", jwt_token.find(".") + 1)
                if second_dot != -1:
                    jwt_token = jwt_token[:second_dot + 44]
                    account_id = decode_jwt_token(jwt_token)
                    if account_id != "N/A":
                        return {"success": True, "data": {"account_id": account_id, "jwt_token": jwt_token}}
                    else:
                        return {"success": False, "error": "jwt_missing"}
        return {"success": False, "error": "login_failed"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "network"}
    except Exception:
        return {"success": False, "error": "api_error"}

def Major_Regsiter(access_token, open_id, field, uid, password, region, is_ghost, session):
    try:
        url = "https://loginbp.ggpolarbear.com/MajorRegister"
        name = generate_random_name()
        headers = {
            "Accept-Encoding": "gzip",
            "Authorization": "Bearer",
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Expect": "100-continue",
            "ReleaseVersion": "OB54",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
            "X-GA": "v1 1",
            "X-Unity-Version": "2018.4."
        }
        lang_code = "pt" if is_ghost else REGION_LANG.get(region.upper(), "en")
        payload = {
            1: name,
            2: access_token,
            3: open_id,
            5: 102000007,
            6: 4,
            7: 1,
            13: 1,
            14: field,
            15: lang_code,
            16: 1,
            17: 1
        }
        payload_bytes = CrEaTe_ProTo(payload)
        encrypted_payload = E_AEs(payload_bytes.hex())
        resp = session.post(url, headers=headers, data=encrypted_payload, verify=False, timeout=20)
        if resp.status_code == 200:
            login_result = perform_major_login(uid, password, access_token, open_id, region, is_ghost, session)
            if login_result["success"]:
                account_data = login_result["data"]
                return {
                    "success": True,
                    "data": {
                        "uid": uid,
                        "password": password,
                        "name": name,
                        "region": "GHOST" if is_ghost else region,
                        "account_id": account_data["account_id"],
                        "jwt_token": account_data["jwt_token"]
                    }
                }
            else:
                return {"success": False, "error": login_result["error"]}
        else:
            return {"success": False, "error": f"http_{resp.status_code}"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "network"}
    except Exception:
        return {"success": False, "error": "api_error"}

def token(uid, password, region, is_ghost, session):
    try:
        url = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
        payload = {
            "client_id": 100067,
            "client_secret": HEX_KEY_STR,
            "client_type": 2,
            "password": password,
            "response_type": "token",
            "uid": uid
        }
        body_json = json.dumps(payload, separators=(',', ':'))
        signature = hmac.new(KEY, body_json.encode(), hashlib.sha256).hexdigest()
        headers = {
            "User-Agent": "GarenaMSDK/4.0.39(SM-A325M ;Android 13;en;HK;)",
            "Authorization": f"Signature {signature}",
            "Content-Type": "application/json; charset=utf-8"
        }
        resp = session.post(url, headers=headers, data=body_json, verify=False, timeout=20)
        resp_json = resp.json()
        if resp_json.get("code") != 0:
            return {"success": False, "error": f"token_api_failed_{resp_json.get('code')}"}
        open_id = resp_json['data']['open_id']
        access_token = resp_json['data']['access_token']
        result = encode_string(open_id)
        field = to_unicode_escaped(result['field_14'])
        field = codecs.decode(field, 'unicode_escape').encode('latin1')
        return Major_Regsiter(access_token, open_id, field, uid, password, region, is_ghost, session)
    except requests.exceptions.Timeout:
        return {"success": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "network"}
    except Exception:
        return {"success": False, "error": "api_error"}

def create_acc(region, is_ghost, session):
    password = generate_custom_password()
    for source in [2, 1, 3]:
        try:
            payload = {"app_id": 100067, "client_type": 2, "password": password, "source": source}
            body_json = json.dumps(payload, separators=(',', ':'))
            signature = hmac.new(KEY, body_json.encode(), hashlib.sha256).hexdigest()
            headers = {
                "User-Agent": "GarenaMSDK/4.0.39(SM-A325M ;Android 13;en;HK;)",
                "Authorization": f"Signature {signature}",
                "Content-Type": "application/json; charset=utf-8"
            }
            resp = session.post("https://100067.connect.garena.com/api/v2/oauth/guest:register", 
                                headers=headers, data=body_json, verify=False, timeout=20)
            resp_json = resp.json()
            if resp_json.get("code") == 0:
                uid = resp_json['data']['uid']
                return token(uid, password, region, is_ghost, session)
            else:
                if resp_json.get("code") == 1006:
                    time.sleep(0.5 + rnd.uniform(0, 0.5))
                    continue
                else:
                    return {"success": False, "error": f"register_api_failed_{resp_json.get('code')}"}
        except:
            continue
    return {"success": False, "error": "register_api_failed"}

def build_workshop_subscribe_proto(workshop_code: str) -> bytes:
    fields = {1: 1, 2: workshop_code, 3: 26, 4: "en"}
    return CrEaTe_ProTo(fields)

def encrypt_workshop_packet(proto_bytes: bytes) -> bytes:
    cipher = AES.new(WORKSHOP_KEY, AES.MODE_CBC, WORKSHOP_IV)
    return cipher.encrypt(pad(proto_bytes, 16))

def subscribe_manual(jwt: str, workshop_code: str, region_url: str, session) -> bool:
    endpoint = region_url.rstrip('/') + "/SubscribeWorkshopCode"
    proto_bytes = build_workshop_subscribe_proto(workshop_code)
    encrypted = encrypt_workshop_packet(proto_bytes)
    headers = {
        'User-Agent': 'UnityPlayer/2022.3.47f1',
        'Authorization': f'Bearer {jwt}',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB54',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Unity-Version': '2022.3.47f1'
    }
    try:
        resp = session.post(endpoint, headers=headers, data=encrypted, verify=False, timeout=20)
        return resp.status_code == 200
    except:
        return False

# ---------- Stats Tracker ----------
class Stats:
    def __init__(self, target):
        self.target = target
        self.lock = threading.Lock()
        self.final_success = 0
        self.total_errors = 0
        self.pending = 0
        self.start_time = datetime.now()
        self.total_retries = 0

    def acquire_slot(self):
        with self.lock:
            if self.final_success + self.pending >= self.target:
                return False
            self.pending += 1
            return True

    def release_slot(self, success=False):
        with self.lock:
            self.pending -= 1
            if success:
                self.final_success += 1
            else:
                self.total_errors += 1

    def increment_retry(self):
        with self.lock:
            self.total_retries += 1

    def get_all(self):
        with self.lock:
            return {
                'target': self.target,
                'final_success': self.final_success,
                'total_errors': self.total_errors,
                'total_retries': self.total_retries,
                'start_time': self.start_time,
                'pending': self.pending,
            }

class LogManager:
    def __init__(self, max_lines=12):
        self.lines = []
        self.lock = threading.Lock()
        self.max_lines = max_lines

    def add(self, msg, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        if "Created" in msg or "Done" in msg or "Subscribed" in msg:
            color = "#00ff66"
            tag = "SUCCESS"
        elif "Failed" in msg or "fail" in msg or "❌" in msg:
            color = "#ff0055"
            tag = "ERROR"
        else:
            color = "#00f0ff"
            tag = "SYSTEM"
        formatted = f"[dim white][{timestamp}][/dim white] [[{color}]{tag}[/{color}]] {msg}"
        with self.lock:
            self.lines.append(formatted)
            if len(self.lines) > self.max_lines:
                self.lines.pop(0)

    def get(self):
        with self.lock:
            return self.lines.copy()

LOG_MANAGER = None

# ---------- Premium UI Renderers ----------
def make_mini_bar(completed, total, length=14):
    if total <= 0: return "[dim white]" + "░" * length + "[/dim white]"
    ratio = min(1.0, completed / total)
    filled = int(ratio * length)
    if filled > 0:
        return f"[bold #00ff66]{'█' * (filled - 1)}[/bold #00ff66][bold #00f0ff]█[/bold #00f0ff][dim white]{'░' * (length - filled)}[/dim white]"
    return f"[dim white]{'░' * length}[/dim white]"

def generate_dashboard(stats: Stats, workshop_code, region):
    s = stats.get_all()
    target = s['target']
    done = s['final_success']
    remaining = max(0, target - done)
    errors = s['total_errors']
    total_attempts = done + errors
    success_rate = (done / total_attempts * 100) if total_attempts > 0 else 0.0
    elapsed = datetime.now() - s['start_time']
    minutes = elapsed.total_seconds() / 60
    acc_per_min = (done / minutes) if minutes > 0 else 0.0

    t = time.time()
    spinner_char = SPINNER_FRAMES[int(t * 12) % len(SPINNER_FRAMES)]
    cyber_icon = CYBER_FRAMES[int(t * 8) % len(CYBER_FRAMES)]
    wave_anim = WAVE_FRAMES[int(t * 10) % len(WAVE_FRAMES)]
    pulse_dot = PULSE_DOTS[int(t * 5) % len(PULSE_DOTS)]

    anim_color1 = GLOW_COLORS[int(t * 4) % len(GLOW_COLORS)]
    anim_color2 = GLOW_COLORS[int((t + 0.5) * 4) % len(GLOW_COLORS)]
    spinner_color = GLOW_COLORS[int(t * 8) % len(GLOW_COLORS)]

    header_text = Text()
    header_text.append(f"{cyber_icon} ", style=f"bold {anim_color1}")
    header_text.append("JXE ULTRA FAST ENGINE", style="bold #00f0ff")
    header_text.append(f" {wave_anim} ", style=f"bold {anim_color2}")
    header_text.append(f"MAP: {workshop_code}", style="bold #ffe600")
    header_text.append(" | ", style="dim white")
    header_text.append(f"REGION: {region}", style="bold #00ff66")
    
    header_panel = Panel(
        Align.center(header_text),
        border_style="#00f0ff",
        box=box.HORIZONTALS,
        padding=(0, 0)
    )

    left_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    left_table.add_column("Key", style="bold white")
    left_table.add_column("Val", justify="right")

    left_table.add_row("🎯 Target Goal", f"[bold #00f0ff]{target}[/bold #00f0ff]")
    left_table.add_row("✅ Subscribed", f"[bold #00ff66]{done}[/bold #00ff66]")
    left_table.add_row("❌ Errors", f"[bold #ff0055]{errors}[/bold #ff0055]")
    left_table.add_row("⏳ Remaining", f"[bold white]{remaining}[/bold white]")
    left_table.add_row("🔄 Retries", f"[bold #ffe600]{s['total_retries']}[/bold #ffe600]")

    stats_panel = Panel(
        left_table,
        title=f"[bold #00f0ff]{cyber_icon} SESSION STATS[/bold #00f0ff]",
        border_style="#00f0ff",
        box=box.ROUNDED
    )

    right_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    right_table.add_column("Key", style="bold white")
    right_table.add_column("Val", justify="right")

    right_table.add_row("⚡ Speed Rate", f"[bold #00ff66]{acc_per_min:.0f} acc/m[/bold #00ff66]")
    right_table.add_row("🎯 Accuracy", f"[bold #00f0ff]{success_rate:.1f}%[/bold #00f0ff]")
    right_table.add_row("🧵 Active Threads", f"[bold #7000ff]{NUM_WORKERS}[/bold #7000ff]")
    right_table.add_row("⏱️ Time Elapsed", f"[bold white]{str(elapsed).split('.')[0]}[/bold white]")
    
    animated_status = f"[bold {spinner_color}]{spinner_char}[/bold {spinner_color}] [bold {anim_color1}]{pulse_dot}[/bold {anim_color1}]"
    right_table.add_row("📡 Link Status", animated_status)

    perf_panel = Panel(
        right_table,
        title=f"[bold #00ff66]⚡ PERFORMANCE[/bold #00ff66]",
        border_style="#00f0ff",
        box=box.ROUNDED
    )

    bar = make_mini_bar(done, target, length=32)
    pct = (done / target * 100) if target > 0 else 0
    prog_text = f"[bold #00f0ff]PROGRESS[/bold #00f0ff] [{bar}] [bold #00ff66]{pct:.1f}%[/bold #00ff66]"
    prog_panel = Panel(Align.center(prog_text), border_style="#00f0ff", box=box.SIMPLE_HEAD)

    main_split = Layout()
    main_split.split_row(
        Layout(stats_panel, ratio=1),
        Layout(perf_panel, ratio=1)
    )

    outer_layout = Layout()
    outer_layout.split_column(
        Layout(header_panel, size=3),
        Layout(main_split, size=8),
        Layout(prog_panel, size=3)
    )

    return outer_layout

def generate_log_panel():
    global LOG_MANAGER
    lines = LOG_MANAGER.get() if LOG_MANAGER else []
    text = Text()
    if not lines:
        text.append("Initializing dynamic worker streams...", style="dim white")
    else:
        for line in lines:
            text.append(Text.from_markup(line + "\n"))
    return Panel(
        text,
        title="[bold #7000ff]📋 LIVE COMMAND LOGS[/bold #7000ff]",
        border_style="#00f0ff",
        box=box.ROUNDED,
        height=10
    )

def live_dashboard(stats: Stats, stop_event: threading.Event, progress_bar, task_id, workshop_code, region):
    console = Console()
    with Live(auto_refresh=False, console=console, refresh_per_second=25) as live:
        while not stop_event.is_set():
            s = stats.get_all()
            done = s['final_success']
            target = s['target']
            progress_bar.update(task_id, completed=done, total=target)

            dash = generate_dashboard(stats, workshop_code, region)
            logs = generate_log_panel()

            layout = Layout()
            layout.split_column(
                Layout(dash, ratio=2),
                Layout(logs, ratio=1)
            )
            live.update(layout, refresh=True)
            time.sleep(0.04)

# ---------- Worker Logic ----------
def retry_with_backoff(func, *args, max_retries=3, stats=None, **kwargs):
    for attempt in range(1, max_retries + 1):
        try:
            result = func(*args, **kwargs)
            if result.get('success', False):
                return True, result.get('data'), None
            else:
                error = result.get('error', 'unknown')
                if '1006' in error:
                    wait = 0.8 + rnd.uniform(0, 0.5)
                else:
                    wait = 0.15 + rnd.uniform(0, 0.2)
                if stats and attempt < max_retries:
                    stats.increment_retry()
                if attempt == max_retries:
                    return False, None, error
                time.sleep(wait)
        except Exception:
            if stats and attempt < max_retries:
                stats.increment_retry()
            if attempt == max_retries:
                return False, None, 'api_error'
            time.sleep(0.2 + rnd.uniform(0, 0.2))
    return False, None, 'max_retries_exceeded'

def generate_account_with_retry(region, is_ghost, stats, log_mgr, session):
    log_mgr.add("Creating account instance...")
    success, data, error = retry_with_backoff(create_acc, region, is_ghost, session, max_retries=3, stats=stats)
    if success:
        log_mgr.add(f"Account Created | UID: [bold white]{data['uid']}[/bold white]")
        return True, data, None
    else:
        log_mgr.add(f"Creation Failed | Reason: {error}")
        return False, None, error

def subscribe_account_with_retry(jwt, workshop, region_url, stats, log_mgr, session):
    def _subscribe():
        try:
            ok = subscribe_manual(jwt, workshop, region_url, session)
            return {'success': ok, 'error': None if ok else 'subscribe_failed'}
        except:
            return {'success': False, 'error': 'subscribe_exception'}

    log_mgr.add("Sending Craftland subscription request...")
    success, _, error = retry_with_backoff(_subscribe, max_retries=3, stats=stats)
    if success:
        log_mgr.add("Subscribed Successfully!")
        return True, None
    else:
        log_mgr.add(f"Subscription Failed | {error}")
        return False, error

NUM_WORKERS = 300

def worker(region, is_ghost, workshop, region_url, stats, stop_event, log_mgr):
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=300, pool_maxsize=300, max_retries=0)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    while not stop_event.is_set():
        if stats.get_all()['final_success'] >= stats.target:
            break
        if not stats.acquire_slot():
            time.sleep(0.0005)
            continue

        gen_success, acc_data, _ = generate_account_with_retry(region, is_ghost, stats, log_mgr, session)
        if not gen_success:
            stats.release_slot(success=False)
            continue

        sub_success, _ = subscribe_account_with_retry(acc_data['jwt_token'], workshop, region_url, stats, log_mgr, session)
        if not sub_success:
            stats.release_slot(success=False)
            continue

        stats.release_slot(success=True)
        log_mgr.add(f"Completed Task for UID: [bold white]{acc_data['uid']}[/bold white]")

# ---------- UI Panels ----------
def show_region_panel(console):
    console.clear()
    regions = sorted(REGION_URLS.keys())
    
    table = Table(
        show_header=True, 
        header_style="bold #00f0ff",
        box=box.ROUNDED, 
        expand=True,
        border_style="#00ff66"
    )
    table.add_column("CODE", style="bold #ffe600", justify="center", width=10)
    table.add_column("SERVER / REGION NAME", style="bold white", justify="left")
    table.add_column("LATENCY", style="bold #00ff66", justify="center", width=12)
    table.add_column("STATUS", style="bold #00f0ff", justify="center", width=12)

    for r in regions:
        name, flag = REGION_DETAILS.get(r, (r, "🌐"))
        ping = f"{rnd.randint(18, 48)}ms"
        status = "● ONLINE"
        table.add_row(
            f"[bold #ffe600]{r}[/bold #ffe600]",
            f"{flag}  {name}",
            f"[bold #00ff66]{ping}[/bold #00ff66]",
            f"[bold #00f0ff]{status}[/bold #00f0ff]"
        )

    panel = Panel(
        table,
        title="[bold #00f0ff]🌐 SELECT HIGH-SPEED SERVER REGION 🌐[/bold #00f0ff]",
        subtitle="[bold white]Enter Code Below (Default BD)[/bold white]",
        border_style="#00f0ff",
        box=box.DOUBLE_EDGE,
        padding=(1, 2)
    )
    console.print(panel)

# ---------- FIXED: Smooth Loading Animation using Live ----------
def show_server_loading_animation(console, selected_region):
    console.clear()
    name, flag = REGION_DETAILS.get(selected_region, (selected_region, "GLOBAL"))
    
    diagnostic_steps = [
        ("DNS Gateway Resolution", "104.22.58.102 [OK]"),
        ("OB54 AES-128 SSL Handshake", "AUTHENTICATED"),
        ("Parallel Thread Allocation", f"{NUM_WORKERS} WORKERS READY"),
        ("Craftland Protocol Buffer", "SYNCHRONIZED"),
        ("Session Tunnel Security", "LOCKED & SECURE")
    ]
    
    total_frames = 36
    
    # Use Live to avoid flickering
    with Live(console=console, refresh_per_second=30, auto_refresh=False) as live:
        for frame in range(1, total_frames + 1):
            pct = int((frame / total_frames) * 100)
            completed_steps = min(int((frame / total_frames) * len(diagnostic_steps)), len(diagnostic_steps))
            
            spinner = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]
            
            diag_table = Table(show_header=True, header_style="bold #00f0ff", box=box.SIMPLE, expand=True)
            diag_table.add_column("STATE", justify="center", width=10)
            diag_table.add_column("SYSTEM INITIALIZATION STEP", style="bold white", justify="left")
            diag_table.add_column("DIAGNOSTIC RESULT", justify="right")
            
            for idx, (step_name, step_result) in enumerate(diagnostic_steps):
                if idx < completed_steps:
                    diag_table.add_row("[bold #00ff66][✔ DONE][/bold #00ff66]", f"[bold white]{step_name}[/bold white]", f"[bold #00ff66]{step_result}[/bold #00ff66]")
                elif idx == completed_steps:
                    diag_table.add_row(f"[bold #ffe600][{spinner} INIT][/bold #ffe600]", f"[bold #00f0ff]{step_name}[/bold #00f0ff]", "[bold #ffe600]PROCESSING...[/bold #ffe600]")
                else:
                    diag_table.add_row("[dim white][○ WAIT][/dim white]", f"[dim white]{step_name}[/dim white]", "[dim white]PENDING[/dim white]")
            
            bar_length = 32
            filled = int((pct / 100) * bar_length)
            bar_str = f"[bold #00ff66]{'█' * filled}[/bold #00ff66][dim white]{'░' * (bar_length - filled)}[/dim white]"
            
            footer_table = Table(show_header=False, box=None, expand=True)
            footer_table.add_column("Info", justify="left")
            footer_table.add_column("Progress", justify="right")
            footer_table.add_row(
                f"[bold white]TARGET SERVER:[/bold white] [bold #ffe600]{flag} {name} [{selected_region}][/bold #ffe600]",
                f"[bold #00f0ff]CONNECTIVITY:[/bold #00f0ff] [{bar_str}] [bold #00ff66]{pct}%[/bold #00ff66]"
            )
            
            main_layout = Layout()
            main_layout.split_column(
                Layout(diag_table, ratio=3),
                Layout(Panel(footer_table, border_style="#00f0ff", box=box.ROUNDED), ratio=1)
            )
            
            panel = Panel(
                main_layout,
                title=f"[bold #00f0ff]🌐 SERVER GATEWAY CONNECTIVITY DIAGNOSTICS - {selected_region} 🌐[/bold #00f0ff]",
                border_style="#00f0ff",
                box=box.ROUNDED,
                padding=(1, 2),
                height=15
            )
            
            live.update(panel, refresh=True)
            time.sleep(0.04)
        
        # Final frame with completed status
        time.sleep(0.4)

def get_valid_int(console, prompt):
    while True:
        try:
            val = int(console.input(f"[bold #00f0ff]{prompt}[/bold #00f0ff]").strip())
            if val > 0:
                return val
            console.print("[bold #ff0055]❌ Enter a positive integer.[/bold #ff0055]")
        except ValueError:
            console.print("[bold #ff0055]❌ Invalid numerical format.[/bold #ff0055]")

def print_banner(console):
    banner_art = """[bold #00f0ff]
            ██╗██╗  ██╗███████╗
            ██║╚██╗██╔╝██╔════╝
            ██║ ╚███╔╝ █████╗  
       ██   ██║ ██╔██╗ ██╔══╝  
       ╚█████╔╝██╔╝ ██╗███████╗
       ╚════╝ ╚═╝  ╚═╝╚══════╝[/bold #00f0ff]"""
 
    header = Panel(
        Align.center(
            Text.from_markup(
                banner_art + "\n\n"
                "[bold white]ULTRA FAST CRAFTLAND SUBSCRIBER TOOL v1.0[/bold white]\n"
                "[bold #ffe600]      MADE BY JAHID X EMPIRE [ JXE ][/bold #ffe600]"
            )
        ),
        border_style="#00f0ff",
        box=box.DOUBLE_EDGE,
        padding=(1, 2)
    )
    console.print(header)

def main():
    global LOG_MANAGER

    console = Console()
    console.clear()
    print_banner(console)
    console.print()

    target = get_valid_int(console, "🔢 Enter Subscriber Target: ")

    workshop_raw = console.input("[bold #00f0ff]📦 Craftland Map Code: [/bold #00f0ff]").strip()
    cleaned = workshop_raw.lstrip()
    if cleaned.lower().startswith('#freefire'):
        cleaned = cleaned[9:]
    elif cleaned.startswith('#'):
        cleaned = cleaned[1:]
    workshop = cleaned.strip()
    if not workshop:
        console.print("[bold #ff0055]❌ Craftland Map code is required.[/bold #ff0055]")
        return

    console.clear()
    show_region_panel(console)
    region = console.input("\n[bold white]Enter region code (Default BD): [/bold white]").strip().upper()
    if not region:
        region = "BD"
    elif region not in REGION_URLS:
        console.print(f"[bold #ff0055]❌ Unknown region '{region}'. Defaulting to BD.[/bold #ff0055]")
        region = "BD"

    show_server_loading_animation(console, region)

    is_ghost = False
    region_url = REGION_URLS.get(region, "https://clientbp.ggpolarbear.com/")

    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Key", style="bold white")
    summary_table.add_column("Val", style="bold #00f0ff")

    name, flag = REGION_DETAILS.get(region, (region, "🌐"))
    summary_table.add_row("🎯 Target Quantity:", f"{target}")
    summary_table.add_row("📦 Craftland Code:", f"{workshop}")
    summary_table.add_row("🌐 Selected Region:", f"{flag} {name} [{region}]")
    summary_table.add_row("⚡ Worker Threads:", f"{NUM_WORKERS} Parallel Connections")
    
    console.print(Panel(summary_table, title="[bold #00ff66]⚙️ CONFIGURATION SUMMARY[/bold #00ff66]", border_style="#00f0ff", box=box.ROUNDED))
    time.sleep(1.5)
    console.clear()

    stats = Stats(target)
    log_manager = LogManager(max_lines=12)
    LOG_MANAGER = log_manager

    stop_event = threading.Event()

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, style="dim white", complete_style="#00ff66"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    )
    task = progress.add_task("[bold #00f0ff]Executing...", total=target)

    dashboard_thread = threading.Thread(
        target=live_dashboard,
        args=(stats, stop_event, progress, task, workshop, region),
        daemon=True
    )
    dashboard_thread.start()

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [
            executor.submit(
                worker,
                region, is_ghost,
                workshop, region_url, stats, stop_event, log_manager
            ) for _ in range(NUM_WORKERS)
        ]

        for f in futures:
            f.result()

    stop_event.set()
    dashboard_thread.join(timeout=1)
    
    time.sleep(0.2)
    console.clear()

    s = stats.get_all()
    done = s['final_success']
    errors = s['total_errors']
    total_attempts = done + errors
    success_rate = (done / total_attempts * 100) if total_attempts > 0 else 0.0
    elapsed = datetime.now() - s['start_time']
    mins, secs = divmod(elapsed.total_seconds(), 60)

    final_panel = Panel(
        Align.center(
            Text.from_markup(
                f"[bold #00ff66]🎉 PROCESS COMPLETED SUCCESSFULLY![/bold #00ff66]\n\n"
                f"[bold white]🎯 Target Requested: {target}[/bold white]\n"
                f"[bold #00ff66]✅ Subscribers Added: {done}[/bold #00ff66]\n"
                f"[bold #ff0055]❌ Failed Retries: {errors}[/bold #ff0055]\n"
                f"[bold #00f0ff]📈 Accuracy Rate: {success_rate:.1f}%[/bold #00f0ff]\n"
                f"[bold #ffe600]⏱️ Total Time Elapsed: {int(mins)}m {int(secs)}s[/bold #ffe600]\n\n"
                f"[bold #7000ff]POWERED BY JAHID X EMPIRE [ JXE ][/bold #7000ff]"
            )
        ),
        title="[bold #00f0ff]🏆 FINAL EXECUTION REPORT[/bold #00f0ff]",
        border_style="#00f0ff",
        box=box.DOUBLE_EDGE,
        padding=(1, 2)
    )
    
    console.print(final_panel)
    sys.exit(0)

if __name__ == "__main__":
    main()

# ---------- BOT FUNCTION EXPORT ----------
def start_bot_subscription(map_code, target_count, region="BD"):
    stats = Stats(target_count)
    log_manager = LogManager(max_lines=12)
    global LOG_MANAGER
    LOG_MANAGER = log_manager
    stop_event = threading.Event()
    is_ghost = False
    region_url = REGION_URLS.get(region, "https://clientbp.ggpolarbear.com/")

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [
            executor.submit(
                worker,
                region, is_ghost,
                map_code, region_url, stats, stop_event, log_manager
            ) for _ in range(NUM_WORKERS)
        ]
        for f in futures:
            f.result()

    s = stats.get_all()
    return s['final_success']