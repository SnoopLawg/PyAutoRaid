# Run all of the raid functions.
from Modules.PyAutoRaid_Configure import PyAutoRaid_Configure
from Modules.CBauto import ClanBoss
from Modules.AutoRewards import AutoRewards
from Modules.BlackOutMonitor import BlackOutMonitor
from Modules.ClassicArena import ClassicArena
from Modules.OpenRaid import openRaid
from Modules.quitAll import quitAll
from Modules.NightmareAttemptText import NightmareAttemptText
import sqlite3 as sql
from Modules.TagTeamArena import TagTeamArena
from Modules.TimeBetween import is_time_between
import sys
import pyautogui
import multiprocessing
from datetime import datetime
import time
from multiprocessing import Process
import os
from Modules.RAIDGUI import gui
import pathlib
from Modules.CheckFilesExist import Check_files_exist, Check_os
import time
from Modules.PushNotifications import push

DIR = os.getcwd()
DB_PATH = os.path.join(DIR, "Settings.db")
# update the 'finished' column of a specific row
connection = sql.connect(DB_PATH)
cursor = connection.cursor()

results = []
start_time = time.time()
max_running_time = (
    1500  # 25 minutes in seconds so that the file doesnt run for too long.
)
DIR = str(pathlib.Path().absolute())


def main():
    push("Started")
    # wake up pc
    pyautogui.click(0, 5)

    PyAutoRaid_Configure("reset")
    # commit the changes to the database
    connection.commit()

    Check_files_exist()

    Check_os()

    # Opening Raid
    try:
        results.append(openRaid())
    except TypeError:
        print(TypeError)
        openRaid()
    except IndexError:
        print(IndexError)
        openRaid()

    # AutoReward Collection
    AutoRewards()

    # CLAN BOSS
    results.append(ClanBoss())

    # ClassicArena fights
    try:
        results.append(ClassicArena())
    except TypeError:
        print(TypeError)
        pass

    # TagTeamArena fights
    try:
        results.append(TagTeamArena())
    except TypeError:
        print(TypeError)
        TagTeamArena()
    # Remove Nne in Notificarti
    results.remove(None)
    push("Finishing", results)
    time.sleep(1)
    command = f"UPDATE PyAutoRaid_Configure SET finished='done' WHERE user_id=1"
    cursor.execute(command)

    # commit the changes to the database
    connection.commit()

    BlackOutMonitor()
    quitAll()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    p = multiprocessing.Process(target=main, name="main")
    g = multiprocessing.Process(target=gui, name="PyAutoRaidGui")
    p2 = multiprocessing.Process(target=main, name="main")
    g2 = multiprocessing.Process(target=gui, name="PyAutoRaidGui")
    p.start()

    g.start()
    DIR = os.getcwd()
    DB_PATH = os.path.join(DIR, "Settings.db")
    connection = sql.connect(DB_PATH)
    cursor = connection.cursor()
    count = 0
    while True:
        count += 1
        if count == 1:
            time.sleep(4)
        if (
            pyautogui.locateOnScreen(DIR + "\\assets\\CBcrashed.png", confidence=0.8)
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(
                    DIR + "\\assets\\CBcrashed.png", confidence=0.8
                )
                != None
            ):
                push("Crashed", results)
                quitAll()
                os.system("taskkill /f /im Main.exe")

        if (
            pyautogui.locateOnScreen(DIR + "\\assets\\CBcrashed2.png", confidence=0.8)
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(
                    DIR + "\\assets\\CBcrashed.png", confidence=0.8
                )
                != None
            ):
                push("Crashed", results)
                quitAll()
                os.system("taskkill /f /im Main.exe")
                # os.system("taskkill /f /im python.exe")
                # p2.start()
                # g2.start()
        current_time = time.time()
        if connection:
            command2 = "SELECT finished FROM PyAutoRaid_Configure"
            cursor.execute(command2)
            PARCresults = cursor.fetchall()
            # print(PARCresults[0][0])
            end = PARCresults[0][0]
        else:
            print("no connection")
        if current_time - start_time > max_running_time or end == "done":
            Total_time = current_time - start_time
            time.sleep(10)
            # connection.close()
            # Terminate
            push("Cancelling", results, Total_time)
            time.sleep(1)
            try:
                p.terminate()
                g.terminate()
                p2.terminate()
                g2.terminate()
                # Cleanup
                p.join()
                g.join()
                p2.join()
                g2.join()
                quitAll()
                exit()
            except:
                print("fail")
                quitAll()
                exit()
