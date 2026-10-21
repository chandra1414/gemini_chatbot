import os
import sys
import time

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
key = os.getenv("GOOGLE_API_KEY")
model = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.8-flash"

if not key:
    print("No GOOGLE_API_KEY found in .env")
    sys.exit(1)

print(f"Testing model: {model} ...")
start = time.time()
try:
    llm = ChatGoogleGenerativeAI(
        model=model, google_api_key=key, timeout=30, max_retries=1
    )
    resp = llm.invoke("Say hello in one short sentence.")
    print("REPLY:", resp.content)
    print(f"Time taken: {time.time() - start:.1f}s")
except Exception as e:
    print("ERROR:", e)