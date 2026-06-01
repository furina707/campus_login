import os
import sys
import io
from PIL import Image

# 导入您的模板和识别函数
# 从 campus_login_lite.py 中导入需要的函数
sys.path.insert(0, os.path.dirname(__file__))
from campus_login_lite import recognize_captcha, preprocess_image, match_digit
from digit_templates import TEMPLATES

def auto_label_all():
    folder = "captchas"
    output_file = "labels_auto.txt"
    
    files = sorted([f for f in os.listdir(folder) if f.endswith('.png')], key=lambda x: int(x.split('.')[0]))
    total = len(files)
    
    print(f"共 {total} 张图片，开始自动识别...")
    
    with open(output_file, 'w') as f:
        for i, filename in enumerate(files):
            filepath = os.path.join(folder, filename)
            with open(filepath, 'rb') as img_f:
                img_data = img_f.read()
            
            try:
                # 调用原有的识别函数
                result = recognize_captcha(img_data)
                f.write(f"{filename},{result}\n")
            except Exception as e:
                print(f"识别失败 {filename}: {e}")
                f.write(f"{filename},????\n")
            
            if (i + 1) % 100 == 0:
                print(f"进度: {i+1}/{total}")
    
    print(f"\n自动标注完成！结果保存到 {output_file}")
    print("接下来需要手动检查并修正错误的标注")

def check_and_correct():
    """逐个显示图片，确认或修正自动标注的结果"""
    folder = "captchas"
    label_file = "labels_auto.txt"
    output_file = "labels_corrected.txt"
    
    # 读取自动标注结果
    auto_labels = {}
    with open(label_file, 'r') as f:
        for line in f:
            filename, label = line.strip().split(',')
            auto_labels[filename] = label
    
    files = sorted(auto_labels.keys(), key=lambda x: int(x.split('.')[0]))
    
    corrected = {}
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in f:
                filename, label = line.strip().split(',')
                corrected[filename] = label
    
    for i, filename in enumerate(files):
        if filename in corrected:
            continue
        
        filepath = os.path.join(folder, filename)
        auto_label = auto_labels[filename]
        
        # 显示图片
        img = Image.open(filepath)
        img.show()
        
        print(f"\n[{i+1}/{len(files)}] {filename}")
        print(f"自动识别: {auto_label}")
        
        user_input = input("输入正确标签 (回车=使用自动识别, s=跳过, q=退出): ").strip()
        
        if user_input.lower() == 'q':
            break
        if user_input.lower() == 's':
            continue
        if user_input == '':
            user_input = auto_label
        
        if len(user_input) == 4 and user_input.isdigit():
            corrected[filename] = user_input
            with open(output_file, 'a') as f:
                f.write(f"{filename},{user_input}\n")
            print(f"已保存: {filename} -> {user_input}")
        else:
            print("输入无效（需要4位数字），跳过")
        
        img.close()
    
    print(f"\n完成！已修正 {len(corrected)} 张，保存到 {output_file}")

if __name__ == '__main__':
    print("1. 自动标注所有图片")
    print("2. 手动修正标注")
    choice = input("请选择 (1/2): ").strip()
    
    if choice == '1':
        auto_label_all()
    elif choice == '2':
        check_and_correct()
    else:
        print("无效选择")