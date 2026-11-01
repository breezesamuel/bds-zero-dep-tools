# -*- coding: utf-8 -*-
"""丙大山硬件自感知探针（第 62 轮）——用真跑回答"能不能接管任何硬件"。

诚实的答案分两层（写死在代码里，不自欺）：
【真能】USB 协议层的"自我描述"：每台 USB 设备上电即上报 VID/PID/类/
厂商/产品名——本探针真实扫描本机注册表枚举全部 USB 设备、识别已知
芯片厂牌、标注可接管通道（HID/串口 CDC/存储/Hub），并列出真实串口。
这就是"自感知·自识别·自适应"的协议层事实依据。
【不能（谁承诺谁撒谎）】厂商私有固件命令集（无文档不可"理解"）、
需内核驱动的设备、GPIO 引脚电气配置（需要板子原理图，不是软件问题）。
"任何硬件零人工全接管"= USB-IF 用 30 年才做到**标准类设备**即插即用；
我们做的是把标准类设备的自描述用到极致 + 已知协议知识库。
"""

import winreg

# 常见芯片/厂商 VID 知识库（自建，可持续扩充——这就是"自学习"的种子）
VID_KB = {
    "045E": "Microsoft（键鼠/HUB/Xbox）", "8087": "Intel（蓝牙/HUB）",
    "1A86": "沁恒 CH340/CH9102 串口（单片机最常见）",
    "10C4": "Silicon Labs CP210x 串口", "0403": "FTDI 串口/FPGA",
    "2341": "Arduino 官方", "2E8A": "树莓派 RP2040",
    "303A": "乐鑫 ESP32 原生USB", "0483": "STMicro（STM32 DFU/虚拟串口）",
    "046D": "罗技", "093A": "Pixart 摄像头", "0BDA": "Realtek（网卡/读卡器）",
    "13FE": "群联 U盘", "0951": "金士顿", "125F": "ADATA",
    "05AC": "Apple", "05E3": "Genesys HUB", "2109": "VIA HUB",
    "046A": "Cherry 键盘", "17EF": "联想", "154B": "VMware 虚拟",
    "06CB": "Synaptics 指纹/触控", "2717": "小米", "12D1": "华为",
    "22B7": "摩托罗拉", "18D1": "Google/Android", "04E8": "三星",
}
CLS_KB = {
    "Mouse": "HID 鼠标 → 可接管通道：HID 报文（读移动/按键）",
    "Keyboard": "HID 键盘 → 可接管：HID 报文",
    "MEDIA": "U盘/存储 → 可接管：块设备读写",
    "Ports": "串口设备 → 可接管：COM 口 AT/自定义帧协议",
    "HIDClass": "HID 设备 → 可接管：HID 报文",
    "DiskDrive": "磁盘 → 块设备",
    "USB": "USB 设备/Hub",
    "Net": "网卡 → 可接管：NDIS/ECM",
    "Bluetooth": "蓝牙 → 标准蓝牙栈",
    "Image": "摄像头 → UVC 标准（OpenCV 可开）",
    "System": "系统设备（电源/HUB）",
    "WPD": "便携设备（MTP/PTP）→ 可接管：文件对象协议",
    "Printer": "打印机 → ESC/POS 等打印语言",
    "Monitor": "显示器（DDC/CI 可控亮度）",
}


def _open(path):
    return winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)


def scan_usb():
    """枚举注册表 USB 设备树 → 结构化清单。"""
    out = []
    try:
        root = _open(r"SYSTEM\CurrentControlSet\Enum\USB")
    except OSError:
        return out
    i = 0
    while True:
        try:
            dev = winreg.EnumKey(root, i)
        except OSError:
            break
        i += 1
        # dev 形如 VID_045E&PID_0745
        vid = pid = ""
        for part in dev.split("&"):
            if part.startswith("VID_"):
                vid = part[4:]
            if part.startswith("PID_"):
                pid = part[4:]
        try:
            k = _open(rf"SYSTEM\CurrentControlSet\Enum\USB\{dev}")
        except OSError:
            continue
        j = 0
        while True:
            try:
                inst = winreg.EnumKey(k, j)
            except OSError:
                break
            j += 1
            try:
                ik = _open(rf"SYSTEM\CurrentControlSet\Enum\USB\{dev}\{inst}")
                desc, mfg, cls, svc = "", "", "", ""
                for name, want in (("DeviceDesc", "desc"), ("Mfg", "mfg"),
                                   ("Class", "cls"), ("Service", "svc")):
                    try:
                        v, _ = winreg.QueryValueEx(ik, name)
                        v = str(v)
                        # 设备描述常带 @xxx.inf,%...%;前缀——剥掉
                        if ";" in v and v.startswith("@"):
                            v = v.split(";")[-1]
                        if want == "desc":
                            desc = v
                        elif want == "mfg":
                            mfg = v
                        elif want == "cls":
                            cls = v
                        else:
                            svc = v
                    except OSError:
                        pass
                out.append({
                    "vid": vid, "pid": pid, "desc": desc, "mfg": mfg,
                    "class": cls, "service": svc,
                    "vendor": VID_KB.get(vid.upper(), ""),
                    "takeover": CLS_KB.get(cls, "") or
                                CLS_KB.get(svc, ""),
                })
            except OSError:
                continue
    return out


def scan_serial():
    """真实枚举本机串口（自发现，不预设）。"""
    out = []
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"HARDWARE\DEVICEMAP\SERIALCOMM")
        i = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(k, i)
            except OSError:
                break
            out.append((name.split("\\")[-1], val))
            i += 1
    except OSError:
        pass
    return out


def report():
    devs = scan_usb()
    serials = scan_serial()
    known = [d for d in devs if d["vendor"] or d["takeover"]]
    lines = ["=" * 64,
             "丙大山硬件自感知探针 · 真机扫描报告（零依赖，纯注册表枚举）",
             "=" * 64,
             f"USB 设备实例总数：{len(devs)}",
             f"已识别（VID 知识库/类通道命中）：{len(known)}",
             f"自发现串口：{len(serials)} 个 "
             + (", ".join(f"{n}→{c}" for n, c in serials) if serials else "(无)"),
             "-" * 64]
    for d in devs:
        tag = d["vendor"] or "（未知厂商——VID 未入库，可扩充知识库后识别）"
        lines.append(f"USB VID_{d['vid']} PID_{d['pid']}  {tag}")
        if d["desc"]:
            lines.append(f"    描述: {d['desc'][:60]}")
        if d["takeover"]:
            lines.append(f"    {d['takeover']}")
    lines += ["-" * 64,
              "诚实边界：以上=协议层自描述事实。厂商私有命令集/需内核驱动的"
              "设备/GPIO 电气配置，不在『插上就能懂』的范围——需要文档或"
              "原理图，这是物理事实，不是能力姿态。",
              "=" * 64]
    return "\n".join(lines), devs, serials


if __name__ == "__main__":
    txt, devs, serials = report()
    print(txt)
