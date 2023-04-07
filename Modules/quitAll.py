# quit all python processes
import time
import os

# from Modules.BlackOutMonitor import BlackOutMonitor
import pygetwindow
import psutil


def check_process_exists(process_name):
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == process_name:
            return True
    return False


print(check_process_exists("Raid.exe"))


def quitAll():
    # time.sleep(5)
    print()
    # os.system("taskkill /f /im RSLHelper.exe")
    # os.system("taskkill /f /im  Raid.exe")
    # os.system("taskkill /f /im PlariumPlay.exe")
    # time.sleep(3)

    print()

    all_windows = pygetwindow.getAllTitles()
    if check_process_exists("RSLHelper.exe") == True:
        print("RSLHelper open. Shutting down.")
        os.system("taskkill /f /im Main.exe")
        os.system("taskkill /f /im PyAutoRaid.exe")
        os.system("taskkill /f /im python.exe")
        os.system("taskkill /f /im main.py")
        os.system("taskkill /f /im PlariumPlay.exe")
        time.sleep(1)

    elif check_process_exists("Raid.exe") == True:
        os.system("taskkill /f /im Raid.exe")
        os.system("taskkill /f /im PlariumPlay.exe")
        os.system("taskkill /f /im Main.exe")
        os.system("taskkill /f /im PyAutoRaid.exe")
        os.system("taskkill /f /im python.exe")
        os.system("taskkill /f /im main.py")


if __name__ == "__main__":
    quitAll()
