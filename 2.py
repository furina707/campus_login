import os

folder = "captchas"
for f in os.listdir(folder):
    if f.endswith('.png'):
        num = int(f.replace('.png', ''))
        if num >= 3001:
            os.remove(os.path.join(folder, f))
            print(f"已删除: {f}")