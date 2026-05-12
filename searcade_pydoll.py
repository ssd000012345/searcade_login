import asyncio
import os
import re
import logging
import random
import base64
import json
from pathlib import Path
from datetime import datetime
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
import ddddocr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ========== 配置 ==========
EMAIL = os.environ["SEARCADE_EMAIL"]
PASSWORD = os.environ["SEARCADE_PASSWORD"]
BASE_URL = "https://searcade.com/en/"
LOGIN_URL = "https://searcade.com/en/"
USERVERIA_AUTH_URL = "https://userveria.com/authorize/"
REDIRECT_URI = "https://searcade.com/accounts/userveria/login/callback/"

SCREENSHOT_DIR = Path("./screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

WXPUSHER_TOKEN = os.environ.get("WXPUSHER_TOKEN", "")
WXPUSHER_UID   = os.environ.get("WXPUSHER_UID", "")

def wxpush(content: str):
    if not WXPUSHER_TOKEN or not WXPUSHER_UID:
        return
    import urllib.request
    payload = json.dumps({
        "appToken": WXPUSHER_TOKEN,
        "content": content,
        "contentType": 1,
        "uids": [WXPUSHER_UID],
    }).encode()
    try:
        req = urllib.request.Request(
            "https://wxpusher.zjiecode.com/api/send/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                log.info("📨 WxPusher 推送成功")
            else:
                log.warning(f"📨 WxPusher 推送失败: {result}")
    except Exception as e:
        log.warning(f"📨 WxPusher 推送异常: {e}")

ocr = ddddocr.DdddOcr(beta=True, show_ad=False)

# ========== 辅助函数（原样保留） ==========
async def take_screenshot(browser, tab, name):
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(SCREENSHOT_DIR / f"{ts}_{name}.png")
        await tab.take_screenshot(path=path)
        log.info(f"📸 截图: {path}")
    except Exception as e:
        log.warning(f"截图失败: {e}")

async def get_text(tab):
    try:
        result = await tab.execute_script("return document.body.innerText")
        if isinstance(result, dict):
            return result.get("result", {}).get("result", {}).get("value", "")
        return str(result)
    except:
        return ""

async def get_url(tab):
    try:
        result = await tab.execute_script("return window.location.href")
        if isinstance(result, dict):
            return result.get("result", {}).get("result", {}).get("value", "")
        return str(result)
    except:
        return ""

async def human_delay(min_s=0.3, max_s=0.8):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def wait_for_url_contains(tab, keyword, timeout=10):
    for _ in range(timeout * 2):
        url = await get_url(tab)
        if keyword in url:
            return True
        await asyncio.sleep(0.5)
    return False

async def wait_for_element_by_text(tab, text, timeout=10):
    for _ in range(timeout * 2):
        body = await get_text(tab)
        if text in body:
            return True
        await asyncio.sleep(0.5)
    return False

# ========== Cloudflare 处理（原封不动拷贝） ==========
async def manual_cf_click(tab, timeout=15):
    log.info("尝试手动完成 Cloudflare 验证（Shadow DOM 穿透点击）...")
    for i in range(timeout):
        body = await get_text(tab)
        if "email" in body or "登录" in body or "请输入邮箱" in body or "用户中心" in body:
            log.info("✅ Cloudflare 验证已通过")
            return True
        try:
            shadow_roots = await tab.find_shadow_roots(deep=False)
            cf_shadow = None
            for sr in shadow_roots:
                try:
                    html = await sr.inner_html
                    if "challenges.cloudflare.com" in html:
                        cf_shadow = sr
                        break
                except:
                    pass
            if cf_shadow is None:
                await asyncio.sleep(1)
                continue
            iframe_el = await cf_shadow.query('iframe[src*="challenges.cloudflare.com"]', timeout=3)
            body_el = await iframe_el.find(tag_name="body", timeout=3)
            inner_shadow = await body_el.get_shadow_root(timeout=3)
            checkbox = await inner_shadow.query("span.cb-i", timeout=3)
            await checkbox.click()
            log.info("已点击 Cloudflare checkbox，等待验证...")
            await asyncio.sleep(3)
            body2 = await get_text(tab)
            if "email" in body2 or "登录" in body2 or "请输入邮箱" in body2 or "用户中心" in body2:
                log.info("✅ 点击后验证通过")
                return True
        except Exception as e:
            log.info(f"第{i+1}s: {e}")
        await asyncio.sleep(1)
    log.error("Cloudflare 验证超时")
    return False

async def ensure_cf_passed(tab, url, timeout=15):
    try:
        async with tab.expect_and_bypass_cloudflare_captcha():
            await tab.go_to(url)
    except:
        await tab.go_to(url)
    for _ in range(timeout):
        body = await get_text(tab)
        if "verify you are human" not in body.lower() and "cloudflare" not in body.lower():
            return True
        await asyncio.sleep(1)
    return await manual_cf_click(tab)

# ========== 验证码识别（备用） ==========
async def fill_captcha(tab):
    for _ in range(3):
        cap_img = None
        try:
            cap_img = await tab.find(id="allow_login_email_captcha", timeout=5)
        except:
            pass
        if not cap_img:
            try:
                cap_img = await tab.find(tag_name="img", alt="验证码", timeout=5)
            except:
                pass
        if cap_img:
            src = cap_img.get_attribute("src")
            if src and src.startswith("data:image"):
                b64 = src.split(",", 1)[1]
                img_bytes = base64.b64decode(b64)
                raw = ocr.classification(img_bytes)
                code = re.sub(r'[^0-9]', '', raw)
                log.info(f"识别验证码: {code}")
                await tab.execute_script(f"""
                    (function() {{
                        var input =
                            document.querySelector('#captcha_allow_login_email_captcha') ||
                            document.querySelector('input[name="captcha"]') ||
                            document.querySelector('input[placeholder*="验证码"]');
                        if (input) {{
                            input.focus();
                            input.value = '{code}';
                            input.dispatchEvent(new Event('input', {{bubbles:true}}));
                            input.dispatchEvent(new Event('change', {{bubbles:true}}));
                        }}
                    }})()
                """)
                return code
        await asyncio.sleep(1)
    return ""

# ========== 浏览器创建（复用原项目） ==========
def _find_chromium() -> str | None:
    candidates = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for p in candidates:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            log.info(f"找到 Chromium: {p}")
            return p
    import subprocess
    try:
        result = subprocess.run(["which", "chromium-browser"], capture_output=True, text=True, timeout=5)
        path = result.stdout.strip()
        if path and os.path.isfile(path):
            return path
    except:
        pass
    return None

async def create_browser():
    opts = ChromiumOptions()
    opts.headless = False  # 配合 xvfb 使用
    path = _find_chromium()
    if path:
        opts.binary_location = path

    opts.add_argument("--window-size=1280,720")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-features=VizDisplayCompositor")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--exclude-switches=enable-automation")
    opts.add_argument("--disable-infobars")
    # 代理已注释（如需代理请取消注释并配置 socks5）
    # opts.add_argument("--proxy-server=socks5://127.0.0.1:10808")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_argument("--disable-save-password-bubble")
    opts.add_argument("--disable-password-generation")
    opts.add_argument("--password-store=basic")
    opts.add_argument("--use-mock-keychain")

    opts.browser_preferences = {
        "credentials_enable_service": False,
        "credentials_enable_autosign": False,
        "profile": {
            "password_manager_enabled": False,
            "default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
            },
        },
        "autofill": {"enabled": False},
        "intl": {"accept_languages": "zh-CN,zh,en-US,en"},
    }

    browser = await Chrome(options=opts).__aenter__()
    tab = await browser.start()

    # 指纹伪装
    try:
        await tab.execute_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)
    except:
        pass

    return browser, tab

