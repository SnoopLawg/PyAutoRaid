# Run all of the raid functions.
from Modules.PyAutoRaid_Configure_Settings import PyAutoRaid_Configure_Settings
from Modules.CBauto import ClanBoss
from Modules.AutoRewards import AutoRewards
from Modules.BlackOutMonitor import BlackOutMonitor
from Modules.ClassicArena import ClassicArena
from Modules.OpenRaid import openRaid
from Modules.quitAll import quitAll
import sqlite3 as sql
from Modules.TagTeamArena import TagTeamArena
import sys,pyautogui,multiprocessing,time,os,pathlib,sys
from datetime import datetime
from multiprocessing import Process
from Modules.RAIDGUI import gui
from Modules.CheckFilesExist import Check_files_exist, Check_os
from Modules.PushNotifications import push
from Modules.Logger import *
####################################################################

if getattr(sys, "frozen", False):
    # we are running in a bundle
    DIR = sys._MEIPASS
    setting=os.getcwd()
else:
    # we are running in a normal Python environment
    DIR = os.getcwd()
    setting=os.getcwd()

ASSETS_PATH = os.path.join(DIR, "assets")
DB_PATH = os.path.join(setting, "Settings.db")

####################################################################

connection = sql.connect(DB_PATH)
cursor = connection.cursor()

####################################################################
#Timing started. Set max run time just in case.
results = []
start_time = time.time()
max_running_time = (1500)  # 25 minutes in seconds so that the file doesnt run for too long.


DIR = str(pathlib.Path().absolute())

####################################################################

def main():
    Erase_Log()
    push("Started")
    Log_start("PyAutoRaid")
    Log_info()

    # wake up pc
    pyautogui.click(0, 5)

    PyAutoRaid_Configure_Settings("reset")
    # commit the changes to the database
    connection.commit()

    Check_files_exist()
    # Opening Raid
    try:
        results.append(openRaid())
    except TypeError:
        Throw_log_error(f"{TypeError} -- Open Raid")
        openRaid()
    except IndexError:
        Throw_log_error(f"{IndexError} -- Open Raid")
        openRaid()

    # AutoReward Collection
    AutoRewards()

    # CLAN BOSS
    results.append(ClanBoss())

    # ClassicArena fights
    try:
        results.append(ClassicArena())
    except TypeError:
        Throw_log_error(f"{TypeError} -- Classic Arena")
        pass

    # TagTeamArena fights
    try:
        results.append(TagTeamArena())
    except TypeError:
        Throw_log_error(f"{TypeError} -- Tag Team Arena")
        TagTeamArena()
    # Remove Nne in Notificarti
    try:
        results.remove(None)
    except:
        pass
    push("Finishing", results)
    time.sleep(1)
    command = f"UPDATE PyAutoRaid_Configure SET finished='done' WHERE user_id=1"
    cursor.execute(command)

    # commit the changes to the database
    connection.commit()

    BlackOutMonitor()
    Log_finish(f"PyAutoRaid -- Finished Successfully, {results}")
    quitAll()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    p = multiprocessing.Process(target=main, name="main")
    g = multiprocessing.Process(target=gui, name="PyAutoRaidGui")
    # p2 = multiprocessing.Process(target=main, name="main")
    # g2 = multiprocessing.Process(target=gui, name="PyAutoRaidGui")
    p.start()
    time.sleep(5)
    g.start()
    DIR = os.getcwd()
    DB_PATH = os.path.join(DIR, "Settings.db")
    connection = sql.connect(DB_PATH)
    cursor = connection.cursor()
    count = 0
    time.sleep(30)
    while True:
        count += 1
        if count == 1:
            time.sleep(4)
        if (
            pyautogui.locateOnScreen(ASSETS_PATH + "\\CBcrashed.png", confidence=0.8)
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\CBcrashed.png", confidence=0.8
                )
                != None
            ):
                push("Crashed", results)
                quitAll()
                os.system("taskkill /f /im Main.exe")

        if (
            pyautogui.locateOnScreen(ASSETS_PATH + "\\CBcrashed2.png", confidence=0.8)
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(ASSETS_PATH + "CBcrashed.png", confidence=0.8)
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
            time.sleep(30)
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
                # p2.terminate()
                # g2.terminate()
                # Cleanup
                p.join()
                g.join()
                # p2.join()
                # g2.join()
                Log_finish("PyAutoRaid")
                quitAll()
                exit()
            except:
                Throw_log_error("did not finish properly")
                quitAll()
                exit()