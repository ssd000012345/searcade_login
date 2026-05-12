import os
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run():
    async with async_playwright() as p:
        # 使用 Stealth 上下文管理器（推荐方式）
        async with Stealth().use_async(p) as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            
            page = await context.new_page()

            try:
                print("正在访问首页...")
                await page.goto("https://searcade.com/en/", wait_until="domcontentloaded", timeout=60000)
                await page.screenshot(path="before_login.png")

                print("点击登录按钮...")
                await page.click("text=Login", timeout=20000)

                email = os.environ.get("SEARCADE_EMAIL")
                password = os.environ.get("SEARCADE_PASSWORD")

                print("填写邮箱...")
                await page.wait_for_selector('input[type="email"]', timeout=15000)
                await page.fill('input[type="email"]', email)
                await page.click("text=Continue with email")

                print("填写密码并登录...")
                await page.wait_for_selector('input[type="password"]', timeout=15000)
                await page.fill('input[type="password"]', password)
                await page.click("button:has-text('Log in')")

                print("等待跳转到管理后台...")
                await page.wait_for_url("**/admin**", timeout=30000)
                await asyncio.sleep(6)

                await page.screenshot(path="after_login.png")
                print("✅ 登录成功！")

            except Exception as e:
                print(f"❌ 发生错误: {e}")
                await page.screenshot(path="error_state.png")
                import traceback
                traceback.print_exc()

            finally:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
