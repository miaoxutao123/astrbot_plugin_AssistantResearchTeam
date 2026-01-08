"""浏览器下载和配置工具.

支持使用Playwright下载Chromium到项目文件夹。
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# Chromium安装目录（项目文件夹内）
CHROMIUM_DIR = PROJECT_ROOT / "browsers" / "chromium"
PLAYWRIGHT_BROWSERS_DIR = PROJECT_ROOT / "browsers" / "playwright"


def get_chrome_path_in_project() -> str | None:
    """获取项目内的Chromium路径（包括Playwright下载的）."""
    system = platform.system()
    
    # 检查旧位置
    if system == "Windows":
        chrome_exe = CHROMIUM_DIR / "chrome.exe"
    elif system == "Darwin":
        chrome_exe = CHROMIUM_DIR / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
    else:
        chrome_exe = CHROMIUM_DIR / "chrome"
    
    if chrome_exe.exists():
        return str(chrome_exe)
    
    # 搜索旧目录
    if CHROMIUM_DIR.exists():
        for root, _dirs, files in os.walk(CHROMIUM_DIR):
            if system == "Windows" and "chrome.exe" in files:
                return os.path.join(root, "chrome.exe")
            elif system != "Windows" and "chrome" in files:
                return os.path.join(root, "chrome")
    
    # 搜索Playwright下载的浏览器
    if PLAYWRIGHT_BROWSERS_DIR.exists():
        for root, _dirs, files in os.walk(PLAYWRIGHT_BROWSERS_DIR):
            if system == "Windows" and "chrome.exe" in files:
                return os.path.join(root, "chrome.exe")
            elif system != "Windows" and "chrome" in files:
                chrome_path = os.path.join(root, "chrome")
                if os.access(chrome_path, os.X_OK):
                    return chrome_path
    
    return None


def load_chrome_path_from_config() -> str | None:
    """从配置文件加载Chrome路径."""
    config_file = PROJECT_ROOT / ".chrome_path"
    try:
        if config_file.exists():
            path = config_file.read_text().strip()
            if os.path.exists(path):
                return path
    except Exception:
        pass
    return None


def save_chrome_path(chrome_path: str) -> None:
    """保存Chrome路径到配置文件."""
    config_file = PROJECT_ROOT / ".chrome_path"
    try:
        config_file.write_text(chrome_path)
    except Exception:
        pass


def find_chrome_path() -> str | None:
    """自动查找Chrome/Chromium浏览器路径.
    
    优先级：
    1. 项目内的Chromium
    2. 配置文件中保存的路径
    3. 系统安装的Chrome
    """
    # 1. 检查项目内的Chromium
    project_chrome = get_chrome_path_in_project()
    if project_chrome:
        return project_chrome
    
    # 2. 检查配置文件
    saved_path = load_chrome_path_from_config()
    if saved_path:
        return saved_path

    system = platform.system()

    # 3. 检查系统安装的Chrome
    if system == "Windows":
        # 检查本地下载的Chromium（旧位置）
        local_chromium = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "chromium"
        )
        for root, _dirs, files in os.walk(local_chromium):
            if "chrome.exe" in files:
                return os.path.join(root, "chrome.exe")

    # 尝试DrissionPage内置查找（排除Edge）
    try:
        from DrissionPage._functions.browser import get_chrome_path
        chrome_path = get_chrome_path(show_msg=False)
        if chrome_path and os.path.exists(chrome_path) and "edge" not in chrome_path.lower():
            return chrome_path
    except Exception:
        pass

    # 常见路径
    if system == "Windows":
        possible_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    elif system == "Darwin":
        possible_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        possible_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def download_chromium_via_playwright() -> str | None:
    """使用Playwright下载Chromium到项目文件夹."""
    print("=" * 50)
    print("使用Playwright下载Chromium浏览器")
    print("=" * 50)
    print(f"安装目录: {PLAYWRIGHT_BROWSERS_DIR}")
    
    # 确保playwright已安装
    try:
        import playwright
    except ImportError:
        print("正在安装playwright...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
    
    # 设置环境变量，指定下载目录
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_BROWSERS_DIR)
    
    # 下载chromium
    print("正在下载Chromium...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"下载失败: {result.stderr}")
            return None
        print("下载完成")
    except Exception as e:
        print(f"下载失败: {e}")
        return None
    
    # 查找下载的浏览器路径
    chrome_path = get_chrome_path_in_project()
    if chrome_path:
        save_chrome_path(chrome_path)
        print(f"✓ Chromium安装成功: {chrome_path}")
        return chrome_path
    
    print("未找到下载的浏览器")
    return None


def download_chromium() -> str | None:
    """下载Chromium到项目文件夹."""
    return download_chromium_via_playwright()


def setup_virtual_display() -> object | None:
    """在Linux上设置虚拟显示器."""
    if platform.system() != "Linux":
        return None

    display = os.environ.get("DISPLAY")
    if display:
        return None

    try:
        from pyvirtualdisplay import Display
        virtual_display = Display(visible=0, size=(1920, 1080))
        virtual_display.start()
        return virtual_display
    except ImportError:
        print("警告: 未安装pyvirtualdisplay")
        return None
    except Exception:
        return None


def ensure_browser() -> str | None:
    """确保有可用的浏览器，没有则自动下载.
    
    Returns:
        浏览器路径
    """
    # 先查找现有浏览器
    chrome_path = find_chrome_path()
    if chrome_path:
        return chrome_path
    
    # 没有找到，自动下载
    print("未检测到Chrome/Chromium浏览器，开始自动下载...")
    return download_chromium()


if __name__ == "__main__":
    # 直接运行此脚本可下载Chromium
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        path = find_chrome_path()
        if path:
            print(f"找到浏览器: {path}")
        else:
            print("未找到浏览器")
        sys.exit(0 if path else 1)
    
    # 检查是否已有浏览器
    existing = find_chrome_path()
    if existing:
        print(f"已找到浏览器: {existing}")
        choice = input("是否仍要下载新的Chromium到项目目录? (y/N): ").strip().lower()
        if choice != "y":
            sys.exit(0)
    
    chrome_path = download_chromium()
    if chrome_path:
        print("\n设置完成！")
    else:
        sys.exit(1)