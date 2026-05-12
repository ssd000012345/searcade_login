import os
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth   # 修正：去掉 _async

async def run():
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=True) 
        
        # 模拟真实浏览器环境
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        page = await context.new_page()

        # 使用 stealth 抹除特征（仍然是异步调用）
        await stealth(page)

        # 1. 访问首页
        print("正在访问首页...")
        try:
            await page.goto("https://searcade.com/en/", wait_until="networkidle", timeout=60000)
            await page.screenshot(path="before_login.png")

            # 2. 点击登录
            print("点击登录按钮...")
            await page.click("text=Login")
            
            # 3. 填写账号密码
            email = os.environ.get("SEARCADE_EMAIL")
            password = os.environ.get("SEARCADE_PASSWORD")

            await page.wait_for_selector('input[type="email"]', timeout=30000)
            await page.fill('input[type="email"]', email)
            await page.click("text=Continue with email")
            
            await page.wait_for_selector('input[type="password"]', timeout=30000)
            await page.fill('input[type="password"]', password)
            await page.click("button:has-text('Log in')")

            # 4. 等待跳转回管理后台
            print("等待登录跳转...")
            await page.wait_for_url("**/admin**", timeout=30000)
            await page.wait_for_load_state("networkidle")
            
            # 额外等待确保页面加载完全
            await asyncio.sleep(5) 
            await page.screenshot(path="after_login.png")
            print("登录成功！")

        except Exception as e:
            print(f"发生错误: {e}")
            await page.screenshot(path="error_state.png")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
