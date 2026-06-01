import numpy as np
from PIL import Image
import os

def build_probability_templates(folder, label_file, img_size=(20, 25)):
    """从标注数据中统计每个位置每个数字的概率分布"""
    # 读取标注
    labels = {}
    with open(label_file, 'r') as f:
        for line in f:
            name, label = line.strip().split(',')
            labels[name] = label
    
    # 初始化: [数字0-9][y][x] 计数
    counts = {str(d): np.zeros(img_size, dtype=np.int32) for d in range(10)}
    totals = {str(d): 0 for d in range(10)}
    
    for filename, code in labels.items():
        if len(code) != 4:
            continue
        filepath = os.path.join(folder, filename)
        img = Image.open(filepath).convert('L')
        
        # 预处理并缩放到 20x25
        pixels = list(img.getdata())
        threshold = sum(pixels) / len(pixels) * 0.8
        bw = img.point(lambda x: 0 if x < threshold else 255, '1')
        bw = bw.resize(img_size, Image.Resampling.LANCZOS)
        
        # 转为矩阵
        matrix = []
        for y in range(img_size[1]):
            for x in range(img_size[0]):
                p = bw.getpixel((x, y))
                matrix.append(0 if p == 0 else 1)
        matrix = np.array(matrix).reshape(img_size[1], img_size[0])
        
        # 对每一位分别统计
        for pos, digit in enumerate(code):
            # 提取该位置的子图（假设4位均匀分布）
            w = img_size[0] // 4
            left = pos * w
            right = (pos + 1) * w
            digit_img = matrix[:, left:right]
            # 累加计数
            counts[digit] += digit_img
            totals[digit] += 1
    
    # 转为概率 (拉普拉斯平滑)
    probs = {}
    for d in range(10):
        d_str = str(d)
        probs[d_str] = (counts[d_str] + 1) / (totals[d_str] + 2)
    
    return probs

def recognize_with_prob(prob_templates, img):
    """使用概率模板识别"""
    # 预处理图片
    pixels = list(img.getdata())
    threshold = sum(pixels) / len(pixels) * 0.8
    bw = img.point(lambda x: 0 if x < threshold else 255, '1')
    bw = bw.resize((20, 25), Image.Resampling.LANCZOS)
    
    matrix = []
    for y in range(25):
        for x in range(20):
            p = bw.getpixel((x, y))
            matrix.append(0 if p == 0 else 1)
    matrix = np.array(matrix).reshape(25, 20)
    
    result = ""
    for pos in range(4):
        w = 20 // 4
        left = pos * w
        right = (pos + 1) * w
        digit_img = matrix[:, left:right]
        
        best_digit = None
        best_score = -1
        for d in range(10):
            d_str = str(d)
            prob = prob_templates[d_str][:, left:right]
            # 计算对数似然
            score = np.sum(np.log(prob) * digit_img + np.log(1 - prob) * (1 - digit_img))
            if score > best_score:
                best_score = score
                best_digit = d_str
        result += best_digit
    return result