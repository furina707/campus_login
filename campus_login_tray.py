#!/usr/bin/env python3
"""
校园网自动登录 - 系统托盘版 v10.0 (零第三方依赖)
仅使用 Python 标准库 + 系统共享库 (ctypes)
"""

import sys
import os
import time
import threading
import urllib.request
import urllib.parse
import subprocess
import re
import struct
import zlib
import ctypes
from datetime import datetime
from typing import Optional, Callable

# ==================== ctypes 加载 GTK/AppIndicator ====================

try:
    _gtk = ctypes.CDLL("libgtk-3.so.0")
    _gobject = ctypes.CDLL("libgobject-2.0.so.0")
    _glib = ctypes.CDLL("libglib-2.0.so.0")
    _appindicator = ctypes.CDLL("libappindicator3.so.1")
    HAS_TRAY = True
except OSError:
    HAS_TRAY = False

G_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
_gtk_menu_items = []
_gtk_callbacks = []


def _gtk_init():
    _gtk.gtk_init(ctypes.POINTER(ctypes.c_int)(), ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p))())


def _gtk_menu_new():
    _gtk.gtk_menu_new.restype = ctypes.c_void_p
    return _gtk.gtk_menu_new()


def _gtk_menu_item_new_with_label(label: str):
    _gtk.gtk_menu_item_new_with_label.restype = ctypes.c_void_p
    _gtk.gtk_menu_item_new_with_label.argtypes = [ctypes.c_char_p]
    return _gtk.gtk_menu_item_new_with_label(label.encode('utf-8'))


def _gtk_separator_menu_item_new():
    _gtk.gtk_separator_menu_item_new.restype = ctypes.c_void_p
    return _gtk.gtk_separator_menu_item_new()


def _gtk_menu_shell_append(menu, item):
    _gtk.gtk_menu_shell_append.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _gtk.gtk_menu_shell_append(menu, item)


def _gtk_widget_show_all(widget):
    _gtk.gtk_widget_show_all.argtypes = [ctypes.c_void_p]
    _gtk.gtk_widget_show_all(widget)


def _gtk_widget_set_sensitive(widget, sensitive):
    _gtk.gtk_widget_set_sensitive.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _gtk.gtk_widget_set_sensitive(widget, 1 if sensitive else 0)


def _gtk_menu_item_set_label(item, label: str):
    _gtk.gtk_menu_item_set_label.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    _gtk.gtk_menu_item_set_label(item, label.encode('utf-8'))


def _g_signal_connect(instance, signal: str, callback, data=None):
    _gobject.g_signal_connect_data.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
    ]
    _gobject.g_signal_connect_data.restype = ctypes.c_ulong
    cb = G_CALLBACK(callback)
    _gtk_callbacks.append(cb)
    return _gobject.g_signal_connect_data(
        instance, signal.encode('utf-8'), cb,
        None, None, 0
    )


def _g_idle_add(callback):
    G_SOURCE_FUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
    cb = G_SOURCE_FUNC(callback)
    _gtk_callbacks.append(cb)
    _glib.g_idle_add.argtypes = [G_SOURCE_FUNC, ctypes.c_void_p]
    _glib.g_idle_add(cb, None)


def _g_timeout_add_seconds(seconds, callback):
    G_SOURCE_FUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
    cb = G_SOURCE_FUNC(callback)
    _gtk_callbacks.append(cb)
    _glib.g_timeout_add_seconds.argtypes = [ctypes.c_uint, G_SOURCE_FUNC, ctypes.c_void_p]
    _glib.g_timeout_add_seconds(seconds, cb, None)


def _app_indicator_new(id_str: str, icon_path: str):
    _appindicator.app_indicator_new.restype = ctypes.c_void_p
    _appindicator.app_indicator_new.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    return _appindicator.app_indicator_new(
        id_str.encode('utf-8'), icon_path.encode('utf-8'), 0
    )


def _app_indicator_set_status(indicator, status: int):
    _appindicator.app_indicator_set_status.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _appindicator.app_indicator_set_status(indicator, status)


def _app_indicator_set_icon(indicator, icon_path: str):
    _appindicator.app_indicator_set_icon.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    _appindicator.app_indicator_set_icon(indicator, icon_path.encode('utf-8'))


def _app_indicator_set_menu(indicator, menu):
    _appindicator.app_indicator_set_menu.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _appindicator.app_indicator_set_menu(indicator, menu)


