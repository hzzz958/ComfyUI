import os, subprocess, time, threading, sys, socket

PORT = 8188

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_comfyui():
    print(f"[ComfyUI] 检查端口 {PORT}...")
    # 如果端口被占用，虽然不能精准杀掉，但我们可以提醒或尝试启动
    # 实际上容器刚启动时，端口通常是干净的
    
    # 3090 优化参数
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    
    while True:
        print(f"\n[ComfyUI] 正在尝试启动核心服务...")
        # 使用 shell=False 防止路径解析问题
        process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        process.wait()
        print(f"\n[ComfyUI] 进程退出，5秒后重启...")
        time.sleep(5)

def start_tunnel():
    print("[Launcher] 正在初始化隧道...")
    try:
        from gradio.networking import setup_tunnel
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio"])
        from gradio.networking import setup_tunnel

    # 等待后端端口就绪再申请隧道，否则 Gradio 可能会报错
    print(f"[Launcher] 等待端口 {PORT} 激活...")
    while not is_port_in_use(PORT):
        time.sleep(2)
    
    print("[Launcher] 端口已就绪，正在申请 Gradio 隧道...")
    while True:
        try:
            # Gradio setup_tunnel 会返回生成的 URL
            share_url = setup_tunnel("127.0.0.1", PORT)
            print("\n" + "="*60)
            print(f"  ComfyUI 公网地址: {share_url}")
            print("="*60 + "\n")
            break
        except Exception as e:
            print(f"[Launcher] 隧道申请重试中... 错误: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # 1. 后台启动 ComfyUI
    t = threading.Thread(target=run_comfyui, daemon=True)
    t.start()
    
    # 2. 主线程管理隧道
    start_tunnel()
    
    # 维持运行
    while True:
        time.sleep(100)
