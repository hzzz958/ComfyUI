import os, subprocess, time, threading, sys, socket, re

PORT = 8188

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_comfyui():
    """守护 ComfyUI 进程"""
    print(f"[ComfyUI] 清理端口 {PORT}...")
    subprocess.run(["fuser", "-k", f"{PORT}/tcp"], check=False)
    
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    while True:
        print(f"\n[ComfyUI] 启动核心服务...")
        process = subprocess.Popen(cmd)
        process.wait()
        print(f"\n[ComfyUI] 进程退出，5秒后重启...")
        time.sleep(5)

def start_cloudflare_tunnel():
    """启动 Cloudflare Quick Tunnel"""
    # 1. 下载 cloudflared 二进制文件
    if not os.path.exists("./cloudflared"):
        print("[Tunnel] 正在下载 cloudflared...")
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        subprocess.run(["wget", "-q", "-O", "cloudflared", url], check=True)
        subprocess.run(["chmod", "+x", "cloudflared"], check=True)

    # 2. 等待后端就绪
    while not is_port_in_use(PORT):
        print(f"[Tunnel] 等待端口 {PORT} 激活...")
        time.sleep(2)

    # 3. 开启隧道并实时抓取 URL
    print("[Tunnel] 正在建立 Cloudflare 隧道...")
    cmd = ["./cloudflared", "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"]
    
    # 使用 Popen 以便实时读取日志输出中的 URL
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    
    for line in proc.stderr:
        # Cloudflare 快速隧道的地址格式通常是 https://xxx.trycloudflare.com
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            print("\n" + "█"*60)
            print(f"  Cloudflare 隧道已就绪！")
            print(f"  公网访问地址: {url}")
            print(f"  API 请求示例: {url}/object_info")
            print("█"*60 + "\n")
            break

if __name__ == "__main__":
    # 启动后端线程
    threading.Thread(target=run_comfyui, daemon=True).start()
    # 启动隧道
    try:
        start_cloudflare_tunnel()
    except KeyboardInterrupt:
        print("关闭中...")
