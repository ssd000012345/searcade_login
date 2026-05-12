import os
import asyncio
from playwright.async_api import async_playwright

# ── 常量 ────────────────────────────────────────────────────────────
SEARCADE_HOME      = "https://searcade.com/en/"
USERVERIA_PATTERNS = ["userveria.com", "searcade.userveria.com"]
SEARCADE_DOMAIN    = "searcade.com"

ADMIN_PATHS = [
    "/en/admin/",
    "/admin/",
    "/en/dashboard/",
    "/dashboard/",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 反检测脚本（来源：puppeteer-extra-stealth 的核心脚本）
STEALTH_JS = """
// 隐藏 navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
// 隐藏 chrome 属性
window.chrome = { runtime: {} };
// 修改 plugins 和 languages 使其更像普通浏览器
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
// 覆盖 permissions 查询
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);
// 更多细节（如 WebGL 指纹等）可以添加，但上述已足够绕过大多数反爬
"""

# ── 辅助函数 ──────────────────────────────────────────────────────
async def print_cookies(context, label: str):
    cookies = await context.cookies()
    searcade_cookies = [c for c in cookies if SEARCADE_DOMAIN in c["domain"]]
    print(f"  [{label}] Searcade Cookies ({len(searcade_cookies)} 个):")
    for c in searcade_cookies:
        print(f"    {c['name']} = {c['value'][:60]}")

async def take_screenshot(page, path: str):
    try:
        await page.screenshot(path=path, full_page=True)
        print(f"  📸 截图已保存: {path}")
    except Exception as e:
        print(f"  ⚠️ 截图失败: {e}")

async def click_first_match(page, selectors: list[str], timeout: int = 5000):
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout)
            await page.click(sel)
            print(f"  ✅ 点击成功: {sel}")
            return True
        except Exception:
            continue
    return False

