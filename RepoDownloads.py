import requests
import re

# Replace with your GitHub repository details
owner = 'SnoopLawg'
repo = 'PyAutoRaid'

# GitHub API URL to get all releases
url = f'https://api.github.com/repos/{owner}/{repo}/releases'

response = requests.get(url)

if response.status_code == 200:
    releases = response.json()
    total_downloads = sum(asset['download_count'] for release in releases for asset in release['assets'])

    with open('README.md', 'r') as file:
        readme = file.read()

    # Update the README.md with the total downloads count
    new_readme = re.sub(r'Total downloads: \d+', f'Total downloads: {total_downloads}', readme)

    with open('README.md', 'w') as file:
        file.write(new_readme)
else:
    print(f'Failed to fetch releases: {response.status_code}')
