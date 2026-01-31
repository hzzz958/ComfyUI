import os, subprocess, time, threading, sys

PORT = 8188

def run_comfyui():
    # 自动清理端口
    subprocess.run(["fuser", "-k", f"{PORT}/tcp"], check=False)
    # 3090 优化启动命令
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(PORT), "--highvram"]
    while True:
        process = subprocess.Popen(cmd)
        process.wait()
        time.sleep(5)

def start_tunnel():
    from gradio.networking import setup_tunnel
    while True:
        try:
            print("\n[Launcher] 正在申请隧道...")
            url = setup_tunnel("127.0.0.1", PORT)
            print(f"\n\n链接已生成: {url}\n\n")
            break
        except:
            time.sleep(5)
    while True: time.sleep(100)

if __name__ == "__main__":
    threading.Thread(target=run_comfyui, daemon=True).start()
    time.sleep(5)
    start_tunnel()
