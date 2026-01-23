# AI-Driven UI Automation Agent 🤖

A lightweight MVP for self-healing UI testing using **Playwright** and **Multimodal LLM (Vision)**.

## 🌟 Key Features
- **Visual Interaction**: Operates browsers through visual recognition instead of fragile DOM selectors (XPath/CSS).
- **Base64 Pipeline**: Efficiently pipes real-time screenshots to LLM Vision APIs.
- **Deterministic Output**: Leverages low-temperature completions for stable coordinate extraction.

## 🛠 Tech Stack
- **Engine**: Playwright (Python)
- **Brain**: Doubao Vision Model / GPT-4o
- **Protocol**: Base64 Encoding / JSON Completion

## 🚀 How to Run
1. Clone the repo
2. `pip install -r requirements.txt`
3. Add your `ARK_API_KEY` to `.env`
4. `python test.py`
