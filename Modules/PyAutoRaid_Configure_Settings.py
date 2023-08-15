import os
import sqlite3 as sql
import pygetwindow
import time
import datetime
from Modules.Logger import *

def PyAutoRaid_Configure_Settings(cbBattle=None):
    import sys

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

    connection = sql.connect(DB_PATH)
    cursor = connection.cursor()
    
    ####################################################################
    command1 = """CREATE TABLE IF NOT EXISTS
        PyAutoRaid_Configure  (user_id INTEGER PRIMARY KEY, finished TEXT, directory_path TEXT, settingsdb_path TEXT, assets_path TEXT)"""
    cursor.execute(command1)

    # insert some data into the tables
    cursor.execute(
        "INSERT OR REPLACE INTO PyAutoRaid_Configure VALUES (1,'{}', '{}', '{}','{}')".format(
            "not_done", DIR, DB_PATH, ASSETS_PATH
        )
    )
    connection.commit()
    # join the tables and select data
    ###################################################################################
    # Drop table if it exists
    today_utc_ = datetime.datetime.utcnow()

    # use timedelta to subtract one day
    # yesterday = today_utc_ - datetime.timedelta(days=1)
    today_utc = today_utc_.strftime("%m/%d/%Y/%H")
    Current_day = today_utc_.strftime("%m/%d/%Y")
    # yesterday_utc = yesterday.strftime("%m/%d/%Y/%H")
    Reset_time = today_utc_.strftime("%m/%d/%Y") + "/10"

    command2 = command2 = """CREATE TABLE IF NOT EXISTS PyAutoRaid_DailyCompleted(
                user_id INTEGER PRIMARY KEY,
                current_day INTEGER,
                Easy INTEGER,
                Normal INTEGER,
                Hard INTEGER,
                Brutal INTEGER,
                Nightmare INTEGER,
                UltraNightmare INTEGER,
                Easy_set INTEGER,
                Normal_set INTEGER,
                Hard_set INTEGER,
                Brutal_set INTEGER,
                Nightmare_set INTEGER,
                UltraNightmare_set INTEGER
            )"""
    cursor.execute(command2)
    try:
        # insert some data into the tables
        cursor.execute(
            "INSERT INTO PyAutoRaid_DailyCompleted VALUES (1,'{}', '{}', '{}','{}','{}','{}','{}', '{}', '{}','{}','{}','{}','{}')".format(
                today_utc_, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            )
        )
        connection.commit()
    except:
        pass
    # join the tables and select data
    ClanBosses = ["Easy", "Normal", "Hard", "Brutal", "Nightmare", "UltraNightmare"]
    for battle in ClanBosses:
        if cbBattle == "reset":
            if today_utc[10:] == Reset_time[10:]:
                Log_start("Reset recorded battles for the day in settings")
                cursor.execute(
                    "UPDATE PyAutoRaid_DailyCompleted SET current_day = ?,Easy = ?, Normal = ?, Hard = ?, Brutal = ?, Nightmare = ?, UltraNightmare = ? WHERE user_id = 1",
                    (Current_day, 0, 0, 0, 0, 0, 0),
                )
                connection.commit()
                from Modules.PushNotifications import push
                Log_finish(", all battles Reset")
                push("RESETTING CLAN BOSS")
        if battle == cbBattle:
            if cbBattle != "reset":
                cursor.execute(f"SELECT {cbBattle} FROM PyAutoRaid_DailyCompleted")
                battles = cursor.fetchone()[0]
                added_battle = int(battles) + 1
                command = f"UPDATE PyAutoRaid_DailyCompleted SET {cbBattle}='{added_battle}' WHERE user_id=1"
                cursor.execute(command)
                # commit the changes to the database
                connection.commit()
    cursor.execute(f"SELECT * FROM PyAutoRaid_DailyCompleted")
    total_battles = cursor.fetchall()[0][2:8]
    sumof = 0
    for i in total_battles:
        sumof += int(i)
    print(sumof)


if __name__ == "__main__":
    PyAutoRaid_Configure_Settings()
