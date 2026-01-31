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
    纯 Python 实现：查找并杀掉占用指定端口的残留进程。
    这种方法不依赖 fuser, lsof 等外部工具，最稳健。
    """
    print(f"[Launcher] 正在深度清理端口 {port}...")
    current_pid = os.getpid()
    try:
        # 遍历 Linux /proc 文件系统查找进程
        pids = [pid for pid in os.listdir('/proc') if pid.isdigit()]
        for pid in pids:
            try:
                pid_int = int(pid)
                if pid_int == current_pid:
                    continue
                
                # 读取进程的命令行参数
                with open(os.path.join('/proc', pid, 'cmdline'), 'r') as f:
                    cmdline = f.read()
                    # 如果进程涉及 python 和 main.py (ComfyUI 入口)，则清理
                    if 'python' in cmdline and ('main.py' in cmdline or 'comfy' in cmdline.lower()):
                        print(f"[Launcher] 发现残留 ComfyUI 进程 {pid_int}，强制杀掉...")
                        os.kill(pid_int, signal.SIGKILL)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
        time.sleep(2) # 等待系统回收端口
    except Exception as e:
        print(f"[Launcher] 清理端口时跳过错误: {e}")

def is_port_in_use(port):
    """检测本地端口是否已激活"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_comfyui():
    """守护 ComfyUI 核心服务进程"""
    # 启动前先确保端口是干净的
    kill_process_on_port(PORT)
    
    # 构建启动命令 (针对 3090 优化)
    cmd = [
        sys.executable, "main.py", 
        "--listen", "127.0.0.1", 
        "--port", str(PORT), 
        "--highvram"
    ]
    
    while True:
        print(f"\n[ComfyUI] 正在启动核心服务...")
        # stdout=None 确保日志直接打印到终端，方便调试
        process = subprocess.Popen(cmd, cwd=os.getcwd())
        process.wait()
        
        print(f"\n[ComfyUI] 进程意外退出，正在清理并准备重启...")
        kill_process_on_port(PORT)
        time.sleep(5)

def start_cloudflare_tunnel():
    """启动 Cloudflare Quick Tunnel 并提取公网 URL"""
    # 1. 下载二进制文件 (如果不存在)
    cf_path = "./cloudflared"
    if not os.path.exists(cf_path):
        print("[Tunnel] 正在静默下载 Cloudflare 穿透工具...")
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        import urllib.request
        try:
            urllib.request.urlretrieve(url, cf_path)
            os.chmod(cf_path, 0o755)
        except Exception as e:
            print(f"[Tunnel] 下载失败: {e}")
            return

    # 2. 等待后端 ComfyUI 端口就绪
    print(f"[Tunnel] 等待本地端口 {PORT} 激活...")
    while not is_port_in_use(PORT):
        time.sleep(2)

    # 3. 开启隧道
    print("[Tunnel] 正在连接 Cloudflare 全球网络...")
    cmd = [cf_path, "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"]
    
    # 捕获 stderr，因为 cloudflared 的 URL 打印在错误流中
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    
    for line in proc.stderr:
        # 寻找匹配 https://xxx.trycloudflare.com 的字符串
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            print("\n" + "█"*65)
            print(f"  ComfyUI 公网 API 地址 (无 iframe / 透明转发):")
            print(f"  {url}")
            print(f"  测试 API: {url}/object_info")
            print("█"*65 + "\n")
            break

if __name__ == "__main__":
    # 1. 启动 ComfyUI 守护线程
    t = threading.Thread(target=run_comfyui, daemon=True)
    t.start()
    
    # 2. 启动 Cloudflare 隧道逻辑 (主线程维持)
    try:
        start_cloudflare_tunnel()
        # 保持主线程不退出
        while True:
            time.sleep(100)
    except KeyboardInterrupt:
        print("\n[Launcher] 收到退出信号，正在关闭服务...")
