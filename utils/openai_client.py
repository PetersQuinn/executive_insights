import os
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Azure-specific config
endpoint = os.getenv("ENDPOINT_URL", "https://ppiproj-resource.services.ai.azure.com/api/projects/ppiproj")
deployment = os.getenv("DEPLOYMENT_NAME", "o4-mini")
subscription_key = os.getenv("AZURE_OPENAI_API_KEY", "REPLACE_WITH_YOUR_KEY_VALUE_HERE")
api_version = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")

# Initialize Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=subscription_key,
    api_version=api_version,
)

def ask_gpt(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=100000 # adjust if needed
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Azure GPT ERROR] {e}" #test
