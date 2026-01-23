import asyncio
import base64
import json
import re
import os
from click import prompt
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

def simplify_accessibility_tree(node):
    if not node:
        return None
    
    simplified = {
        "role": node.get("role"),
        "name": node.get("name"),
    }
    if node.get("description"):
        simplified["description"] = node.get("description")

    if "children" in node:
        children = [simplify_accessibility_tree(c) for c in node["children"]]
        children = [c for c in children if c and (c.get("name") or c.get("children"))]
        if children:
            simplified["children"] = children

    return simplified

async def main():
    async with async_playwright() as p:
        # Launch Browser 
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        print("Navigating to Google...")
        await page.goto("https://www.google.com", wait_until="networkidle")
        
        # --- Core Step : Base64 Pipeline ---
        # A. Take Screenshot & Encode to Base64 string
        screenshot_bytes = await page.screenshot()
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # B. Capturing Accessibility Tree via CDP
        print("Capturing Accessibility Tree via CDP...")
        try:
            # Create a CDP (Chrome DevTools Protocol) session
            cdp_client = await page.context.new_cdp_session(page)
            
            # Call the underlying protocol directly to get the full accessibility tree.
            # getFullAXTree returns a list of semantic nodes for the entire page（flattened）.
            accessibility_data = await cdp_client.send("Accessibility.getFullAXTree")
            raw_tree = {"children": accessibility_data.get("nodes", [])}
            
        except Exception as e:
            print(f"CDP Capture failed: {e}")
            raw_tree = {}
        # print(raw_tree)
        simplified_tree = simplify_accessibility_tree(raw_tree)
        # print(simplified_tree)
        tree_json_str = json.dumps(simplified_tree, ensure_ascii=False, indent=2)
        # print(tree_json_str)

        # C. Send to Doubao Vision Model
        print("Requesting AI reasoning (Vision + Semantic)...")
        prompt = f"""
        You are an expert Web Automation Agent.
        Your task is to find the center coordinates(x, y) of the 'Google Sreach' button.

        CONTEXT:
        - Below is the simplified Accessibility Tree of the current page.
        - You are also provided with a screentshot of the page.

        ACCESSIBILITY TREE:
        {tree_json_str}

        INSTRUCTIONS:
        1. Use the Accessibility Tree to identify the semantic role and name of the target.
        2. Cross-reference with the screenshot to determine the precise pixel coordinates.
        3. Respond ONLY with a valid JSON object:{{"x":interger, "y":interget}}.
        4. Do not include any explanation or additional text.
        """

        # Trigger the "Chat Completion" API to request a model response
        response = client.chat.completions.create(
            # endpoint_id: The specific model deployment ID (e.g., Doubao/Ark endpoint in ByteDance)
            model=endpoint_id, 
            
            # messages: The conversational context. LLMs process tasks by predicting the next tokens in a dialogue.
            messages=[
                {
                    # role: "user" defines this as an instruction coming from the end-user
                    "role": "user",
                    
                    # content: A multimodal list containing both text instructions and image data
                    "content": [
                        {
                            "type": "text", 
                            # The Prompt: This is the core instruction for the AI.
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            # Image Injection: Passing the Playwright screenshot via the Base64 pipeline.
                            # The AI performs "Spatial Reasoning" on these pixels to calculate the [x, y] position.
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            
            # temperature: Controls the randomness of the output.
            # 0 = "Deterministic": The model always chooses the token with the highest probability.
            # In QA automation, this must be 0 to ensure test results are stable and reproducible.
            temperature=0  
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