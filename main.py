import os
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth  # 正确导入

# ── 常量 ────────────────────────────────────────────────────────────
SEARCADE_HOME      = "https://searcade.com/en/"
USERVERIA_PATTERNS = ["userveria.com", "searcade.userveria.com"]  # 支持主域和子域
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

# ── 辅助：打印 cookies ──────────────────────────────────────────────
async def print_cookies(context, label: str):
    cookies = await context.cookies()
    searcade_cookies = [c for c in cookies if SEARCADE_DOMAIN in c["domain"]]
    print(f"  [{label}] Searcade Cookies ({len(searcade_cookies)} 个):")
    for c in searcade_cookies:
        print(f"    {c['name']} = {c['value'][:60]}")

# ── 辅助：截图 ───────────────────────────────────────────────────────
async def take_screenshot(page, path: str):
    try:
        await page.screenshot(path=path, full_page=True)
        print(f"  📸 截图已保存: {path}")
    except Exception as e:
        print(f"  ⚠️ 截图失败: {e}")

# ── 辅助：等待并点击元素（多选择器尝试）────────────────────────────
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

# ── 辅助：开始录屏（仅在调试时启用）────────────────────────────────
async def start_video_recording(context, file_name: str):
    try:
        await context.start_video_recording()  # 注：此方法在 context 上调用，会在 close 时自动保存
        print(f"  🎥 开始录屏: {file_name}")
    except Exception as e:
        print(f"  ⚠️ 录屏启动失败: {e}")

async def stop_and_save_video(context, page, path: str):
    try:
        # 等待几秒让页面稳定
        await asyncio.sleep(2)
        await context.close()  # 关闭 context 会自动保存视频
        # 注意：context.close() 会同时关闭页面，需要确保之前已完成所有操作
        # 实际项目中建议不同的方式：记录视频路径，最后手动保存
        print(f"  🎥 录屏已保存: {path}")
    except Exception as e:
        print(f"  ⚠️ 保存录屏失败: {e}")

# ── 主流程 ───────────────────────────────────────────────────────────
async def run():
    email    = os.environ.get("SEARCADE_EMAIL")
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
            record_video_dir="videos"  # 录屏保存目录（若不需要可注释）
        )
        page = await context.new_page()
        await stealth(page)  # 修正！

        # 可选：启动录屏（如果不需要，可注释整块）
        # await start_video_recording(context, "login_recording.webm")

        # ══════════════════════════════════════════════════
        # Step 1: 访问首页
        # ══════════════════════════════════════════════════
        print("\n📸 登录前截图...")
        print("Step 1: 访问 Searcade 首页...")
        await page.goto(SEARCADE_HOME, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)
        await take_screenshot(page, "before_login.png")
        print(f"  当前 URL: {page.url}")

        # ══════════════════════════════════════════════════
        # Step 2: 点击登录按钮
        # ══════════════════════════════════════════════════
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

        # ══════════════════════════════════════════════════
        # Step 3: 等待 OAuth 页面加载（支持子域名）
        # ══════════════════════════════════════════════════
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

        # 等待页面稳定，处理可能的 Cloudflare 挑战
        await asyncio.sleep(3)

        # ══════════════════════════════════════════════════
        # Step 4: 填写邮箱和密码（增强选择器）
        # ══════════════════════════════════════════════════
        print("\nStep 4: 填写登录表单...")

        # 首先打印页面标题和当前 URL 帮助调试
        print(f"  页面标题: {await page.title()}")
        print(f"  最终 URL: {page.url}")

        # 邮箱输入框选择器（更全面）
        email_selectors = [
            "input[type='email']",
            "input[name='email']",
            "input[id='email']",
            "input[placeholder*='email' i]",
            "input[autocomplete='email']",
            "input[name='username']",      # 有些 OAuth 系统用 username 字段
            "input[placeholder*='用户名']",
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
            # 调试：将当前页面的所有 input 打印出来
            inputs = await page.query_selector_all("input")
            print("  🔍 当前页面 input 元素列表：")
            for inp in inputs[:10]:  # 只显示前10个避免过多日志
                name = await inp.get_attribute("name")
                inp_type = await inp.get_attribute("type")
                print(f"      <input name='{name}' type='{inp_type}'>")
            raise Exception("❌ 找不到邮箱输入框，登录失败")

        # 密码输入框
        password_selectors = [
            "input[type='password']",
            "input[name='password']",
            "input[id='password']",
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

        # ══════════════════════════════════════════════════
        # Step 5: 提交表单
        # ══════════════════════════════════════════════════
        print("\nStep 5: 提交登录表单...")
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Login')",
            "button:has-text('Sign in')",
            "button:has-text('Continue')",
            "button:has-text('Log in')",
            "button:has-text('登录')",
        ]
        submitted = await click_first_match(page, submit_selectors, timeout=5000)
        if not submitted:
            print("  ⚠️ 未找到提交按钮，尝试 Enter 键提交...")
            await page.keyboard.press("Enter")

        # ══════════════════════════════════════════════════
        # Step 6: 等待回到 Searcade
        # ══════════════════════════════════════════════════
        print("\nStep 6: 等待 OAuth 回调，返回 Searcade...")
        try:
            await page.wait_for_url(f"**/{SEARCADE_DOMAIN}/**", timeout=20000)
            print(f"  ✅ 已回调到: {page.url}")
        except Exception:
            print(f"  ⚠️ 等待超时，当前 URL: {page.url}")

        await asyncio.sleep(2)

        # ══════════════════════════════════════════════════
        # Step 7: 截图 & 验证登录状态
        # ══════════════════════════════════════════════════
        print("\n📸 登录后截图...")
        await page.goto(SEARCADE_HOME, wait_until="networkidle", timeout=20000)
        await take_screenshot(page, "after_login.png")
        await print_cookies(context, "登录后")

        # 检查登录标志
        is_logged_in = False
        logged_in_indicators = [
            "a[href*='logout']",
            "a[href*='signout']",
            "button:has-text('Logout')",
            ".user-menu",
            ".account",
            "[data-user]",
            ".avatar",
        ]
        for sel in logged_in_indicators:
            try:
                await page.wait_for_selector(sel, timeout=3000)
                print(f"  ✅ 检测到已登录标志: {sel}")
                is_logged_in = True
                break
            except Exception:
                continue

        # ══════════════════════════════════════════════════
        # Step 8: 尝试访问 Admin 后台
        # ══════════════════════════════════════════════════
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

        # ══════════════════════════════════════════════════
        # 最终结果
        # ══════════════════════════════════════════════════
        print("\n" + "═" * 50)
        if is_logged_in:
            print("✅ 登录成功！用户已认证")
        elif admin_found:
            print("✅ 登录成功！已访问到 Admin 页面")
        else:
            print("⚠️ 登录状态不明确，请查看截图确认")
            if "login" in page.url.lower():
                raise Exception("❌ 登录失败，仍在登录页面")

        # 关闭浏览器前，保存录屏（如果启用了 record_video_dir）
        # 注意：录屏文件会在 browser.close() 时自动保存到 record_video_dir
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
