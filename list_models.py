
import os

import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GOOGLE_API_KEY")

r = requests.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    params={"key": key, "pageSize": 100},
    timeout=30,
)
data = r.json()

if "models" not in data:
    print("ERROR:", r.text)
else:
    print("Models available for your key (that can generate text):\n")
    for m in data["models"]:
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print(m["name"].replace("models/", ""))