#!/usr/bin/env python3
"""
校园网自动登录脚本 - 使用模板识别
"""
import sys
import os
import urllib.request
import urllib.parse
import http.cookiejar
import time
import re
from PIL import Image
import io

# 配置信息
LOGIN_URL = "http://218.200.239.185:8888/portalserver/user/unionautologin.do"
USERNAME = "SCXY15982477461"
PASSWORD = "065968"
DEBUG_MODE = True

# 导入模板
try:
    from digit_templates import TEMPLATES
    if DEBUG_MODE:
        print("✓ 模板加载成功")
except ImportError:
    print("✗ 模板文件不存在！")
    sys.exit(1)

def preprocess_image(img):
    """图像预处理"""
    img = img.convert('L')
    # 自适应阈值
    pixels = list(img.getdata())
    avg_brightness = sum(pixels) / len(pixels)
    threshold = avg_brightness * 0.8
    img = img.point(lambda x: 0 if x < threshold else 255, '1')
    return img

def match_digit(digit_matrix, position=0):
    """匹配单个数字"""
    best_match = '?'
    best_score = -1
    
    # 计算黑色像素数（快速识别1）
    black_count = sum(sum(1 for x in range(20) if digit_matrix[y][x] == 0) for y in range(25))
    if black_count < 30:
        return '1'
    
    for digit, template in TEMPLATES.items():
        # 第一位不能是0
        if position == 0 and digit == '0':
            continue
        
        same = 0
        for y in range(25):
            for x in range(20):
                if digit_matrix[y][x] == template[y][x]:
                    same += 1
        score = same / 500  # 25*20=500
        
        if score > best_score:
            best_score = score
            best_match = digit
    
    return best_match if best_score > 0.65 else '?'

def recognize_captcha(img_content):
    """识别验证码"""
    img = Image.open(io.BytesIO(img_content))
    img = preprocess_image(img)
    
    w, h = img.width, img.height
    digit_width = w // 4
    
    result = ''
    for i in range(4):
        left = i * digit_width
        right = (i + 1) * digit_width
        digit_img = img.crop((left, 0, right, h))
        digit_img = digit_img.resize((20, 25))
        
        # 转换为矩阵
        matrix = []
        pixels = digit_img.getdata()
        for y in range(25):
            row = []
            for x in range(20):
                row.append(0 if pixels[y*20 + x] == 0 else 1)
            matrix.append(row)
        
        digit = match_digit(matrix, position=i)
        result += digit
    
    return result

class HTTPSession:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj)
        )
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def get(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
        try:
            with self.opener.open(req, timeout=10) as resp:
                return resp.read().decode('utf-8', errors='ignore'), resp
        except Exception as e:
            return str(e), None
    
    def get_binary(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
        try:
            with self.opener.open(req, timeout=10) as resp:
                return resp.read(), resp
        except Exception as e:
            return None, None
    
    def post(self, url, data):
        post_data = urllib.parse.urlencode(data).encode('utf-8')
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': self.user_agent
        }
        req = urllib.request.Request(url, data=post_data, headers=headers)
        try:
            with self.opener.open(req, timeout=10) as resp:
                return resp.read().decode('utf-8', errors='ignore'), resp
        except Exception as e:
            return str(e), None
    
    def get_cookie(self, name):
        for c in self.cj:
            if c.name == name:
                return c.value
        return ''

def login():
    """执行登录"""
    session = HTTPSession()
    
    # 1. 访问初始页面获取JSESSIONID
    if DEBUG_MODE:
        print("\n[1/4] 初始化会话...")
    
    params_url = (
        f"{LOGIN_URL}?brasip=183.221.77.105&area=union"
        f"&wlanuserip=null&redirectUrl=example/sccmcceducookie/cnunion"
        f"&domain=@cmccgxsd"
    )
    session.get(params_url)
    time.sleep(0.5)
    
    # 2. 获取验证码
    if DEBUG_MODE:
        print("[2/4] 获取验证码...")
    
    base_url = "http://218.200.239.185:8888/portalserver"
    captcha_url = f"{base_url}/user/randomimage"
    
    captcha_img, resp = session.get_binary(captcha_url)
    if not captcha_img:
        print("✗ 获取验证码失败")
        return False
    
    # 3. 识别验证码
    if DEBUG_MODE:
        print("[3/4] 识别验证码...")
    
    captcha_code = recognize_captcha(captcha_img)
    print(f"识别结果: {captcha_code}")
    
    if len(captcha_code) != 4 or '?' in captcha_code:
        print(f"✗ 验证码识别失败: {captcha_code}")
        return False
    
    # 4. 提交登录
    if DEBUG_MODE:
        print("[4/4] 提交登录...")
    
    login_data = {
        "name": USERNAME,
        "pass": PASSWORD,
        "psNum": captcha_code
    }
    
    jsessionid = session.get_cookie('JSESSIONID')
    submit_url = (
        f"{LOGIN_URL};jsessionid={jsessionid}"
        f"?brasip=183.221.77.105&area=union"
        f"&wlanuserip=null&redirectUrl=example/sccmcceducookie/cnunion"
        f"&domain=@cmccgxsd"
    )
    
    response_text, resp = session.post(submit_url, login_data)
    
    if DEBUG_MODE:
        print(f"\n服务器响应: {response_text[:500]}")
    
    # 判断登录结果
    if "登录成功" in response_text or "欢迎" in response_text:
        print("\n✓✓✓ 登录成功！ ✓✓✓")
        return True
    elif "验证码错误" in response_text:
        print("\n✗ 验证码错误")
        return False
    elif "用户名或密码错误" in response_text:
        print("\n✗ 用户名或密码错误")
        return False
    else:
        print("\n✗ 登录失败")
        return False

def main():
    print("=" * 50)
    print("校园网自动登录脚本")
    print("=" * 50)
    
    for attempt in range(1, 4):
        print(f"\n第 {attempt} 次尝试")
        print("-" * 30)
        
        success = login()
        if success:
            break
        
        if attempt < 3:
            print("\n等待 2 秒后重试...")
            time.sleep(2)
    
    if not success:
        print("\n✗ 登录失败，请检查网络或手动登录")
    time.sleep(2)

if __name__ == '__main__':
    main()