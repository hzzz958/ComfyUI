import os
import subprocess
import time
import threading
import sys
import socket
import re
import signal

# --- 配置 ---
PORT = 8188

def kill_process_on_port(port):
    """
    纯 Python 暴力清理方案：不依赖 fuser/lsof。
    直接遍历 /proc 文件夹，寻找并杀死所有占用 8188 端口的 python 进程。
    """
    print(f"[Launcher] 正在深度清理端口 {port}...")
    current_pid = os.getpid()
    try:
        # 遍历 /proc 下的所有进程 ID
        for pid in [p for p in os.listdir('/proc') if p.isdigit()]:
            try:
                pid_int = int(pid)
                if pid_int == current_pid:
                    continue
                
                # 读取进程的命令行
                with open(os.path.join('/proc', pid, 'cmdline'), 'r') as f:
                    cmdline = f.read().replace('\0', ' ')
                    # 只要包含 python 且包含 main.py 或 port 8188，就干掉
                    if 'python' in cmdline and ('main.py' in cmdline or str(port) in cmdline):
                        print(f"[Launcher] 强行终止残留进程: {pid_int}")
                        os.kill(pid_int, signal.SIGKILL)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
        time.sleep(2) # 留给内核释放端口的时间
    except Exception as e:
        print(f"[Launcher] 清理端口过程跳过: {e}")

def is_port_in_use(port):
    """用 socket 检测端口是否真的开了"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_comfyui():
    """守护主服务进程"""
    # 彻底清理残留，解决 Address already in use
    kill_process_on_port(PORT)
    
    # 启动命令 (针对 3090 优化)
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    
    while True:
        print(f"\n[ComfyUI] 启动中...")
        # 显式指定 cwd，确保路径正确
        process = subprocess.Popen(cmd, cwd=os.getcwd())
        process.wait()
        
        print(f"\n[ComfyUI] 进程退出，准备重启...")
        kill_process_on_port(PORT)
        time.sleep(5)

def start_cloudflare_tunnel():
    """启动 Cloudflare 快速隧道"""
    cf_path = "./cloudflared"
    
    # 1. 纯 Python 下载，不依赖 wget/curl
    if not os.path.exists(cf_path):
        print("[Tunnel] 正在静默下载 Cloudflare 穿透工具...")
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        import urllib.request
        try:
            urllib.request.urlretrieve(url, cf_path)
            os.chmod(cf_path, 0o755)
        except Exception as e:
            print(f"[Tunnel] 工具下载失败: {e}")
            return

    # 2. 轮询等待后端启动
    print(f"[Tunnel] 等待本地端口 {PORT} 激活...")
    while not is_port_in_use(PORT):
        time.sleep(2)

    # 3. 开启隧道并抓取 URL
    print("[Tunnel] 正在建立 Cloudflare 网络连接...")
    cmd = [cf_path, "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"]
    
    # 隧道输出都在 stderr
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
    
    for line in proc.stderr:
        # 提取 trycloudflare 域名
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            print("\n" + "█"*60)
            print(f"  ComfyUI 公网 API 地址已就绪 (原生转发):")
            print(f"  {url}")
            print("█"*60 + "\n")
            break

if __name__ == "__main__":
    # 1. 异步启动后端
    threading.Thread(target=run_comfyui, daemon=True).start()
    
    # 2. 启动隧道并保持主进程
    try:
        start_cloudflare_tunnel()
        while True:
            time.sleep(100)
    except KeyboardInterrupt:
        print("\n[Launcher] 正在安全退出...")