# ========== Searcade 登录流程（两步登录） ==========
async def login_searcade(browser, tab):
    log.info("开始登录 Searcade...")

    # 1. 访问首页，处理可能的 CF
    await ensure_cf_passed(tab, BASE_URL)
    await take_screenshot(browser, tab, "01_home")

    # 2. 点击 Login 按钮
    log.info("点击登录按钮")
    try:
        login_btn = await tab.find(tag_name="a", text="Login", timeout=10)
    except:
        login_btn = await tab.find(tag_name="button", text="Login", timeout=10)
    await login_btn.click()
    await asyncio.sleep(2)

    # 3. 等待跳转到 userveria OAuth 页面
    if not await wait_for_url_contains(tab, "userveria.com", timeout=15):
        log.warning("未跳转到 userveria，当前 URL: " + await get_url(tab))
        # 若未跳转，尝试直接构造 OAuth URL
        oauth_url = f"{USERVERIA_AUTH_URL}?client_id=8305d2e2-e91f-4deb-8909-f669259bc23f&redirect_uri={REDIRECT_URI}&scope=profile&response_type=code"
        await tab.go_to(oauth_url)
        await asyncio.sleep(2)

    # 4. 处理 OAuth 页面上的 CF 验证
    await ensure_cf_passed(tab, await get_url(tab))

    # 5. 填写邮箱并点击 "Continue with email"
    log.info("填写邮箱并点击 Continue with email")
    try:
        email_input = await tab.find(tag_name="input", name="email", timeout=10)
    except:
        email_input = await tab.find(tag_name="input", type="email", timeout=10)
    await email_input.click()
    await email_input.type_text(EMAIL, humanize=True)
    await human_delay()

    try:
        continue_btn = await tab.find(tag_name="button", text="Continue with email", timeout=10)
    except:
        continue_btn = await tab.find(tag_name="button", text="Continue", timeout=10)
    await continue_btn.click()
    log.info("已点击 Continue with email")

    # 6. 等待密码输入框出现（可能伴随新的 CF 挑战）
    await asyncio.sleep(2)
    await ensure_cf_passed(tab, await get_url(tab))

    log.info("等待密码输入框")
    try:
        pass_input = await tab.find(tag_name="input", name="password", timeout=15)
    except:
        pass_input = await tab.find(tag_name="input", type="password", timeout=15)
    await pass_input.click()
    await pass_input.type_text(PASSWORD, humanize=True)
    await human_delay()

    # 7. 提交登录
    log.info("点击登录提交")
    try:
        submit_btn = await tab.find(tag_name="button", text="Log in", timeout=10)
    except:
        submit_btn = await tab.find(tag_name="button", type="submit", timeout=10)
    await submit_btn.click()

    # 8. 等待重定向回 searcade.com
    if await wait_for_url_contains(tab, "searcade.com", timeout=20):
        log.info("✅ 成功回调至 Searcade")
    else:
        log.warning("未检测到回调，当前 URL: " + await get_url(tab))

    await asyncio.sleep(3)
    await take_screenshot(browser, tab, "02_logged_in")

    # 9. 验证登录成功
    body = await get_text(tab)
    if "logout" in body.lower() or "sign out" in body.lower() or "dashboard" in body.lower():
        log.info("✅ 登录验证成功")
        return True
    else:
        log.error("❌ 登录后未找到成功标识")
        return False

# ========== 主流程 ==========
async def main():
    browser, tab = None, None
    try:
        browser, tab = await create_browser()
        success = await login_searcade(browser, tab)
        if success:
            wxpush("✅ Searcade 自动登录成功")
        else:
            wxpush("❌ Searcade 登录失败，请检查截图")
    except Exception as e:
        log.exception(e)
        if browser and tab:
            await take_screenshot(browser, tab, "99_error")
        wxpush(f"❌ Searcade 登录异常: {e}")
    finally:
        if browser:
            await asyncio.sleep(5)
            await browser.__aexit__(None, None, None)
        log.info("任务结束")

if __name__ == "__main__":
    asyncio.run(main())
