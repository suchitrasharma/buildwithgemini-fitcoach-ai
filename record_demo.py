import asyncio
import os
from playwright.async_api import async_playwright

ARTIFACT_DIR = "/config/.gemini/antigravity/brain/08d2929c-d1d5-4ee0-85a0-9038a785abd7"
APP_URL = "https://fitcoach-frontend-216397559854.us-east1.run.app"

async def record_demo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=ARTIFACT_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print("1. Navigating to FitCoach AI frontend...")
        await page.goto(APP_URL, wait_until="networkidle")
        await asyncio.sleep(3)

        print("2. Triggering Prompt 1 (Exercise Catalog Lookup)...")
        await page.fill("#input", "List exercises for chest")
        await page.click("button.send-btn")

        print("Waiting for response 1...")
        # Wait for agent bubble to contain content other than placeholder '…'
        await page.wait_for_selector(".msg.agent .bubble:not(:has-text('…'))", timeout=45000)
        await asyncio.sleep(5)

        print("3. Triggering Prompt 2 (Richer 1RM Strength Calculation & Badge Generation)...")
        await page.fill("#input", "Calculate my 1RM for 200 lbs at 5 reps and generate a 50 workouts milestone badge")
        await asyncio.sleep(1)
        await page.click("button.send-btn")

        print("Waiting for response 2...")
        # Wait for second agent bubble to finish rendering
        await page.wait_for_selector(".msg.agent:nth-of-type(4) .bubble:not(:has-text('…'))", timeout=60000)
        await asyncio.sleep(6)

        print("Closing browser context to save video...")
        video = page.video
        await context.close()
        await browser.close()

        if video:
            video_path = await video.path()
            print(f"Video saved to: {video_path}")

            target_path = os.path.join(ARTIFACT_DIR, "fitcoach_demo.webm")
            os.rename(video_path, target_path)
            print(f"Renamed video to: {target_path}")

if __name__ == "__main__":
    asyncio.run(record_demo())
