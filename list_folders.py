import requests
from msal import PublicClientApplication

# === CONFIG ===
CLIENT_ID = "81a52509-4aa7-4060-ad96-4859d35701ba"
TENANT_ID = "b96cc57b-d146-48f5-a381-7cf474c23a9e"
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
