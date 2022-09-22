# Check if all the py files were downloaded

from ast import Global
import os.path
from platform import platform
import tkinter
from tkinter import messagebox
import platform
import pyautogui
import pathlib


def CheckFilesExist():
    Needed_Files = [
        "TimeBetween.py",
        "AutoRewards.py",
        "BlackOutMonitor.py",
        "CBauto.py",
        "CheckFilesExist.py",
        "ClassicArena.py",
        "log.txt",
        "LoopFindImage.py",
        "Main.py",
        "NightMareAttemptText.py",
        "OpenRaid.py",
        "quitAll.py",
    ]
    Total_files = 0
    for file in Needed_Files:
        operating = CheckOS()
        dir = str(pathlib.Path().absolute())
        if operating == "Windows":
            filepath = dir + "\\" + file
        elif operating == "Darwin":
            filepath = dir + "/" + file
        file_exists = os.path.exists(filepath)
        if file_exists == True:
            print("Have", file)
            Total_files += 1
        elif file_exists == False:
            print("Dont have", file)
    missing = int(11 - Total_files)
    if Total_files == len(Needed_Files) - 1:
        print(Total_files, "files were downloaded")
    else:
        print("All 11 files were not downloaded. Only", Total_files, "were")
        tkinter.messagebox.showerror(
            title="ALL FILES NOT DOWNLOADED", message="You have missing files"
        )
        exit()


def CheckOS():
    operating = platform.system()
    if operating == "Darwin":
        return operating
    elif operating == "Windows":
        # pyautogui.hotkey('winleft', 'm')
        return operating
    else:
        print("I have no idea what OS this is")
        exit()


if __name__ == "__main__":
    CheckOS()
    CheckFilesExist()
