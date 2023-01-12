import sqlite3 as sql
import pathlib
import time
import multiprocessing
from Modules.RAIDGUI import (
    gui,
    AutoClanBoss,
    AutoReward,
    AutoTagTeamArena,
    AutoClassicArena,
    BlackOutMonitors,
)

dir = str(pathlib.Path().absolute())


def SQL(results=[]):

    # AutoReward1 = AutoReward()
    # AutoClanBoss1 = AutoClanBoss
    # AutoClassicArena1 = AutoClassicArena
    # AutoTagTeamArena1 = AutoTagTeamArena
    # BlackOutMonitors1 = BlackOutMonitors

    connection = sql.connect(dir + "/Settings.db")

    cursor = connection.cursor()

    command1 = """CREATE TABLE IF NOT EXISTS
    PyAutoRaid(user_id INTEGER PRIMARY KEY, auto_cb TEXT, auto_ca TEXT, auto_tta TEXT, auto_r TEXT, blackout_monitor TEXT)"""

    cursor.execute(command1)

    # cursor.execute(
    #     "INSERT OR REPLACE INTO PyAutoRaid (user_id,auto_cb, auto_ca, auto_tta, auto_r, blackout_monitor) VALUES (1,'True', 'True', 'True','True', 'True')",
    # )

    cursor.execute(
        "INSERT OR REPLACE INTO PyAutoRaid (user_id,auto_cb, auto_ca, auto_tta, auto_r, blackout_monitor) VALUES (1,'{}', '{}', '{}','{}', '{}')".format(
            AutoReward(),
            "Truee",
            "Truee",
            "Truee",
            "Truee",
        )
    )

    cursor.execute("SELECT * FROM PyAutoRaid")

    results = cursor.fetchall()
    connection.commit()

    print(results)
    return results


if __name__ == "__main__":
    # gui()
    # g = multiprocessing.Process(target=gui, name="PyAutoRaidGui")
    # g.start()
    SQL()
