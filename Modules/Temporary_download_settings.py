import os
import requests
#using this file to temporarily download the settings from github because PyAutoRaid_Configure.py is not creatign the .db when an exe file
def temp_settings():
    url = "https://raw.githubusercontent.com/SnoopLawg/PyAutoRaid/main/Settings.db"
    filename = "Settings.db"
    current_folder=os.getcwd()
    settings_path=os.path.join(current_folder,filename)
    if not os.path.exists(settings_path):
        response = requests.get(url)
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"{filename} has been downloaded.")
    else:
        print(f"{filename} already exists.")

if __name__ == "__main__":
    temp_settings()