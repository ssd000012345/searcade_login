import os
import asyncio
from playwright.async_api import async_playwright

# 正确导入 stealth（推荐方式）
from playwright_stealth import stealth_async

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            locale='zh-CN'
        )
        
        page = await context.new_page()
        
        # 应用 stealth 伪装
        await stealth_async(page)

        try:
            print("正在访问首页...")
            await page.goto("https://searcade.com/en/", wait_until="domcontentloaded", timeout=60000)
            await page.screenshot(path="before_login.png")

            print("点击登录按钮...")
            await page.click("text=Login", timeout=15000)
            
            email = os.environ.get("SEARCADE_EMAIL")
            password = os.environ.get("SEARCADE_PASSWORD")

            print("填写邮箱...")
            await page.wait_for_selector('input[type="email"]', timeout=15000)
            await page.fill('input[type="email"]', email)
            await page.click("text=Continue with email")

            print("填写密码...")
            await page.wait_for_selector('input[type="password"]', timeout=15000)
            await page.fill('input[type="password"]', password)
            await page.click("button:has-text('Log in')")

            print("等待登录跳转...")
            await page.wait_for_url("**/admin**", timeout=30000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(5)

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
