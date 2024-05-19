import re
import sys
import requests

# Get the latest release from the GitHub API
repo = "SnoopLawg/PyAutoRaid"
url = f"https://api.github.com/repos/{repo}/releases/latest"
response = requests.get(url)
data = response.json()
latest_version = data['tag_name']

# Extract the numeric part of the version and increment it
match = re.match(r'v(\d+\.\d+)-beta', latest_version)
if not match:
    print("Invalid version format")
    sys.exit(1)

version = match.group(1)
major, minor = map(int, version.split('.'))
minor += 1

# Generate the new version
new_version = f"v{major}.{minor}-beta"
print(new_version)
