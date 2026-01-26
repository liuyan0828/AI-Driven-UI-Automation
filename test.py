import asyncio
import base64
import json
import re
import os
from playwright.async_api import async_playwright
from openai import OpenAI
from dotenv import load_dotenv
from typing import Literal, Optional
from pydantic import BaseModel, Field

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

class WebAction(BaseModel):
    """
    Schema for the AI Agent's decision-making process.
    This model enforces structured output for the LLM, ensuring that the reasoning is captured and the actions are type-safe.
    """
    # --- Reasoning Layer ---
    thought: str = Field(description="Internal reasoning: Why this action is chosen based on the goals.")
    # --- Action Selection Layer ---
    action_type: Literal["click", "type", "scroll", "wait", "finish"] = Field(description="The next atomic action to perform.")
    # --- Parameter Layer ---
    x:Optional[int] = Field(None, description="The X coordinate for click actions.")
    y:Optional[int] = Field(None, description="The Y coordinate for click actions.")
    text:Optional[str] = Field(None, description="The text content for 'type' action.")


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
        You are an expert Web Automation Agent.Analyze the Accessibility Tree and Screenshot.
        Goal: Click the 'Google Search' button.

        ACCESSIBILITY TREE:
        {tree_json_str}

        OUTPUT INSTRUCTIONS:
        Your output must be a JSON object with the following EXACT keys:
        1. "thought": A brief explanation of why you are taking this action.
        2. "action_type": Must be one of ["click", "type", "scroll", "wait", "finish"].
        3. "x": (Integer) The X coordinate for clicking.
        4. "y": (Integer) The Y coordinate for clicking.
        5. "text": (String) Only for "type" actions.

        Example:
        {{
        "thought": "I found the search button in the center-bottom of the screen.",
        "action_type": "click",
        "x": 640,
        "y": 450
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
        
        # D. Parse coordinates and perform click 
        res_content = response.choices[0].message.content
        try:
            # Pydantic handles the validation and conversion into a Python object.
            action = WebAction.model_validate_json(res_content)

            print(f"AI THOUGHT: {action.thought}")
            print(f"AI ACTION: {action.action_type}")

            if action.action_type == "click":
                print(f"Executing click at ({action.x}, {action.y})")
                await page.mouse.click(action.x, action.y)
            elif action.action_type == "type":
                print(f"Typing: {action.text}")
                await page.keyboard.type(action.text)

        except Exception as e:
            print(f"Reasoning Parse Error: {e}\nRaw Response: {res_content}")

        
        await asyncio.sleep(3)
        await browser.close()

asyncio.run(main())