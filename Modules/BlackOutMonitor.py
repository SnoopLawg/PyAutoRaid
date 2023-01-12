# Black out the monitor in the end. Put it to sleep so ya boy can sleep
import sys
import time
import sqlite3 as sql
import pathlib
import os

DIR = os.getcwd()
DB_PATH = os.path.join(DIR, "Data", "Settings.db")
ASSETS_PATH = os.path.join(DIR, "assets")
connection = sql.connect(DB_PATH)
cursor = connection.cursor()


def BlackOutMonitor():
    cursor.execute("SELECT * FROM PyAutoRaid")
    results = cursor.fetchall()
    connection.commit()
    Run = results
    Run = Run[0][5]
    if Run == "True":
        time.sleep(2)
        if sys.platform.startswith("linux"):
            import os

            os.system("xset dpms force off")

        elif sys.platform.startswith("win"):
            import win32gui
            import win32con

            SC_MONITORPOWER = 0xF170
            win32gui.SendMessageTimeout(
                win32con.HWND_BROADCAST,
                win32con.WM_SYSCOMMAND,
                SC_MONITORPOWER,
                2,
                win32con.SMTO_NOTIMEOUTIFNOTHUNG,
                1000,
            )

        elif sys.platform.startswith("darwin"):
            import subprocess

            subprocess.call(
                "echo 'tell application \"Finder\" to sleep' | osascript", shell=True
            )


if __name__ == "__main__":
    BlackOutMonitor()
