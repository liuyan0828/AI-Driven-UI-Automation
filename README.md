# AI-Driven UI Automation Agent 🤖

This project implements an intelligent, autonomous web agent designed to navigate and interact with web applications. Moving beyond traditional, fragile CSS/XPath selectors, this agent uses a **Multimodal Reasoning** approach to achieve more robust UI automation.

## 🌟 Key Features
- **Multimodal Perception**: Combines visual screenshots with semantic data to "understand" the page like a human.
- **Accessibility Tree Integration (via CDP)**: Utilizes the **Chrome DevTools Protocol (CDP)** to capture the page's semantic skeleton, providing a logic-based "source of truth" that bypasses redundant DOM structures.
- **Intelligent Coordinate Calculation**: The AI reasons over the image pixels and semantic nodes to return precise $(x, y)$ coordinates for interaction, ensuring high stability even when the UI changes.
- **Recursive Tree Simplification**: Includes a custom Python utility to prune the Accessibility Tree, reducing noise and optimizing API token consumption by over 80%.

## 🛠 Tech Stack
- **Language**: Python 3.x
- **Automation**: [Playwright](https://playwright.dev/python/)
- **AI Engine**: Doubao Vision Model (via Ark API) / OpenAI Multimodal API
- **Protocol**: Chrome DevTools Protocol (CDP)

## 🚀 How to Run
1. Clone the repo
2. `pip install -r requirements.txt`
3. Add your `ARK_API_KEY` to `.env`
4. `python test.py`
