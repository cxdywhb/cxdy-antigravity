#!/usr/bin/env python3
"""安装或卸载官方 Antigravity 的本机代理与界面增强。"""

import argparse
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parent
HOME_ROOT = Path.home()
TARGET_APP = Path("/Applications/Antigravity.app")
INSTALL_DIR = HOME_ROOT / "Library/Application Support/Antigravity Desktop Enhancements"
LABEL = "local.antigravity.interface-enhancements"
PLIST = HOME_ROOT / "Library/LaunchAgents" / f"{LABEL}.plist"
DOMAIN = f"gui/{os.getuid()}"
JOB = f"{DOMAIN}/{LABEL}"
APP_VERSION = "2.34.0"
BEGIN = "# >>> antigravity-desktop-enhancements >>>"
END = "# <<< antigravity-desktop-enhancements <<<"


def run(*args, **options):
    return subprocess.run(args, check=True, **options)


def prerequisites():
    if sys.platform != "darwin":
        raise ValueError("安装仅支持 macOS。")
    with (TARGET_APP / "Contents/Info.plist").open("rb") as source:
        info = plistlib.load(source)
    if (info.get("CFBundleIdentifier"), info.get("CFBundleShortVersionString")) != (
        "com.google.antigravity", APP_VERSION
    ):
        raise ValueError(f"请先安装官方 Antigravity {APP_VERSION} 到 /Applications。")
    requirement = (
        'anchor apple generic and certificate leaf[subject.OU] = "EQHXZ8M8AV" '
        'and identifier "com.google.antigravity"'
    )
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", "-R=" + requirement, str(TARGET_APP))
    node = shutil.which("node")
    if not node:
        raise ValueError("终端中未找到 Node.js，请先安装 Node.js 22.4 或更高版本。")
    version = run(node, "--version", capture_output=True, text=True).stdout.strip()
    match = re.match(r"v(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (22, 4):
        raise ValueError("Context Viewer 需要 Node.js 22.4 或更高版本。")
    swift = run("/usr/bin/xcrun", "--find", "swiftc", capture_output=True, text=True).stdout.strip()
    run("/bin/launchctl", "print", DOMAIN, stdout=subprocess.DEVNULL)
    return os.path.abspath(node), swift


def managed_proxy(text, port=None):
    marker_counts = [text.splitlines().count(marker) for marker in (BEGIN, END)]
    if marker_counts == [1, 1]:
        pattern = re.compile(r"^" + re.escape(BEGIN) + r"\n.*?^" + re.escape(END) + r"(?:\n|$)", re.M | re.S)
        text, count = pattern.subn("", text)
        if count != 1:
            raise ValueError("代理配置标记顺序不正确，请先手动检查 .zshenv。")
    elif marker_counts != [0, 0]:
        raise ValueError("代理配置标记不完整或重复，请先手动检查 .zshenv。")
    if port is None:
        return text
    block = (PACKAGE / "src/proxy.zsh.in").read_text(encoding="utf-8").replace("@PORT@", str(port))
    if text and not text.endswith("\n"):
        text += "\n"
    return text + block


def write_atomic(target, content, mode=0o600):
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as out:
        tmp = Path(out.name)
        try:
            os.fchmod(out.fileno(), mode)
            out.write(content)
            out.close()
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)


def job_loaded():
    return subprocess.run(
        ["/bin/launchctl", "print", JOB], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def make_manifest(node):
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(INSTALL_DIR / "AntigravityLauncher"), str(INSTALL_DIR / "context-viewer"),
            str(INSTALL_DIR / "load-interface.cjs"), node
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "LimitLoadToSessionType": "Aqua",
        "StandardOutPath": str(INSTALL_DIR / "运行日志.log"),
        "StandardErrorPath": str(INSTALL_DIR / "运行日志.log"),
        "WorkingDirectory": str(INSTALL_DIR),
    }


