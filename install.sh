#!/bin/bash
set -e

REPO="furina707/campus_login"
BASE_URL="https://raw.githubusercontent.com/$REPO/main"
INSTALL_DIR="$HOME/campus_login"

echo "============================================"
echo "  校园网自动登录 - 一键安装脚本"
echo "============================================"
echo ""

if [ -d "$INSTALL_DIR" ]; then
    echo "[!] 目录 $INSTALL_DIR 已存在"
    read -rp "    是否覆盖? [y/N] " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "安装已取消"
        exit 0
    fi
fi

mkdir -p "$INSTALL_DIR"

echo "[1/4] 下载程序文件..."
curl -fsSL "$BASE_URL/campus_login_tray.py" -o "$INSTALL_DIR/campus_login_tray.py"
curl -fsSL "$BASE_URL/manage_service.sh" -o "$INSTALL_DIR/manage_service.sh"
chmod +x "$INSTALL_DIR/manage_service.sh"

echo "[2/4] 创建目录结构..."
mkdir -p "$INSTALL_DIR/models"
mkdir -p "$INSTALL_DIR/icons"
mkdir -p "$INSTALL_DIR/logs"

if [ ! -f "$INSTALL_DIR/models/common_old.onnx" ]; then
    echo "[!] 警告: 未检测到模型文件"
    echo "    请将以下文件放入 $INSTALL_DIR/models/:"
    echo "      - common_old.onnx (验证码识别模型)"
    echo "      - charset.txt    (字符集文件)"
    echo ""
fi

if [ -z "$(ls -A "$INSTALL_DIR/icons/" 2>/dev/null)" ]; then
    echo "[*] 下载默认图标..."
    for icon in icon_normal.png icon_connected.png icon_error.png icon_paused.png; do
        curl -fsSL "$BASE_URL/icons/$icon" -o "$INSTALL_DIR/icons/$icon" 2>/dev/null || true
    done
fi

echo "[3/4] 安装系统依赖..."
if command -v pacman &>/dev/null; then
    echo "    [*] 检测到 Arch Linux，使用 pacman 安装..."
    sudo pacman -S --needed --noconfirm \
        gtk3 libappindicator-gtk3 onnx-runtime 2>/dev/null || {
        echo "    [!] 部分包安装失败，请手动安装:"
        echo "        sudo pacman -S gtk3 libappindicator-gtk3 onnx-runtime"
    }
    ldconfig -p | grep -q 'libonnxruntime' && \
        echo "    [OK] ONNX Runtime 已就绪" || \
        echo "    [!] 未找到 libonnxruntime，请确认 onnx-runtime 已正确安装"
else
    echo "    [!] 非 Arch 系统，请手动安装以下系统库:"
    echo "        GTK3, libappindicator3, ONNX Runtime"
fi

echo "[4/4] 配置 systemd 服务..."
mkdir -p "$HOME/.config/systemd/user"

cat > "$HOME/.config/systemd/user/campus-login.service" << EOF
[Unit]
Description=Campus Network Auto-Login
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/campus_login_tray.py
WorkingDirectory=$INSTALL_DIR
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload

echo ""
echo "============================================"
echo "  安装完成!"
echo "============================================"
echo ""
echo "使用方法:"
echo "  启动服务:    $INSTALL_DIR/manage_service.sh start"
echo "  开机自启:    $INSTALL_DIR/manage_service.sh enable"
echo "  查看状态:    $INSTALL_DIR/manage_service.sh status"
echo "  查看日志:    $INSTALL_DIR/manage_service.sh logs"
echo "  直接运行:    python3 $INSTALL_DIR/campus_login_tray.py"
echo ""
echo "注意: 请确保 $INSTALL_DIR/models/ 中有模型文件"