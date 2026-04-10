"""
PURPOSE: dsp-connect Web 调试界面 — Flask + Socket 转发
PATTERN: Web 前端 → Flask 后端 → TCP socket → DscShellServe
FOR: 弱 AI 参考如何给嵌入式调试工具加 Web UI
"""

import socket
import threading
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 全局连接状态
conn = {
    "host": "127.0.0.1",
    "port": 9000,
    "sock": None,
    "lock": threading.Lock(),
}


def sock_connect(host, port):
    """连接到 DscShellServe 的 TCP 端口"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect((host, port))
    # 读掉初始 prompt "dsc> "
    try:
        s.recv(1024)
    except socket.timeout:
        pass
    return s


def sock_send_cmd(s, cmd):
    """发送命令并读取响应（直到收到 'dsc> ' prompt）"""
    s.sendall((cmd + "\n").encode())
    buf = b""
    while True:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
        # 响应结束标志：以 "dsc> " 结尾
        if buf.endswith(b"dsc> "):
            buf = buf[: -len(b"dsc> ")]
            break
    return buf.decode(errors="replace").strip()


@app.route("/")
def index():
    return render_template("index.html",
                           host=conn["host"],
                           port=conn["port"],
                           connected=conn["sock"] is not None)


@app.route("/connect", methods=["POST"])
def do_connect():
    host = request.form.get("host", "127.0.0.1")
    port = int(request.form.get("port", 9000))
    with conn["lock"]:
        # 关闭旧连接
        if conn["sock"]:
            try:
                conn["sock"].close()
            except OSError:
                pass
        try:
            conn["sock"] = sock_connect(host, port)
            conn["host"] = host
            conn["port"] = port
            return jsonify(ok=True, msg=f"Connected to {host}:{port}")
        except Exception as e:
            conn["sock"] = None
            return jsonify(ok=False, msg=str(e))


@app.route("/disconnect", methods=["POST"])
def do_disconnect():
    with conn["lock"]:
        if conn["sock"]:
            try:
                conn["sock"].close()
            except OSError:
                pass
            conn["sock"] = None
    return jsonify(ok=True, msg="Disconnected")


@app.route("/cmd", methods=["POST"])
def do_cmd():
    cmd = request.form.get("cmd", "").strip()
    if not cmd:
        return jsonify(ok=False, msg="Empty command")
    with conn["lock"]:
        if not conn["sock"]:
            return jsonify(ok=False, msg="Not connected")
        try:
            resp = sock_send_cmd(conn["sock"], cmd)
            return jsonify(ok=True, resp=resp)
        except Exception as e:
            conn["sock"] = None
            return jsonify(ok=False, msg=f"Connection lost: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
