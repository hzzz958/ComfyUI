import os
import subprocess
import time
import threading
import sys

# --- 配置 ---
PORT = 8188

def kill_port_owner(port):
    """清理残留端口占用"""
    try:
        # 使用 fuser 强杀占用端口的进程
        subprocess.run(["fuser", "-k", f"{port}/tcp"], check=False)
        time.sleep(2)
    except Exception as e:
        print(f"[Launcher] 端口清理中... {e}")

def run_comfyui():
    """守护 ComfyUI 进程"""
    kill_port_owner(PORT)
    # 针对 3090 的优化参数：--highvram
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    
    while True:
        print(f"\n[ComfyUI] 启动中...")
        process = subprocess.Popen(cmd)
        process.wait()
        print(f"\n[ComfyUI] 进程退出，准备重启...")
        kill_port_owner(PORT)
        time.sleep(5)

def start_tunnel():
    """启动 Gradio 隧道 (无需 Token，安全且兼容 API)"""
    try:
        from gradio.networking import setup_tunnel
    except ImportError:
        print("[Launcher] 正在安装 gradio...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio"])
        from gradio.networking import setup_tunnel

    print("\n[Launcher] 正在申请公网隧道...")
    try:
        # 这个地址在 UI 和 API 调用上完全通用
        share_url = setup_tunnel("127.0.0.1", PORT)
        print("\n" + "★"*60)
        print(f"  公网访问地址 (API/UI): {share_url}")
        print("★"*60 + "\n")
    except Exception as e:
        print(f"[Launcher] 隧道启动失败: {e}")

    while True:
        time.sleep(100)

if __name__ == "__main__":
    # 1. 启动后端
    t = threading.Thread(target=run_comfyui, daemon=True)
    t.start()
    
    # 2. 预热
    time.sleep(5)
    
    # 3. 开启隧道
    try:
        start_tunnel()
    except KeyboardInterrupt:
        print("退出程序")
