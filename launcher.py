import os
import subprocess
import time
import threading
import socket

# --- 配置 ---
PORT = 8188

def kill_port_owner(port):
    """暴力清理端口占用"""
    print(f"[Launcher] 检查端口 {port} 是否被占用...")
    try:
        # 查找占用端口的 PID
        pid = subprocess.check_output(["fuser", f"{port}/tcp"]).decode().strip()
        if pid:
            print(f"[Launcher] 清理残留进程: {pid}")
            subprocess.run(["kill", "-9", pid])
            time.sleep(2)
    except:
        pass

def run_comfyui():
    """守护 ComfyUI 进程"""
    # 启动前清理一次
    kill_port_owner(PORT)
    
    cmd = ["python3", "main.py", "--listen", "127.0.0.1", "--port", str(PORT)]
    while True:
        print(f"\n[ComfyUI] 正在启动核心服务...")
        process = subprocess.Popen(cmd)
        process.wait()
        print(f"\n[ComfyUI] 进程已退出，准备重启...")
        kill_port_owner(PORT) # 重启前再次清理
        time.sleep(3)

def start_tunnel():
    """启动 Gradio 隧道 (无需 Authtoken)"""
    try:
        from gradio.networking import setup_tunnel
    except ImportError:
        print("[Launcher] 正在安装 gradio...")
        subprocess.check_call(["pip", "install", "gradio"])
        from gradio.networking import setup_tunnel

    print("\n[Launcher] 正在申请 Gradio 公网隧道 (API 模式)...")
    # 这行代码会直接返回一个 https://xxx.gradio.live 的字符串
    share_url = setup_tunnel("127.0.0.1", PORT)
    
    print("\n" + "★"*40)
    print(f"  您的公网 API/UI 地址:")
    print(f"  {share_url}")
    print("★"*40 + "\n")

    # 保持主线程
    while True:
        time.sleep(100)

if __name__ == "__main__":
    # 1. 启动 ComfyUI 守护线程
    t = threading.Thread(target=run_comfyui, daemon=True)
    t.start()
    
    # 2. 等待 ComfyUI 启动完成
    time.sleep(5)
    
    # 3. 启动隧道
    try:
        start_tunnel()
    except KeyboardInterrupt:
        print("停止服务")
