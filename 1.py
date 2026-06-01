import urllib.request
import os

os.makedirs("captchas", exist_ok=True)
for i in range(2999, 3001):
    urllib.request.urlretrieve("http://218.200.239.185:8888/portalserver/user/randomimage", f"captchas/{i}.png")