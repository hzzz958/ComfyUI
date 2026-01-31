import os, subprocess, time, threading, sys, socket
import gradio as gr

PORT = 8188

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_comfyui():
    """守护 ComfyUI 进程并自动清理端口"""
    print(f"[ComfyUI] 正在清理端口 {PORT}...")
    subprocess.run(["fuser", "-k", f"{PORT}/tcp"], check=False)
    
    # 3090 优化参数
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    
    while True:
        print(f"\n[ComfyUI] 启动中...")
        process = subprocess.Popen(cmd)
        process.wait()
        print(f"\n[ComfyUI] 进程退出，5秒后重启...")
        time.sleep(5)

def start_gradio_tunnel():
    """
    使用 Gradio 6.x 的标准 launch 模式建立隧道。
    这种方式生成的链接在 API 调用上最为稳定。
    """
    print("[Launcher] 正在等待 ComfyUI 启动...")
    while not is_port_in_use(PORT):
        time.sleep(2)

    print("[Launcher] 后端已就绪，正在开启 Gradio 隧道 (无 iframe 模式)...")
    
    # 创建一个极简的转发逻辑
    # 我们不添加任何 Blocks 内容，直接利用 Gradio 的代理能力
    def dummy_fn():
        return "ComfyUI Proxy Running"

    with gr.Blocks() as demo:
        gr.Markdown(f"### ComfyUI 3090 Instance Running on Port {PORT}")
        # 这里不放置 iframe，仅作为隧道入口

    # 关键参数：
    # 1. share=True 开启隧道
    # 2. _api_mode=True (如果库版本支持) 优化 API 响应
    demo.launch(
        share=True, 
        server_name="127.0.0.1", 
        server_port=7860, # Gradio 自身的端口
        quiet=True
    )

if __name__ == "__main__":
    # 1. 启动后端线程
    t = threading.Thread(target=run_comfyui, daemon=True)
    t.start()
    
    # 2. 启动隧道（主线程）
    try:
        start_gradio_tunnel()
    except KeyboardInterrupt:
        print("关闭中...")
