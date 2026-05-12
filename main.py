import os
import asyncio
from curl_cffi.requests import AsyncSession
from urllib.parse import urlencode, urlparse, parse_qs
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def take_screenshot(url: str, path: str, cookies: dict = None):
    """使用 Playwright 对指定 URL 截图"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        # 注入 cookies
        if cookies:
            cookie_list = []
            for name, value in cookies.items():
                cookie_list.append({
                    "name": name,
                    "value": value,
                    "domain": urlparse(url).netloc,
                    "path": "/",
                })
            await context.add_cookies(cookie_list)

        page = await context.new_page()
        await stealth_async(page)
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            await page.screenshot(path=path, full_page=True)
            print(f"  📸 截图已保存: {path}")
        except Exception as e:
            print(f"  ⚠️ 截图失败: {e}")
        finally:
            await browser.close()


async def run():
    email = os.environ.get("SEARCADE_EMAIL")
    password = os.environ.get("SEARCADE_PASSWORD")

    if not email or not password:
        raise ValueError("未设置 SEARCADE_EMAIL 或 SEARCADE_PASSWORD")

    oauth_params = {
        "client_id": "8305d2e2-e91f-4deb-8909-f669259bc23f",
        "redirect_uri": "https://searcade.com/accounts/userveria/login/callback/",
        "scope": "profile",
        "response_type": "code",
    }

    async with AsyncSession(impersonate="chrome124") as session:

        # ── 登录前截图 ──────────────────────────────────────────
        print("📸 登录前截图...")
        await take_screenshot("https://searcade.com/en/", "before_login.png")

        print("\nStep 1: 访问 searcade 首页建立 Cookie...")
        r0 = await session.get("https://searcade.com/en/")
        print(f"  状态码: {r0.status_code}")
        print(f"  Cookies: {dict(session.cookies)}")

        print("\nStep 2: 访问 OAuth 授权页获取 state...")
        authorize_url = f"https://userveria.com/authorize/?{urlencode(oauth_params)}"
        r1 = await session.get(authorize_url)
        print(f"  状态码: {r1.status_code}")
        print(f"  最终 URL: {r1.url}")
        print(f"  响应片段: {r1.text[:300]}")

        state = parse_qs(urlparse(str(r1.url)).query).get("state", [None])[0]
        print(f"  State: {state}")

        if r1.status_code == 403:
            print("  ❌ 仍被 Cloudflare 拦截，等待后重试...")
            await asyncio.sleep(5)
            r1 = await session.get(authorize_url)
            print(f"  重试状态码: {r1.status_code}")
            state = parse_qs(urlparse(str(r1.url)).query).get("state", [None])[0]

        print("\nStep 3: 获取 userveria payload...")
        payload_url = "https://userveria.com/authorize/_payload.json"
        r_payload = await session.get(payload_url)
        print(f"  Payload 状态码: {r_payload.status_code}")
        if r_payload.status_code == 200:
            print(f"  Payload: {r_payload.text[:500]}")

        print("\nStep 4: 登录 userveria...")
        login_headers = {
            "Content-Type": "application/json",
            "Origin": "https://userveria.com",
            "Referer": authorize_url,
        }
        login_data = {
            "email": email,
            "password": password,
        }

        endpoints = [
            "https://userveria.com/api/auth/login",
            "https://userveria.com/api/auth/email",
            "https://userveria.com/api/login",
            "https://userveria.com/auth/login",
        ]

        login_success = False
        for endpoint in endpoints:
            print(f"\n  尝试端点: {endpoint}")
            r_login = await session.post(
                endpoint,
                json=login_data,
                headers=login_headers,
            )
            print(f"  状态码: {r_login.status_code}")
            print(f"  响应: {r_login.text[:300]}")
            if r_login.status_code in (200, 201):
                login_success = True
                print(f"  ✅ 登录端点找到: {endpoint}")
                break

        print("\nStep 5: 完成 OAuth 授权并回调...")
        if state:
            r_auth = await session.post(
                "https://userveria.com/api/authorize",
                json={"state": state, **oauth_params},
                headers=login_headers,
            )
            print(f"  授权状态码: {r_auth.status_code}")
            print(f"  授权响应: {r_auth.text[:300]}")

            try:
                auth_data = r_auth.json()
                if "redirect_uri" in auth_data or "code" in auth_data:
                    code = auth_data.get("code", "")
                    callback_url = (
                        f"https://searcade.com/accounts/userveria/login/callback/"
                        f"?code={code}&state={state}"
                    )
                    print(f"\n  回调 URL: {callback_url}")
                    r_callback = await session.get(callback_url)
                    print(f"  回调状态码: {r_callback.status_code}")
                    print(f"  回调最终 URL: {r_callback.url}")
            except Exception as e:
                print(f"  解析授权响应失败: {e}")

        print("\nStep 6: 验证登录状态...")
        r_check = await session.get("https://searcade.com/en/admin/")
        print(f"  状态码: {r_check.status_code}")
        print(f"  最终 URL: {r_check.url}")
        searcade_cookies = {
            k: v for k, v in session.cookies.items()
            if "searcade" in k or "session" in k.lower() or "csrf" in k.lower()
        }
        print(f"  关键 Cookies: {searcade_cookies}")

        final_url = str(r_check.url)

        # ── 登录后截图（注入 session cookies）──────────────────
        print("\n📸 登录后截图...")
        all_cookies = dict(session.cookies)
        await take_screenshot(
            "https://searcade.com/en/",
            "after_login.png",
            cookies=all_cookies,
        )

        # 尝试直接截 admin 页面
        await take_screenshot(
            "https://searcade.com/en/admin/",
            "after_login_admin.png",
            cookies=all_cookies,
        )

        # ── 登录结果判断 ────────────────────────────────────────
        if "/admin" in final_url and r_check.status_code == 200:
            print("\n✅ 登录成功！已进入 Admin 后台")
        elif "login" in final_url or r_check.status_code in (401, 403):
            print("\n❌ 登录失败，被重定向到登录页面")
            raise Exception("登录失败")
        elif r_check.status_code == 404:
            print("\n⚠️ Admin 路径 404，尝试其他路径...")
            for admin_path in [
                "/admin/",
                "/en/admin/",
                "/dashboard/",
                "/en/dashboard/",
            ]:
                r_try = await session.get(f"https://searcade.com{admin_path}")
                print(f"  {admin_path}: {r_try.status_code} -> {r_try.url}")
        else:
            print(f"\n⚠️ 未知状态: {r_check.status_code} at {r_check.url}")


if __name__ == "__main__":
    asyncio.run(run())
