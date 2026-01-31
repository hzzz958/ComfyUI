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
    彻底清理端口占用
    """
    print(f"[Launcher] 正在清理端口 {port}...")
    current_pid = os.getpid()
    
    # 方案 1: 用 lsof/fuser (如果有)
    try:
        result = subprocess.run(['lsof', '-i', f':{port}', '-t'], 
                              capture_output=True, text=True, timeout=3)
        if result.stdout.strip():
            for pid_str in result.stdout.strip().split('\n'):
                try:
                    pid = int(pid_str)
                    if pid != current_pid:
                        print(f"[Launcher] 杀死进程 {pid}")
                        os.kill(pid, signal.SIGKILL)
                except (ValueError, ProcessLookupError):
                    pass
            time.sleep(2)
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # 方案 2: 遍历 /proc (如果有)
    if os.path.exists('/proc'):
        try:
            for pid in os.listdir('/proc'):
                if not pid.isdigit():
                    continue
                try:
                    pid_int = int(pid)
                    if pid_int == current_pid:
                        continue
                    
                    # 读取 net/tcp 找占用端口的进程
                    with open(f'/proc/{pid}/net/tcp', 'r') as f:
                        for line in f:
                            parts = line.split()
                            if len(parts) > 3:
                                local_addr = parts[1]
                                # 格式: IP:PORT (16进制)
                                if ':' in local_addr:
                                    hex_port = local_addr.split(':')[1]
                                    if int(hex_port, 16) == port:
                                        print(f"[Launcher] 杀死进程 {pid_int}")
                                        os.kill(pid_int, signal.SIGKILL)
                except (FileNotFoundError, PermissionError, ValueError):
                    pass
        except Exception as e:
            print(f"[Launcher] /proc 扫描失败: {e}")
    
    # 方案 3: 暴力杀死所有 python main.py
    try:
        result = subprocess.run(['pgrep', '-f', 'python.*main.py'], 
                              capture_output=True, text=True, timeout=3)
        if result.stdout.strip():
            for pid_str in result.stdout.strip().split('\n'):
                try:
                    pid = int(pid_str)
                    if pid != current_pid:
                        print(f"[Launcher] 杀死 python main.py 进程 {pid}")
                        os.kill(pid, signal.SIGKILL)
                except (ValueError, ProcessLookupError):
                    pass
            time.sleep(2)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    time.sleep(2)

def is_port_in_use(port):
    """用 socket 检测端口是否开了"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', port))
        return result == 0

def run_comfyui():
    """启动并守护 ComfyUI"""
    # 彻底清理残留
    kill_process_on_port(PORT)
    
    # 启动命令
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    
    while True:
        print(f"\n[ComfyUI] 启动中...")
        try:
            process = subprocess.Popen(
                cmd, 
                cwd=os.getcwd(),
                stdout=sys.stdout,  # 直接输出到终端
                stderr=sys.stderr
            )
            process.wait()
        except Exception as e:
            print(f"[ComfyUI] 启动失败: {e}")
        
        print(f"\n[ComfyUI] 进程退出，30秒后重启...")
        kill_process_on_port(PORT)
        time.sleep(30)

def download_cloudflared():
    """下载 cloudflared"""
    cf_path = "./cloudflared"
    
    if os.path.exists(cf_path):
        print("[Tunnel] cloudflared 已存在")
        return cf_path
    
    print("[Tunnel] 正在下载 cloudflared...")
    
    # 多个备选 URL
    urls = [
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        "https://github.com/cloudflare/cloudflared/releases/download/2024.12.2/cloudflared-linux-amd64",
    ]
    
    for url in urls:
        try:
            import urllib.request
            urllib.request.urlretrieve(url, cf_path, timeout=30)
            os.chmod(cf_path, 0o755)
            print(f"[Tunnel] cloudflared 下载成功")
            return cf_path
        except Exception as e:
            print(f"[Tunnel] 下载失败 ({url}): {e}")
            if os.path.exists(cf_path):
                os.remove(cf_path)
            continue
    
    raise Exception("cloudflared 下载失败，请检查网络")

def start_cloudflare_tunnel():
    """启动 Cloudflare 隧道"""
    cf_path = download_cloudflared()
    
    # 等待 ComfyUI 启动
    print(f"[Tunnel] 等待 ComfyUI 启动 (端口 {PORT})...")
    max_wait = 120  # 最多等 2 分钟
    waited = 0
    while not is_port_in_use(PORT):
        if waited > max_wait:
            raise Exception(f"ComfyUI 未在 {max_wait} 秒内启动")
        time.sleep(2)
        waited += 2
        print(f"[Tunnel] 仍在等待... ({waited}s)")
    
    print(f"[Tunnel] ComfyUI 已就绪，启动隧道...")
    cmd = [cf_path, "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"]
    
    # 隧道进程
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # 同时监听 stdout 和 stderr
    url_found = False
    for line in iter(lambda: proc.stderr.readline() or proc.stdout.readline(), ''):
        if not line:
            continue
        print(f"[Tunnel] {line.rstrip()}")
        
        if not url_found:
            match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
            if match:
                url = match.group(0)
                print("\n" + "█"*70)
                print(f"✅  ComfyUI 公网地址:")
                print(f"    {url}")
                print("█"*70 + "\n")
                url_found = True

if __name__ == "__main__":
    try:
        # 启动 ComfyUI 后台线程
        comfyui_thread = threading.Thread(target=run_comfyui, daemon=False)
        comfyui_thread.start()
        
        # 启动隧道（主线程）
        start_cloudflare_tunnel()
        
        # 保持主进程运行
        while True:
            time.sleep(100)
    
    except KeyboardInterrupt:
        print("\n[Launcher] 收到中断信号，正在关闭...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[Launcher] 错误: {e}")
        sys.exit(1)
