import os
import pathlib
import platform
import tkinter
from tkinter import messagebox, filedialog


def Check_files_exist():
    needed_files = [
        "TimeBetween.py",
        "AutoRewards.py",
        "BlackOutMonitor.py",
        "CBauto.py",
        "CheckFilesExist.py",
        "ClassicArena.py",
        "LoopFindImage.py",
        "NightMareAttemptText.py",
        "OpenRaid.py",
        "quitAll.py",
        "Raid.exe",
    ]
    total_files = 0
    for file in needed_files:
        operating_system = Check_os()
        current_dir = str(pathlib.Path().absolute())
        if operating_system == "Windows":
            filepath = f"{current_dir}\\Modules\\{file}"
        elif operating_system == "Darwin":
            filepath = f"{current_dir}/{file}"
        if os.path.exists(filepath):
            print(f"Found {file}")
            total_files += 1
        elif file == "Raid.exe":
            if operating_system == "Windows":
                default_install_path = f"C:\\Users\\{os.getlogin()}\\AppData\\Local\\PlariumPlay\\StandAloneApps\\raid\\34744\\Raid.exe"
                filepath = default_install_path
                if not os.path.exists(filepath):
                    tkinter.messagebox.showerror(
                        "Error",
                        "You do not have Raid downloaded. Please select the file path of your Raid.exe.",
                    )
                    filepath = filedialog.askopenfilename(
                        initialdir="C:\\",
                        title="Select Raid.exe",
                        filetypes=(("Executable files", "*.exe"), ("all files", "*.*")),
                    )
                    if not os.path.exists(filepath):
                        tkinter.messagebox.showerror(
                            "Error", "Invalid file path. Please try again."
                        )
                        Check_files_exist()
                total_files += 1
        else:
            print(f"Missing {file}")
    if total_files >= len(needed_files) - 1:
        print(f"{total_files} files were found.")
    else:
        print(f"Not all {len(needed_files)} files were found. Only {total_files} were.")
        tkinter.messagebox.showerror("Error", "Some files are missing.")
    return filepath


def Check_os():
    operating_system = platform.system()
    if operating_system in ["Darwin", "Windows"]:
        return operating_system
    else:
        print("I have no idea what OS this is")
        exit()


if __name__ == "__main__":
    Check_os()
    Check_files_exist()