def install(port):
    if not 1 <= port <= 65535:
        raise ValueError("Clash 混合端口必须在 1 到 65535 之间。")
    if PLIST.exists() or PLIST.is_symlink() or INSTALL_DIR.exists() or INSTALL_DIR.is_symlink() or job_loaded():
        raise ValueError("已有同名后台任务或安装目录。请核对现有安装，避免覆盖。")
    node, swift = prerequisites()
    startup = (Path(os.environ.get("ZDOTDIR") or HOME_ROOT).expanduser() / ".zshenv").resolve()
    existed = startup.is_file()
    saved = startup.read_bytes() if existed else b""
    mode = stat.S_IMODE(startup.stat().st_mode) if existed else 0o600
    text = saved.decode("utf-8")
    if managed_proxy(text) != text:
        raise ValueError(".zshenv 已留有本交付包的代理配置段，请先核对旧安装。")
    patched = managed_proxy(text, port).encode("utf-8")

    PLIST.parent.mkdir(parents=True, exist_ok=True)
    INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=INSTALL_DIR.parent, prefix=".antigravity-setup-") as tmp:
        stage = Path(tmp) / "runtime"
        stage.mkdir(mode=0o700)
        shutil.copytree(PACKAGE / "vendor/context-viewer", stage / "context-viewer")
        shutil.copy2(PACKAGE / "src/load-interface.cjs", stage / "load-interface.cjs")
        run(node, "--check", str(stage / "load-interface.cjs"))
        run(swift, "-O", str(PACKAGE / "src/AntigravityLauncher.swift"), "-o", str(stage / "AntigravityLauncher"))
        (stage / "startup-path.txt").write_text(str(startup), encoding="utf-8")
        (stage / "原始代理配置备份").write_bytes(saved)
        rc_check = Path(tmp) / "zshenv"
        rc_check.write_bytes(patched)
        run("/bin/zsh", "-n", str(rc_check))
        agent_data = plistlib.dumps(make_manifest(node))
        if PLIST.exists() or PLIST.is_symlink() or job_loaded():
            raise ValueError("安装期间出现同名后台任务，请先核对。")
        if (startup.exists() != existed) or (existed and startup.read_bytes() != saved):
            raise ValueError(".zshenv 在安装期间已变化，请重新运行安装。")
        stage.rename(INSTALL_DIR)

    try:
        write_atomic(startup, patched, mode)
        write_atomic(PLIST, agent_data, 0o644)
        run("/bin/launchctl", "bootstrap", DOMAIN, str(PLIST))
    except BaseException:
        if job_loaded():
            run("/bin/launchctl", "bootout", JOB)
        PLIST.unlink(missing_ok=True)
        if startup.exists() and startup.read_bytes() == patched:
            if existed:
                write_atomic(startup, saved, mode)
            else:
                startup.unlink()
        shutil.rmtree(INSTALL_DIR)
        raise

    print("安装完成。请退出已打开的 Antigravity，再点击官方图标。")


def uninstall():
    with PLIST.open("rb") as source:
        manifest = plistlib.load(source)
    if manifest.get("ProgramArguments", [None])[0] != str(INSTALL_DIR / "AntigravityLauncher"):
        raise ValueError("这个后台任务由其他安装维护，请使用对应的卸载方法。")
    startup = Path((INSTALL_DIR / "startup-path.txt").read_text(encoding="utf-8"))
    previous = startup.read_text(encoding="utf-8") if startup.is_file() else None
    cleaned = managed_proxy(previous) if previous is not None else None
    if job_loaded():
        run("/bin/launchctl", "bootout", JOB)
    if cleaned != previous:
        write_atomic(startup, cleaned.encode("utf-8"), stat.S_IMODE(startup.stat().st_mode))
    PLIST.unlink()
    shutil.rmtree(INSTALL_DIR)
    print("已移除后台启动与本包新增的代理配置。退出并重新打开官方 App 后生效。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install", "uninstall"))
    parser.add_argument("--port", type=int, default=7897, help="Clash 的 HTTP 或混合代理端口")
    options = parser.parse_args()
    if options.action == "check":
        node, swift = prerequisites()
        print(f"已确认官方 App 签名、用户图形会话和运行工具。\nNode.js: {node}\nSwift: {swift}")
    elif options.action == "install":
        install(options.port)
    else:
        uninstall()


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        sys.exit(f"操作未完成。{exc}")