# ── 主流程 ────────────────────────────────────────────────────────
async def run():
    email = os.environ.get("SEARCADE_EMAIL")
    password = os.environ.get("SEARCADE_PASSWORD")
    if not email or not password:
        raise ValueError("请设置环境变量 SEARCADE_EMAIL 和 SEARCADE_PASSWORD")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            record_video_dir="videos",  # 录屏保存目录
        )
        page = await context.new_page()

        # 注入反检测脚本（替代 playwright-stealth）
        await page.add_init_script(STEALTH_JS)

        # Step 1: 访问首页
        print("\n📸 登录前截图...")
        print("Step 1: 访问 Searcade 首页...")
        await page.goto(SEARCADE_HOME, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)
        await take_screenshot(page, "before_login.png")
        print(f"  当前 URL: {page.url}")

        # Step 2: 点击登录按钮
        print("\nStep 2: 点击登录按钮...")
        login_selectors = [
            "a[href*='login']",
            "a:has-text('Login')",
            "a:has-text('Sign in')",
            "button:has-text('Login')",
            ".login-btn",
            "#login",
        ]
        clicked = await click_first_match(page, login_selectors, timeout=8000)
        if not clicked:
            print("  ⚠️ 未找到登录按钮，尝试直接访问 OAuth 授权页...")
            await page.goto(
                "https://searcade.userveria.com/api/v1/oauth/authorize"
                "?client_id=8305d2e2-e91f-4deb-8909-f669259bc23f"
                "&redirect_uri=https%3A%2F%2Fsearcade.com%2Faccounts%2Fuserveria%2Flogin%2Fcallback%2F"
                "&scope=profile&response_type=code",
                wait_until="networkidle",
                timeout=30000,
            )

        # Step 3: 等待 OAuth 页面加载
        print("\nStep 3: 等待 OAuth 授权页面...")
        oauth_ready = False
        for pattern in USERVERIA_PATTERNS:
            try:
                await page.wait_for_url(f"**/{pattern}/**", timeout=15000)
                print(f"  ✅ 已跳转到: {page.url} (匹配 {pattern})")
                oauth_ready = True
                break
            except Exception:
                continue
        if not oauth_ready:
            print(f"  当前 URL: {page.url}（未跳转到已知 OAuth 域名，继续尝试）")

        await asyncio.sleep(3)

        # Step 4: 填写登录表单
        print("\nStep 4: 填写登录表单...")
        print(f"  页面标题: {await page.title()}")
        print(f"  最终 URL: {page.url}")

        # 邮箱输入框
        email_selectors = [
            "input[type='email']", "input[name='email']", "input[id='email']",
            "input[placeholder*='email' i]", "input[autocomplete='email']",
            "input[name='username']",
        ]
        email_filled = False
        for sel in email_selectors:
            try:
                await page.wait_for_selector(sel, timeout=8000)
                await page.fill(sel, email)
                print(f"  ✅ 邮箱已填写 (selector: {sel})")
                email_filled = True
                break
            except Exception:
                continue
        if not email_filled:
            inputs = await page.query_selector_all("input")
            print("  🔍 当前页面 input 元素列表：")
            for inp in inputs[:10]:
                name = await inp.get_attribute("name")
                inp_type = await inp.get_attribute("type")
                print(f"      <input name='{name}' type='{inp_type}'>")
            raise Exception("❌ 找不到邮箱输入框，登录失败")

        # 密码输入框
        password_selectors = [
            "input[type='password']", "input[name='password']", "input[id='password']",
            "input[name='passwd']",
        ]
        password_filled = False
        for sel in password_selectors:
            try:
                await page.fill(sel, password)
                print(f"  ✅ 密码已填写 (selector: {sel})")
                password_filled = True
                break
            except Exception:
                continue
        if not password_filled:
            raise Exception("❌ 找不到密码输入框，登录失败")
        await asyncio.sleep(0.5)

        # Step 5: 提交登录表单
        print("\nStep 5: 提交登录表单...")
        submit_selectors = [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Login')", "button:has-text('Sign in')",
            "button:has-text('Continue')", "button:has-text('Log in')",
            "button:has-text('登录')",
        ]
        submitted = await click_first_match(page, submit_selectors, timeout=5000)
        if not submitted:
            print("  ⚠️ 未找到提交按钮，尝试 Enter 键提交...")
            await page.keyboard.press("Enter")

        # Step 6: 等待回到 Searcade
        print("\nStep 6: 等待 OAuth 回调，返回 Searcade...")
        try:
            await page.wait_for_url(f"**/{SEARCADE_DOMAIN}/**", timeout=20000)
            print(f"  ✅ 已回调到: {page.url}")
        except Exception:
            print(f"  ⚠️ 等待超时，当前 URL: {page.url}")
        await asyncio.sleep(2)

        # Step 7: 截图 & 验证登录状态
        print("\n📸 登录后截图...")
        await page.goto(SEARCADE_HOME, wait_until="networkidle", timeout=20000)
        await take_screenshot(page, "after_login.png")
        await print_cookies(context, "登录后")

        is_logged_in = False
        logged_in_indicators = [
            "a[href*='logout']", "a[href*='signout']", "button:has-text('Logout')",
            ".user-menu", ".account", "[data-user]", ".avatar",
        ]
        for sel in logged_in_indicators:
            try:
                await page.wait_for_selector(sel, timeout=3000)
                print(f"  ✅ 检测到已登录标志: {sel}")
                is_logged_in = True
                break
            except Exception:
                continue

        # Step 8: 尝试访问 Admin 后台
        print("\nStep 8: 尝试访问 Admin 后台...")
        admin_found = False
        for path in ADMIN_PATHS:
            url = f"https://{SEARCADE_DOMAIN}{path}"
            await page.goto(url, wait_until="networkidle", timeout=15000)
            status_text = await page.title()
            final_url = page.url
            print(f"  {path} → {final_url} (title: {status_text})")
            if "404" not in status_text and "not found" not in status_text.lower():
                print(f"  ✅ Admin 页面可能可访问: {final_url}")
                await take_screenshot(page, "after_login_admin.png")
                admin_found = True
                break
        if not admin_found:
            await take_screenshot(page, "after_login_admin.png")

        # 最终结果
        print("\n" + "═" * 50)
        if is_logged_in:
            print("✅ 登录成功！用户已认证")
        elif admin_found:
            print("✅ 登录成功！已访问到 Admin 页面")
        else:
            print("⚠️ 登录状态不明确，请查看截图确认")
            if "login" in page.url.lower():
                raise Exception("❌ 登录失败，仍在登录页面")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
