# Tkinter gui to activate certain parts of PyAutoRaid

import tkinter as tk
from tkinter import ttk
from tkinter import *
import sqlite3 as sql
import pathlib


dir = str(pathlib.Path().absolute())
# from SQL_test import SQL
connection = sql.connect(dir + "/Settings.db")

cursor = connection.cursor()

command1 = """CREATE TABLE IF NOT EXISTS
    PyAutoRaid(user_id INTEGER PRIMARY KEY, auto_cb TEXT, auto_ca TEXT, auto_tta TEXT, auto_r TEXT, blackout_monitor TEXT)"""

cursor.execute(command1)

###################################################
# The setup of the tkinter window and tabs
root = Tk()
root.title("PyAutoRaid Settings")
tab_control = ttk.Notebook(root)
tab1 = ttk.Frame(tab_control)
tab2 = ttk.Frame(tab_control)
tab3 = ttk.Frame(tab_control)
tab4 = ttk.Frame(tab_control)
tab5 = ttk.Frame(tab_control)
tab_control.add(tab1, text="Auto Rewards")
tab_control.add(tab2, text="Clan Boss")
tab_control.add(tab3, text="Classic Arena")
tab_control.add(tab4, text="Tag Team Arena")
tab_control.add(tab5, text="Other Settings")

#####################################################
# Get what all the radiobuttons are set as and submit to settings.db
def submission():
    var1.get()
    var2.get()
    var3.get()
    var4.get()
    var5.get()
    cursor.execute(
        "INSERT OR REPLACE INTO PyAutoRaid (user_id,auto_cb, auto_ca, auto_tta, auto_r, blackout_monitor) VALUES (1,'{}', '{}', '{}','{}', '{}')".format(
            var1.get(),
            var2.get(),
            var3.get(),
            var4.get(),
            var5.get(),
        )
    )
    # Read and set 'results' to be equal to current settings from setting.db
    cursor.execute("SELECT * FROM PyAutoRaid")

    results = cursor.fetchall()
    connection.commit()

    print(results)
    return results


####################
# Set the radiobuttons to have the value it was last set on from results variable from settings.db
cursor.execute("SELECT * FROM PyAutoRaid")

results = cursor.fetchall()
connection.commit()


var1 = tk.BooleanVar(value=results[0][1])
var2 = tk.BooleanVar(value=results[0][2])
var3 = tk.BooleanVar(value=results[0][3])
var4 = tk.BooleanVar(value=results[0][4])
var5 = tk.BooleanVar(value=results[0][5])

###########################
def AutoReward():
    if var1.get() == False:
        print("False")
        return "False"

    elif var1.get() == True:
        print("True")
        return "True"


def AutoClanBoss():
    if var2.get() == False:
        print("False")
        return "False"
    elif var2.get() == True:
        print("True")
        return "True"


def AutoClassicArena():
    if var3.get() == False:
        print("False")
        return "False"
    elif var3.get() == True:
        print("True")
        return "True"


def AutoTagTeamArena():
    if var4.get() == False:
        print("False")
        return "False"
    elif var4.get() == True:
        print("True")
        return "True"


def BlackOutMonitors():
    if var5.get() == False:
        print("False")
        return "False"
    elif var5.get() == True:
        print("True")
        return "True"


#################################
# The actual tkinter window widgets
def gui():

    tab_control.pack(expand=1, fill="both")

    ttk.Checkbutton(
        tab1,
        text="Activate AutoRewards?",
        variable=var1,
        offvalue=False,
        onvalue=True,
        command=AutoReward,
    ).grid(column=0, row=0, padx=30, pady=30)
    ttk.Checkbutton(
        tab2,
        text="Activate Auto Clan Boss?",
        variable=var2,
        offvalue=False,
        onvalue=True,
        command=AutoClanBoss,
    ).grid(column=0, row=0, padx=30, pady=30)
    ttk.Checkbutton(
        tab3,
        text="Activate Auto Classic Arena?",
        variable=var3,
        offvalue=False,
        onvalue=True,
        command=AutoClassicArena,
    ).grid(column=0, row=0, padx=30, pady=30)
    ttk.Checkbutton(
        tab4,
        text="Activate Auto Tag Team Arena?",
        variable=var4,
        offvalue=False,
        onvalue=True,
        command=AutoTagTeamArena,
    ).grid(column=0, row=0, padx=30, pady=30)
    ttk.Checkbutton(
        tab5,
        text="Activate Blackout Screen After?",
        variable=var5,
        offvalue=False,
        onvalue=True,
        command=BlackOutMonitors,
    ).grid(column=0, row=0, padx=30, pady=30)

    ttk.Button(tab1, text="SUBMIT", command=submission).grid(
        column=0, row=1, padx=30, pady=30
    )
    ttk.Button(tab2, text="SUBMIT", command=submission).grid(
        column=0, row=1, padx=30, pady=30
    )
    ttk.Button(tab3, text="SUBMIT", command=submission).grid(
        column=0, row=1, padx=30, pady=30
    )
    ttk.Button(tab4, text="SUBMIT", command=submission).grid(
        column=0, row=1, padx=30, pady=30
    )
    ttk.Button(tab5, text="SUBMIT", command=submission).grid(
        column=0, row=1, padx=30, pady=30
    )
    # ttk.Button(tab1, text="Restart PyAutoRaid", command=Main.main).grid(
    #     column=1, row=1, padx=30, pady=30
    # )
    # ttk.Button(tab2, text="Restart PyAutoRaid", command=Main.main).grid(
    #     column=1, row=1, padx=30, pady=30
    # )
    # ttk.Button(tab3, text="Restart PyAutoRaid", command=Main.main).grid(
    #     column=1, row=1, padx=30, pady=30
    # )
    # ttk.Button(tab4, text="Restart PyAutoRaid", command=Main.main).grid(
    #     column=1, row=1, padx=30, pady=30
    # )
    # ttk.Button(tab5, text="Restart PyAutoRaid", command=Main.main).grid(
    #     column=1, row=1, padx=30, pady=30
    # )

    root.mainloop()


if __name__ == "__main__":
    gui()
