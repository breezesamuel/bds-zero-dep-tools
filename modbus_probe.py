# -*- coding: utf-8 -*-
"""丙大山工控探针（第 62 轮）——Modbus TCP 协议层真跑证明。

零依赖（纯 socket）自实现：
  · 从站（服务端）：监听 502 端口语义，支持 FC03 读保持寄存器/FC06 写单寄存器
  · 主站（客户端）：构造 MBAP+PDU，读回验证
自环 = 从站与主站在本机对跑，寄存器写入→读回→逐字比对。
这是"协议层能通讯"的真跑事实——有了这层，接真 PLC/网关只差
IP/端口/寄存器表（客户现场的配置工作）。

诚实边界：Modbus 只是工控最薄的一层协议；profinet/ethercat 等实时
总线需要专用硬件与主站授权，不在此证明范围（不吹）。
"""

import socket
import struct
import threading
import time

# 从站寄存器表（保持寄存器 FC03/FC06 操作对象）
REGS = {0: 0x4244, 1: 0x5355, 2: 0x2026, 3: 0x0001}   # "BDSU 2026" 彩蛋


def slave_server(host="127.0.0.1", port=15020, run_seconds=8):
    """极简 Modbus TCP 从站。返回 (处理请求数, 读回校验结果列表)。"""
    regs = dict(REGS)
    served = []
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    srv.settimeout(run_seconds)
    end = time.time() + run_seconds

    def handle(conn):
        while time.time() < end:
            try:
                data = conn.recv(260)
            except (socket.timeout, OSError):
                return
            if not data or len(data) < 8:
                return
            tid, pid, ln, uid, fc = struct.unpack(">HHHBB", data[:8])
            if pid != 0:
                continue
            if fc == 3:                                     # 读保持寄存器
                addr, n = struct.unpack(">HH", data[8:12])
                vals = [regs.get(addr + i, 0) for i in range(n)]
                body = struct.pack(">BBB", uid, fc, n * 2) + b"".join(
                    struct.pack(">H", v) for v in vals)
                conn.sendall(struct.pack(">HHH", tid, 0, len(body)) + body)
                served.append(("read", addr, n, vals))
            elif fc == 6:                                   # 写单寄存器
                addr, val = struct.unpack(">HH", data[8:12])
                regs[addr] = val
                conn.sendall(data)                          # 原样回显=确认
                served.append(("write", addr, val))

    def serve():
        while time.time() < end:
            try:
                conn, _ = srv.accept()
                conn.settimeout(2)
                threading.Thread(target=handle, args=(conn,),
                                 daemon=True).start()
            except socket.timeout:
                break

    threading.Thread(target=serve, daemon=True).start()
    return regs, served


def master_read(host, port, addr, n, unit=1):
    """主站：FC03 读保持寄存器。带短包/时序容错（3 次重试）。"""
    tid = int(time.time()) & 0xFFFF
    pdu = struct.pack(">HHHBBHH", tid, 0, 6, unit, 3, addr, n)
    for attempt in range(3):
        try:
            s = socket.create_connection((host, port), timeout=3)
            s.settimeout(3)
            s.sendall(pdu)
            resp = b""
            while len(resp) < 9:
                chunk = s.recv(260)
                if not chunk:
                    break
                resp += chunk
            if len(resp) >= 9:
                want = 9 + resp[8]
                while len(resp) < want:
                    chunk = s.recv(260)
                    if not chunk:
                        break
                    resp += chunk
            s.close()
            if len(resp) >= 9 and resp[7] == 3 and len(resp) >= 9 + n * 2:
                return list(struct.unpack(f">{n}H", resp[9:9 + n * 2]))
        except (OSError, struct.error):
            pass
        time.sleep(0.3)
    return []


def master_write(host, port, addr, val, unit=1):
    tid = int(time.time()) & 0xFFFF
    pdu = struct.pack(">HHHBBHH", tid, 0, 6, unit, 6, addr, val)
    s = socket.create_connection((host, port), timeout=3)
    s.sendall(pdu)
    resp = s.recv(260)
    s.close()
    return resp[:12] == pdu          # 回显一致=写确认


def selfloop_proof():
    """自环证明：起从站 → 主站写 → 主站读回 → 比对。返回报告 dict。"""
    port = 15020
    regs, _ = slave_server(port=port, run_seconds=10)
    time.sleep(0.5)
    report = {"port": port, "steps": [], "ok": True}
    w = 0x6688
    ok_w = master_write("127.0.0.1", port, 2, w)
    report["steps"].append(f"FC06 写寄存器[2]={hex(w)} → {'确认' if ok_w else '失败'}")
    report["ok"] &= ok_w
    vals = master_read("127.0.0.1", port, 0, 4)
    expect = [regs[0], regs[1], w, regs[3]]
    match = vals == expect
    report["steps"].append(f"FC03 读[0..3] → {['%04X' % v for v in vals]} "
                           f"→ {'与写入一致' if match else '不一致'}")
    report["ok"] &= match
    report["expect"] = ['%04X' % v for v in expect]
    return report


if __name__ == "__main__":
    r = selfloop_proof()
    print("丙大山工控探针 · Modbus TCP 自环证明")
    for s in r["steps"]:
        print("  ", s)
    print("结论：", "协议层通讯真跑通过" if r["ok"] else "未通过")