def _app_indicator_set_label(indicator, label: str, guide: str = ""):
    _appindicator.app_indicator_set_label.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    _appindicator.app_indicator_set_label(indicator, label.encode('utf-8'), guide.encode('utf-8'))


def _gtk_main():
    _gtk.gtk_main()


def _gtk_main_quit():
    _gtk.gtk_main_quit()

# ==================== 配置 ====================

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
CHARSET_PATH = os.path.join(MODEL_DIR, 'charset.txt')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'logs', 'tray.log')

LOGIN_URL = "http://218.200.239.185:8888/portalserver/user/unionautologin.do"
USERNAME = "SCXY15982477461"
PASSWORD = "065968"

CHECK_INTERVAL = 30
MAX_RETRIES = 3
RETRY_INTERVAL = 5

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# ==================== 纯 Python PNG 解码器 ====================

def _png_decode(data: bytes):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("Not a PNG file")
    
    pos = 8
    chunks = {}
    idat_data = b''
    
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        crc = struct.unpack('>I', data[pos+8+length:pos+12+length])[0]
        
        if chunk_type == b'IHDR':
            chunks['IHDR'] = struct.unpack('>IIBBBBB', chunk_data)
        elif chunk_type == b'IDAT':
            idat_data += chunk_data
        elif chunk_type == b'IEND':
            break
        
        pos += 12 + length
    
    width, height, bit_depth, color_type = chunks['IHDR'][:4]
    
    raw = zlib.decompress(idat_data)
    
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type, 1)
    stride = width * channels * (bit_depth // 8)
    
    pixels = []
    scanline = stride + 1
    prev_row = bytearray(stride)
    
    for y in range(height):
        start = y * scanline + 1
        filt = raw[start - 1]
        row = bytearray(raw[start:start + stride])
        
        if filt == 0:
            pass
        elif filt == 1:
            for i in range(len(row)):
                a = row[i - channels] if i >= channels else 0
                row[i] = (row[i] + a) & 0xFF
        elif filt == 2:
            for i in range(len(row)):
                b = prev_row[i]
                row[i] = (row[i] + b) & 0xFF
        elif filt == 3:
            for i in range(len(row)):
                a = row[i - channels] if i >= channels else 0
                b = prev_row[i]
                row[i] = (row[i] + ((a + b) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(len(row)):
                a = row[i - channels] if i >= channels else 0
                b = prev_row[i]
                c = prev_row[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                row[i] = (row[i] + pr) & 0xFF
        
        pixels.append(list(row))
        prev_row = row
    
    gray = []
    for row in pixels:
        if color_type == 0:
            gray.append(row[:])
        elif color_type == 2:
            gray.append([row[i*3] for i in range(width)])
        elif color_type == 4:
            gray.append([row[i*2] for i in range(width)])
        elif color_type == 6:
            gray.append([row[i*4] for i in range(width)])
    
    return gray, width, height


def _resize_bilinear(img, new_w, new_h):
    old_w = len(img[0])
    old_h = len(img)
    result = []
    for y in range(new_h):
        src_y = (y + 0.5) * old_h / new_h - 0.5
        y0 = int(src_y)
        y1 = min(y0 + 1, old_h - 1)
        fy = src_y - y0
        row = []
        for x in range(new_w):
            src_x = (x + 0.5) * old_w / new_w - 0.5
            x0 = int(src_x)
            x1 = min(x0 + 1, old_w - 1)
            fx = src_x - x0
            val = (img[y0][x0] * (1-fx) * (1-fy) +
                   img[y0][x1] * fx * (1-fy) +
                   img[y1][x0] * (1-fx) * fy +
                   img[y1][x1] * fx * fy)
            row.append(val)
        result.append(row)
    return result


def _argmax_2d(matrix):
    max_val = matrix[0][0]
    max_i, max_j = 0, 0
    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            if val > max_val:
                max_val = val
                max_i, max_j = i, j
    return max_i, max_j


def _argmax_1d(arr):
    max_val = arr[0]
    max_idx = 0
    for i, val in enumerate(arr):
        if val > max_val:
            max_val = val
            max_idx = i
    return max_idx


# ==================== ctypes ONNX Runtime ====================

HAS_ONNX = False
_ort = None

try:
    _ort = ctypes.CDLL("libonnxruntime.so.1")
    HAS_ONNX = True
except OSError:
    try:
        _ort = ctypes.CDLL("libonnxruntime.so")
        HAS_ONNX = True
    except OSError:
        HAS_ONNX = False


class OrtSession:
    def __init__(self, model_path: str):
        if not HAS_ONNX:
            raise RuntimeError("libonnxruntime not found")
        
        self.session_ptr = ctypes.c_void_p()
        
        _ort.CreateSession.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        _ort.CreateSession.restype = ctypes.c_int
        status = _ort.CreateSession(model_path.encode('utf-8'), ctypes.byref(self.session_ptr), None)
        if status != 0:
            raise RuntimeError(f"CreateSession failed: {status}")
        
        self.input_names = ['input']
        self.input_shape = [1, 1, 64, -1]

    def run(self, input_data):
        input_flat = []
        for row in input_data[0][0]:
            input_flat.extend(row)
        
        n = len(input_flat)
        FloatArray = ctypes.c_float * n
        arr = FloatArray(*input_flat)
        
        shape = [1, 1, len(input_data[0][0]), len(input_data[0][0][0])]
        Int64Array = ctypes.c_int64 * 4
        shape_arr = Int64Array(*shape)

        ort_input = ctypes.Structure
        ort_input._fields_ = [
            ('name', ctypes.c_char_p),
            ('data_type', ctypes.c_int),
            ('dimensions', ctypes.c_int),
            ('shape', ctypes.POINTER(ctypes.c_int64)),
            ('data', ctypes.c_void_p),
        ]
        
        inp = ort_input()
        inp.name = b'input'
        inp.data_type = 1
        inp.dimensions = 4
        inp.shape = shape_arr
        inp.data = ctypes.cast(arr, ctypes.c_void_p)
        
        inputs_arr = (ctypes.POINTER(type(ort_input)) * 1)(ctypes.pointer(inp))
        
        output_ptr = ctypes.c_void_p()
        outputs = (ctypes.POINTER(ctypes.c_void_p) * 1)(ctypes.byref(output_ptr))
        
        _ort.Run.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
            ctypes.c_size_t,
            ctypes.c_void_p,
        ]
        _ort.Run.restype = ctypes.c_int
        
        status = _ort.Run(
            self.session_ptr, None,
            inputs_arr, 1,
            outputs, None, 1,
            None
        )
        if status != 0:
            raise RuntimeError(f"Run failed: {status}")
        
        raw_output = ctypes.cast(output_ptr, ctypes.POINTER(ctypes.c_float))
        seq_len = 66
        class_count = 11
        result = [[0.0] * class_count for _ in range(seq_len)]
        for t in range(seq_len):
            for c in range(class_count):
                result[t][c] = raw_output[t * class_count + c]
        
        return [result]


# ==================== ddddocr 核心代码 (纯标准库) ====================

def load_charset(charset_path: str) -> list:
    charset = []
    try:
        with open(charset_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    idx, char = line.split(': ', 1)
                    charset.append(eval(char))
        return charset
    except Exception as e:
        print(f"Charset load failed: {e}")
        return ["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]

DEFAULT_CHARSET = load_charset(CHARSET_PATH)


class DdddOcr:
    def __init__(self):
        model_path = os.path.join(MODEL_DIR, 'common_old.onnx')
        self.session = OrtSession(model_path)
        self.charset = DEFAULT_CHARSET
    
    def _preprocess_image(self, img_bytes: bytes):
        pixels, width, height = _png_decode(img_bytes)
        
        target_height = 64
        target_width = int(width * (target_height / height))
        
        resized = _resize_bilinear(pixels, target_width, target_height)
        
        normalized = [[v / 255.0 for v in row] for row in resized]
        
        return [[[normalized]]]
    
    def _ctc_decode(self, predicted_indices: list) -> list:
        decoded_indices = []
        prev_idx = None
        for idx in predicted_indices:
            if idx != prev_idx and idx != 0:
                decoded_indices.append(idx)
            prev_idx = idx
        return decoded_indices
    
    def classification(self, img_content: bytes) -> str:
        processed_image = self._preprocess_image(img_content)
        
        outputs = self.session.run(processed_image)
        output = outputs[0]
        
        predicted_indices = [_argmax_1d(timestep) for timestep in output]
        
        decoded_indices = self._ctc_decode(predicted_indices)
        result = ''.join([self.charset[idx] for idx in decoded_indices 
                         if 0 <= idx < len(self.charset)])
        
        return result

# ==================== 桌面通知 ====================

def show_notification(title: str, message: str):
    try:
        subprocess.run([
            'notify-send',
            '-u', 'normal',
            '-t', '5000',
            title,
            message
        ], check=False, timeout=2)
    except Exception as e:
        print(f"Notification failed: {e}")

# ==================== 校园网登录服务 ====================

class CampusLoginService:
    def __init__(self):
        self.running = False
        self.paused = False
        self.ocr_engine = DdddOcr()
        self.status_callback: Optional[Callable] = None
        self.log_callback: Optional[Callable] = None
        self.notification_callback: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._status_lock = threading.Lock()
        
        self.stats = {
            'login_count': 0,
            'success_count': 0,
            'fail_count': 0,
            'last_login': None,
            'start_time': None,
            'check_count': 0,
            'connected_count': 0,
            'disconnected_count': 0
        }
    
    def set_callbacks(self, status_cb=None, log_cb=None, notification_cb=None):
        self.status_callback = status_cb
        self.log_callback = log_cb
        self.notification_callback = notification_cb or show_notification
    
    def _log(self, message: str, level='INFO'):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        safe_msg = message.replace('✓', '[OK]').replace('✗', '[X]').replace('⚠️', '[!]').replace('⚠', '[!]')
        formatted_msg = f"[{timestamp}] [{level}] {safe_msg}"
        
        print(formatted_msg, flush=True)
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(formatted_msg + '\n')
        
        if self.log_callback:
            self.log_callback(formatted_msg)
    
    def _update_status(self, status: str):
        if self.status_callback:
            if HAS_TRAY:
                def _do_update(_):
                    self.status_callback(status)
                    return 0
                _g_idle_add(_do_update)
            else:
                self.status_callback(status)
    
    def _notify(self, title: str, message: str):
        safe_title = title.replace('✓', '[OK]').replace('✗', '[X]').replace('⚠️', '[!]').replace('⚠', '[!]')
        safe_message = message.replace('✓', '[OK]').replace('✗', '[X]').replace('⚠️', '[!]').replace('⚠', '[!]')
        if self.notification_callback:
            self.notification_callback(safe_title, safe_message)
    
    def check_network(self) -> bool:
        test_urls = [
            ('http://www.baidu.com', 'Baidu'),
            ('http://www.qq.com', 'QQ'),
            ('http://www.aliyun.com', 'AliYun')
        ]
        
        for url, name in test_urls:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                start_time = time.time()
                urllib.request.urlopen(req, timeout=5)
                elapsed = time.time() - start_time
                self._log(f"Network OK via {name} ({elapsed:.2f}s)")
                return True
            except Exception as e:
                self._log(f"Network FAIL via {name}: {type(e).__name__}: {e}")
                continue
        
        return False
    
    def get_captcha(self) -> bytes:
        url = "http://218.200.239.185:8888/portalserver/captcha.do"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://218.200.239.185:8888/portalserver/login/index.do'
        }
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=10)
        return response.read()
    
    def login(self, captcha_code: str) -> tuple:
        data = {
            'userId': USERNAME,
            'password': PASSWORD,
            'captcha': captcha_code,
            'service': '',
            'queryString': '',
            'operatorPwd': '',
            'userType': '2',
            'validCode': '',
            'passwordEncrypt': 'false'
        }
        
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        req = urllib.request.Request(LOGIN_URL, data=encoded_data, headers=headers)
        response = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        
        if '"result":"success"' in response:
            return True, "Success"
        elif '"result":"fail"' in response:
            match = re.search(r'"message":"([^"]+)"', response)
            error_msg = match.group(1) if match else "Failed"
            return False, error_msg
        else:
            return False, "Unknown"
    
    def do_login(self) -> bool:
        self._log("Attempting login...")
        self._notify("Campus Login", "Trying to login...")
        
        for attempt in range(MAX_RETRIES):
            try:
                self._log(f"Attempt {attempt + 1}/{MAX_RETRIES}")
                
                captcha_img = self.get_captcha()
                
                debug_dir = os.path.join(os.path.dirname(__file__), 'debug')
                os.makedirs(debug_dir, exist_ok=True)
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                with open(os.path.join(debug_dir, f'captcha_{ts}.png'), 'wb') as f:
                    f.write(captcha_img)
                
                captcha_code = self.ocr_engine.classification(captcha_img)
                self._log(f"Captcha: {captcha_code}")
                
                if not (captcha_code.isdigit() and len(captcha_code) == 4):
                    self._log("Invalid captcha")
                    time.sleep(RETRY_INTERVAL)
                    continue
                
                success, message = self.login(captcha_code)
                self.stats['last_login'] = datetime.now()
                
                if success:
                    self.stats['login_count'] += 1
                    self.stats['success_count'] += 1
                    self._log(f"[OK] Login success!", 'SUCCESS')
                    self._notify("Campus Login", "[OK] Login successful!")
                    
                    time.sleep(2)
                    if self.check_network():
                        self._log("Network verified", 'SUCCESS')
                        return True
                    else:
                        self._log("Network verify failed", 'WARNING')
                        continue
                else:
                    self.stats['login_count'] += 1
                    self.stats['fail_count'] += 1
                    self._log(f"[X] Login failed: {message}", 'ERROR')
                    
            except urllib.error.HTTPError as e:
                self._log(f"HTTP Error {e.code}: {e.reason} (URL: {e.url})", 'ERROR')
            except urllib.error.URLError as e:
                self._log(f"URL Error: {e.reason}", 'ERROR')
            except ConnectionResetError:
                self._log("Connection reset by server", 'ERROR')
            except ConnectionRefusedError:
                self._log("Connection refused by server", 'ERROR')
            except TimeoutError:
                self._log("Connection timeout", 'ERROR')
            except Exception as e:
                self._log(f"Error: {type(e).__name__}: {e}", 'ERROR')
            
            time.sleep(RETRY_INTERVAL)
        
        self._log("[X] All retries failed", 'ERROR')
        self._notify("Campus Login", "[X] All attempts failed")
        return False
    
    def run(self):
        self._log("=" * 60)
        self._log("CAMPUS NETWORK AUTO-LOGIN SERVICE STARTED")
        self._log(f"Interval: {CHECK_INTERVAL}s | Retries: {MAX_RETRIES}")
        self._log("=" * 60)
        
        self.stats['start_time'] = datetime.now()
        consecutive_failures = 0
        
        while self.running:
            while self.paused and self.running:
                time.sleep(1)
            
            if not self.running:
                break
            
            self.stats['check_count'] += 1
            network_ok = self.check_network()
            
            if network_ok:
                self.stats['connected_count'] += 1
                if consecutive_failures > 0:
                    msg = f"Network recovered ({consecutive_failures} failures)"
                    self._log(msg, 'SUCCESS')
                    self._notify("Campus Network", msg)
                consecutive_failures = 0
                self._update_status("Connected [OK]")
            else:
                self.stats['disconnected_count'] += 1
                consecutive_failures += 1
                msg = f"[!] Disconnected ({consecutive_failures}x)"
                self._log(msg, 'WARNING')
                self._update_status("Disconnected [!]")
                
                if consecutive_failures == 1:
                    self._notify("Campus Network", "[!] Disconnected!")
                
                if self.do_login():
                    consecutive_failures = 0
                    self._update_status("Connected [OK]")
                else:
                    self._update_status("Login Failed [X]")
            
            for _ in range(CHECK_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)
        
        self._log("Service stopped")
        self._update_status("Stopped")
    
    def start(self):
        if not self.running:
            self.running = True
            self.paused = False
            self._thread = threading.Thread(target=self.run, daemon=True)
            self._thread.start()
    
    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)
    
    def pause(self):
        self.paused = True
        self._update_status("Paused")
    
    def resume(self):
        self.paused = False
        self._update_status("Running...")
    
    def get_stats(self) -> dict:
        return self.stats.copy()

# ==================== 图标路径 ====================

ICON_DIR = os.path.join(os.path.dirname(__file__), 'icons')
ICON_NORMAL = os.path.join(ICON_DIR, 'icon_normal.png')
ICON_CONNECTED = os.path.join(ICON_DIR, 'icon_connected.png')
ICON_ERROR = os.path.join(ICON_DIR, 'icon_error.png')
ICON_PAUSED = os.path.join(ICON_DIR, 'icon_paused.png')

# ==================== AppIndicator3 系统托盘 ====================

class CampusLoginTray:
    def __init__(self):
        self.logs = []
        self.max_logs = 100
        self.current_status = "启动中..."
        self.menu_items = {}
        
        # 初始化服务
        self.service = CampusLoginService()
        self.service.set_callbacks(
            status_cb=self.update_indicator,
            log_cb=self.add_log,
            notification_cb=self.show_notification
        )
        
        if not HAS_TRAY:
            self._run_headless()
            return
        
        _gtk_init()
        
        # 创建 AppIndicator
        self.indicator = _app_indicator_new("campus-login", ICON_NORMAL)
        _app_indicator_set_status(self.indicator, 1)
        _app_indicator_set_icon(self.indicator, ICON_NORMAL)
        
        # 创建菜单
        self.menu = _gtk_menu_new()
        
        # 顶部：状态显示
        self.status_menu_item = _gtk_menu_item_new_with_label("状态加载中...")
        _gtk_widget_set_sensitive(self.status_menu_item, False)
        _gtk_menu_shell_append(self.menu, self.status_menu_item)
        
        _gtk_menu_shell_append(self.menu, _gtk_separator_menu_item_new())
        
        # 控制选项
        for label, key in [("开始监控", "start"), ("停止监控", "stop"), ("暂停/继续", "pause")]:
            item = _gtk_menu_item_new_with_label(label)
            _g_signal_connect(item, "activate", self._make_menu_cb(key))
            _gtk_menu_shell_append(self.menu, item)
            self.menu_items[key] = item
        
        _gtk_menu_shell_append(self.menu, _gtk_separator_menu_item_new())
        
        # 功能选项
        for label, key in [("立即检查", "check"), ("统计信息", "stats"), ("查看日志", "logs")]:
            item = _gtk_menu_item_new_with_label(label)
            _g_signal_connect(item, "activate", self._make_menu_cb(key))
            _gtk_menu_shell_append(self.menu, item)
            self.menu_items[key] = item
        
        _gtk_menu_shell_append(self.menu, _gtk_separator_menu_item_new())
        
        # 退出
        quit_item = _gtk_menu_item_new_with_label("退出程序")
        _g_signal_connect(quit_item, "activate", lambda w, d: self.on_quit())
        _gtk_menu_shell_append(self.menu, quit_item)
        
        _gtk_widget_show_all(self.menu)
        _app_indicator_set_menu(self.indicator, self.menu)
        
        # 定时更新状态
        _g_timeout_add_seconds(5, self._timer_update_status)
        
        self.update_indicator("Starting...")
        self.update_status_display()
        
        show_notification("Campus Login v9.0", "ctypes 版本 - 零 gi 依赖\n每30秒监控网络")
        self.service.start()
    
    def _make_menu_cb(self, key):
        def cb(widget, data):
            if key == "start": self.on_start()
            elif key == "stop": self.on_stop()
            elif key == "pause": self.on_pause_resume()
            elif key == "check": self.on_check_now()
            elif key == "stats": self.on_show_stats()
            elif key == "logs": self.on_show_logs()
        return cb
    
    def _timer_update_status(self, _=None):
        self.update_status_display()
        return 1
    
    def _run_headless(self):
        print("[!] No GTK/AppIndicator libraries, running headless mode")
        show_notification("Campus Login v9.0", "无图形界面模式\n每30秒监控网络")
        self.service.start()
        try:
            while self.service.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.service.stop()
    
    def update_indicator(self, status: str):
        if HAS_TRAY:
            if 'Connected' in status:
                _app_indicator_set_icon(self.indicator, ICON_CONNECTED)
                _app_indicator_set_label(self.indicator, f" {status}", "")
            elif 'Disconnected' in status or 'Failed' in status:
                _app_indicator_set_icon(self.indicator, ICON_ERROR)
                _app_indicator_set_label(self.indicator, f" {status}", "")
            elif 'Paused' in status:
                _app_indicator_set_icon(self.indicator, ICON_PAUSED)
                _app_indicator_set_label(self.indicator, f" {status}", "")
            else:
                _app_indicator_set_icon(self.indicator, ICON_NORMAL)
                _app_indicator_set_label(self.indicator, f" {status}", "")
        self.current_status = status
    
    def update_status_display(self):
        """更新菜单顶部的状态显示"""
        stats = self.service.get_stats()
        
        # 计算运行时间
        if stats['start_time']:
            elapsed = datetime.now() - stats['start_time']
            hours = int(elapsed.total_seconds() // 3600)
            minutes = int((elapsed.total_seconds() % 3600) // 60)
            seconds = int(elapsed.total_seconds() % 60)
            
            if hours > 0:
                runtime = f"{hours}小时{minutes}分"
            else:
                runtime = f"{minutes}分{seconds}秒"
        else:
            runtime = "未启动"
        
        # 构建状态文本
        if stats['check_count'] > 0:
            ok_rate = stats['connected_count'] / stats['check_count'] * 100
        else:
            ok_rate = 0
        
        status_lines = [
            f"状态: {self.current_status}",
            f"运行时间: {runtime}",
            f"网络检查: {stats['check_count']}次 (正常率{ok_rate:.0f}%)",
        ]
        
        if stats['login_count'] > 0:
            login_rate = stats['success_count'] / stats['login_count'] * 100
            status_lines.append(f"自动登录: {stats['login_count']}次 (成功率{login_rate:.0f}%)")
            if stats['last_login']:
                last_login_str = stats['last_login'].strftime('%H:%M:%S')
                status_lines.append(f"上次登录: {last_login_str}")
        else:
            status_lines.append("自动登录: 未触发 (网络正常)")
        
        status_text = "\n".join(status_lines)
        
        if HAS_TRAY:
            try:
                _gtk_menu_item_set_label(self.status_menu_item, status_text)
            except Exception as e:
                print(f"Update status error: {e}")
    
    def add_log(self, message: str):
        self.logs.append(message)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)
    
    def show_notification(self, title: str, message: str):
        show_notification(title, message)
    
    def on_start(self):
        self.service.start()
    
    def on_stop(self):
        self.service.stop()
    
    def on_pause_resume(self):
        if self.service.paused:
            self.service.resume()
        else:
            self.service.pause()
    
    def on_check_now(self):
        threading.Thread(target=self._manual_check, daemon=True).start()
    
    def _manual_check(self):
        self.add_log("[Manual Check]")
        network_ok = self.service.check_network()
        
        if network_ok:
            self.add_log("Status: Connected [OK]")
            self.show_notification("Campus Network", "[OK] Connected")
        else:
            self.add_log("Status: Disconnected [X]")
            self.show_notification("Campus Network", "[X] Disconnected")
            threading.Thread(target=self.service.do_login, daemon=True).start()
    
    def on_show_stats(self):
        stats = self.service.get_stats()
        
        lines = [
            "=" * 50,
            "STATISTICS",
            "-" * 50,
            f"Started: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S') if stats['start_time'] else '-'}",
            f"Checks: {stats['check_count']}",
            f"Connected: {stats['connected_count']} | Disconnected: {stats['disconnected_count']}",
            f"Logins: {stats['login_count']} (OK:{stats['success_count']} X:{stats['fail_count']})",
            f"Last login: {stats['last_login'].strftime('%H:%M:%S') if stats['last_login'] else '-'}",
            "=" * 50
        ]
        
        output = '\n'.join(lines)
        print('\n' + output)
        
        stats_file = '/tmp/campus_login_stats.txt'
        with open(stats_file, 'w', encoding='utf-8') as f:
            f.write(output + '\n')
        
        subprocess.run(['xdg-open', stats_file], check=False)
    
    def on_show_logs(self):
        output = '=' * 60 + '\n'
        output += 'RECENT LOGS\n'
        output += '-' * 60 + '\n'
        output += '\n'.join(self.logs[-50:])
        output += '\n' + '=' * 60 + '\n'
        
        print('\n' + output)
        
        log_file = '/tmp/campus_login_recent.log'
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(output)
        
        subprocess.run(['xdg-open', log_file], check=False)
    
    def on_quit(self):
        show_notification("Campus Login", "服务已停止")
        self.service.stop()
        if HAS_TRAY:
            _gtk_main_quit()
        sys.exit(0)

# ==================== 主入口 ====================

if __name__ == "__main__":
    log_file = '/home/furina/campus_login/logs/tray.log'
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n[{datetime.now()}] Campus Login v9.0 (ctypes) Started\n")
    
    tray = CampusLoginTray()
    
    if HAS_TRAY:
        _gtk_main()
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            tray.service.stop()