import asyncio
import base64
import json
import re
import os
from playwright.async_api import async_playwright
from openai import OpenAI
from dotenv import load_dotenv

from models import WebAction
from recorder import ActionRecorder
from utils import simplify_accessibility_tree, get_img_hash

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

async def get_ai_decision(page, tree_json):
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
        # 在 get_ai_decision 中
        max_tree_length = 20000  # 设置一个合理的 Token 安全阈值
        if len(tree_json_str) > max_tree_length:
            tree_json_str = tree_json_str[:max_tree_length] + "... [Tree truncated for token limit]"
        # print(tree_json_str)

        # C. Send to Doubao Vision Model
        print("Requesting AI reasoning (Vision + Semantic)...")
        prompt = f"""
            You are an expert Web Automation Agent. Analyze the Accessibility Tree and Screenshot.
            Goal: Search for 'playwright' on DuckDuckGo.

            INSTRUCTIONS:
            1. Identify the search input box.
            2. We will type 'playwright' and submit via the Enter key.
            3. If you are already on the search results page (URL contains 'q=playwright'), return action_type: "finish".
            4. Otherwise, return action_type: "type", and text: "playwright".

            ACCESSIBILITY TREE:
            {tree_json_str}

            OUTPUT INSTRUCTIONS:
            Your output must be a JSON object with these EXACT keys:
            1. "thought": Explain your reasoning.
            2. "action_type": Use "type" to perform the search or "finish" if done.
            3. "text": Must be "playwright" (only for "type" action).

            Example:
            {{
            "thought": "I will type 'playwright' into the search box to initiate the search.",
            "action_type": "type",
            "text": "playwright"
            }}
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
            response_format={"type": "json_object"},
            # temperature: Controls the randomness of the output.
            # 0 = "Deterministic": The model always chooses the token with the highest probability.
            # In QA automation, this must be 0 to ensure test results are stable and reproducible.
            temperature=0  
        )
        
        res_raw = response.choices[0].message.content
        return WebAction.model_validate_json(res_raw), screenshot_bytes, prompt, res_raw

async def main():
    async with async_playwright() as p:
        # Launch Browser 
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        recorder = ActionRecorder()
        
        print("Navigating to duckduckgo...")
        await page.goto("https://duckduckgo.com/", wait_until="domcontentloaded")

        # --- PHASE 4: Action Loop with Self-healing ---
        for step in range(1, 4):
            print(f"\n>>> Executing Step {step}")
            
            # 1. 自愈循环：尝试执行，如果页面没动就重试
            max_retries = 3
            success = False
            
            for attempt in range(max_retries):
                before_url = page.url
                # A. 动作前获取状态
                cdp = await page.context.new_cdp_session(page)
                ax_tree = await cdp.send("Accessibility.getFullAXTree")
                tree_str = json.dumps(simplify_accessibility_tree({"children": ax_tree.get("nodes", [])}))
                
                # B. 获取 AI 决策
                action, before_bytes, p_text, r_json = await get_ai_decision(page, tree_str)
                before_hash = get_img_hash(before_bytes)

                if action.action_type == "finish" or "q=" in page.url:
                    print("Task finished: Navigation to search results confirmed.")

                # C. 执行动作
                print(f"AI Thought: {action.thought}")
                if action.action_type == "type_and_click" or action.action_type == "type":
                    print(f"Action: Typing '{action.text}' and pressing Enter ... ")
                    await page.keyboard.type(action.text, delay=100)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    print("Enter pressed for form submission.")
                
                await asyncio.sleep(3) # 等待页面反应
                
                # D. 自愈校验：比较截图哈希
                after_bytes = await page.screenshot()

                if page.url != before_url:
                    print(f"Success! Navigation detected: {page.url}")
                    recorder.record_step(step, before_bytes, after_bytes, p_text, r_json)
                    break
                else:
                    print(f"Attempt {attempt+1} failed: UI not changed. Retrying...")

            if not success:
                print("Task aborted: Persistent UI unresponsiveness.")
                break
            if action.action_type == "finish": break
    
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())