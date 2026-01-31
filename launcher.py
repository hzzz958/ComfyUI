import os, subprocess, time, threading, sys, socket, re, signal

PORT = 8188

def kill_process_on_port(port):
    """纯 Python 实现：查找并杀掉占用端口的进程"""
    print(f"[Launcher] 正在检查端口 {port}...")
    try:
        # 使用 Python 原生命令寻找 PID (Linux 通用)
        result = subprocess.check_output(["lsof", "-t", f"-i:{port}"], stderr=subprocess.STDOUT)
        pids = result.decode().strip().split('\n')
        for pid in pids:
            if pid:
                print(f"[Launcher] 发现残留进程 {pid}，正在清理...")
                os.kill(int(pid), signal.SIGKILL)
        time.sleep(2)
    except Exception:
        # 如果没有 lsof 或没有进程，直接跳过
        pass

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_comfyui():
    """守护 ComfyUI 进程"""
    # 强制清理端口
    kill_process_on_port(PORT)
    
    # 启动命令
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    
    while True:
        print(f"\n[ComfyUI] 正在启动核心服务...")
        # 显式指定工作目录
        process = subprocess.Popen(cmd, cwd=os.getcwd())
        process.wait()
        print(f"\n[ComfyUI] 进程退出，准备重启...")
        time.sleep(5)

def start_cloudflare_tunnel():
    """启动 Cloudflare 隧道"""
    # 1. 下载 cloudflared
    if not os.path.exists("./cloudflared"):
        print("[Tunnel] 正在下载 cloudflared...")
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        # 使用 python 下载，不依赖 wget
        import urllib.request
        urllib.request.urlretrieve(url, "./cloudflared")
        os.chmod("./cloudflared", 0o755)

    # 2. 等待后端就绪
    print("[Tunnel] 等待端口就绪...")
    while not is_port_in_use(PORT):
        time.sleep(2)

    # 3. 开启隧道
    print("[Tunnel] 正在连接 Cloudflare 网络...")
    cmd = ["./cloudflared", "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"]
    
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    
    # 实时抓取日志中的 URL
    for line in proc.stderr:
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            print("\n" + "█"*60)
            print(f"  ComfyUI 公网 API 地址 (无 iframe):")
            print(f"  {url}")
            print("█"*60 + "\n")
            break

if __name__ == "__main__":
    # 启动后端
    threading.Thread(target=run_comfyui, daemon=True).start()
    # 启动隧道
    try:
        start_cloudflare_tunnel()
    except KeyboardInterrupt:
        print("关闭...")
