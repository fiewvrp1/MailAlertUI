import os
import requests
from msal import PublicClientApplication
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
CLIENT_ID = os.environ["CLIENT_ID"]
TENANT_ID = os.environ["TENANT_ID"]
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Read"]

# === AUTH ===
app = PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
result = app.acquire_token_interactive(scopes=SCOPES)
access_token = result['access_token']

# === CALL Graph & Loop through all pages ===
url = "https://graph.microsoft.com/v1.0/me/mailFolders"
headers = {'Authorization': f'Bearer {access_token}'}

print("✅ Your mail folders (All pages):")

while url:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    for folder in data['value']:
        print(f"📂 {folder['displayName']} -> {folder['id']}")

    url = data.get('@odata.nextLink')
