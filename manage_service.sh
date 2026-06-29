#!/bin/bash
# 校园网自动登录服务管理脚本

SERVICE="campus-login.service"

case "$1" in
    start)
        echo "启动服务..."
        systemctl --user start $SERVICE
        echo "✓ 服务已启动"
        ;;
    stop)
        echo "停止服务..."
        systemctl --user stop $SERVICE
        echo "✓ 服务已停止"
        ;;
    restart)
        echo "重启服务..."
        systemctl --user restart $SERVICE
        echo "✓ 服务已重启"
        ;;
    status)
        systemctl --user status $SERVICE
        ;;
    enable)
        echo "启用开机自启..."
        systemctl --user enable $SERVICE
        echo "✓ 开机自启已启用"
        ;;
    disable)
        echo "禁用开机自启..."
        systemctl --user disable $SERVICE
        echo "✓ 开机自启已禁用"
        ;;
    logs)
        echo "查看日志..."
        journalctl --user -u $SERVICE -f
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|enable|disable|logs}"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看状态"
        echo "  enable  - 启用开机自启"
        echo "  disable - 禁用开机自启"
        echo "  logs    - 查看实时日志"
        ;;
esac