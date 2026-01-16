import asyncio
import base64
import json
import re
import os
from playwright.async_api import async_playwright
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.environ.get("ARK_API_KEY")
endpoint_id = os.environ.get("ARK_ENDPOINT_ID")

if not api_key or not endpoint_id:
    print("Environment variables missing: Please check ARK_API_KEY and ARK_ENDPOINT_ID")
    exit()

# 1. Configure Doubao Client 
client = OpenAI(
    api_key=api_key,
    base_url="https://ark.cn-beijing.volces.com/api/v3"
)

async def main():
    async with async_playwright() as p:
        # Launch Browser 
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        print("Navigating to Google...")
        await page.goto("https://www.google.com", wait_until="networkidle")
        
        # --- Core Step : Base64 Pipeline ---
        # A. Take Screenshot
        screenshot_bytes = await page.screenshot()
        
        # B. Encode to Base64 string
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # C. Send to Doubao Vision Model
        print("Requesting AI vision analysis...")
        response = client.chat.completions.create(
            model=endpoint_id, 
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze the image and find the center coordinates of the 'Google Search' button. Return the result strictly in JSON format:{\"x\":interger, \"y\":interger.Do not include any other text.}"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            temperature=0  # Set to 0 for deterministic output
        )
        
        # D. Parse coordinates and perform click 
        res_text = response.choices[0].message.content
        print(f"Model Response: {res_text}")
        
        # Extract JSON using Regex(in case the model adds extra conversation)
        match = re.search(r'\{.*\}', res_text)
        if match:
            try:
                coords = json.loads(match.group())
                target_x = coords['x']
                target_y = coords['y']
                print(f"AI decided to click coordinates: {target_x}, {target_y}")
                await page.mouse.click(target_x, target_y)
            except json.JSONDecodeError:
                print("Error: Could not parse JSON from AI response.")
        else:
            print("Error: No valid coordinates found in the response.")

        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())