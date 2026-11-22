#!/usr/bin/env python3
"""在临时目录中检查安装、卸载和启动任务失败后的回滚。"""

from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import plistlib
import subprocess
import tempfile
from unittest.mock import patch

module_path = Path(__file__).resolve().parents[1] / "setup.py"
spec = importlib.util.spec_from_file_location("antigravity_setup", module_path)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
original = "# 已有的用户配置\nexport EXAMPLE_SETTING=1\n"
later_edit = "# 安装后追加的配置\n"


def exercise(bootstrap_fails):
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        startup = home / ".zshenv"
        startup.write_text(original, encoding="utf-8")
        startup.chmod(0o640)
        agent = home / "LaunchAgents/demo.plist"
        runtime = home / "local runtime"
        loaded = False

        def simulate(*args, **kwargs):
            nonlocal loaded
            if args[0] == "/bin/zsh":
                return subprocess.run(args, check=True, **kwargs)
            if "-o" in args and args[0] == "mock-swiftc":
                Path(args[args.index("-o") + 1]).touch()
            if args[:2] == ("/bin/launchctl", "bootstrap"):
                if bootstrap_fails:
                    raise subprocess.CalledProcessError(1, args)
                loaded = True
            if args[:2] == ("/bin/launchctl", "bootout"):
                loaded = False

        with patch.multiple(
            setup,
            HOME_ROOT=home, INSTALL_DIR=runtime, PLIST=agent, run=simulate,
            job_loaded=lambda: loaded, prerequisites=lambda: ("/some path/node", "mock-swiftc"),
        ), patch.dict(setup.os.environ, {"ZDOTDIR": str(home)}), redirect_stdout(io.StringIO()):
            if bootstrap_fails:
                try:
                    setup.install(7997)
                except subprocess.CalledProcessError:
                    pass
                else:
                    raise AssertionError("模拟启动失败时，安装应返回错误。")
                assert not runtime.exists() and not agent.exists()
                assert startup.read_text(encoding="utf-8") == original
            else:
                setup.install(7997)
                cfg = plistlib.loads(agent.read_bytes())
                assert loaded and cfg["ProgramArguments"][3] == "/some path/node"
                assert (runtime / "context-viewer/i18n/zh-CN.json").is_file()
                assert "http://127.0.0.1:7997" in startup.read_text(encoding="utf-8")
                with startup.open("a", encoding="utf-8") as f:
                    f.write(later_edit)
                setup.uninstall()
                assert not loaded and not agent.exists() and not runtime.exists()
                assert startup.read_text(encoding="utf-8") == original + later_edit
            assert startup.stat().st_mode & 0o777 == 0o640


assert setup.managed_proxy(setup.managed_proxy(original, 7897)) == original
exercise(bootstrap_fails=False)
exercise(bootstrap_fails=True)
print("代理配置、安装、卸载与失败回滚自检通过。")
