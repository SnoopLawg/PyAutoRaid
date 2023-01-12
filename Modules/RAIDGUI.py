# Tkinter gui to activate certain parts of PyAutoRaid

import tkinter as tk
from tkinter import ttk
from tkinter import *
import sqlite3 as sql
import pathlib
import os

DIR = os.getcwd()
ASSETS_PATH = os.path.join(DIR, "assets")
DB_PATH = os.path.join(DIR, "Data", "Settings.db")

connection = sql.connect(DB_PATH)
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
    ###################################################

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


if len(results) > 0:
    var1 = tk.BooleanVar(value=results[0][1])
    var2 = tk.BooleanVar(value=results[0][2])
    var3 = tk.BooleanVar(value=results[0][3])
    var4 = tk.BooleanVar(value=results[0][4])
    var5 = tk.BooleanVar(value=results[0][5])
else:
    var1 = tk.BooleanVar(value=True)
    var2 = tk.BooleanVar(value=True)
    var3 = tk.BooleanVar(value=True)
    var4 = tk.BooleanVar(value=True)
    var5 = tk.BooleanVar(value=True)

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


##################################
def quit_everything():
    os.system("taskkill /f /im RSLHelper.exe")
    os.system("taskkill /f /im  Raid.exe")
    os.system("taskkill /f /im PlariumPlay.exe")
    os.system("taskkill /f /im Main.exe")
    os.system("taskkill /f /im python.exe")
    os.system("taskkill /f /im PyAutoRaid Settings.exe")


#################################
def restart():
    import Main

    os.system("taskkill /f /im RSLHelper.exe")
    os.system("taskkill /f /im  Raid.exe")
    os.system("taskkill /f /im PlariumPlay.exe")
    os.system("taskkill /f /im Main.exe")
    Main.main()


# The actual tkinter window widgets
def gui():

    tab_control.pack(expand=1, fill="both")

    def create_tab(tab, command, text):
        ttk.Checkbutton(
            tab,
            text=text,
            variable=var1,
            offvalue=False,
            onvalue=True,
            command=command,
        ).grid(column=0, row=0, padx=30, pady=30)
        ttk.Button(tab, text="SUBMIT", command=submission).grid(
            column=0, row=1, padx=30, pady=30
        )
        ttk.Button(tab, text="Restart PyAutoRaid", command=restart).grid(
            column=1, row=1, padx=30, pady=30
        )
        ttk.Button(tab, text="Quit All", command=quit_everything).grid(
            column=2, row=1, padx=30, pady=30
        )

    create_tab(tab1, AutoReward, "Activate Auto Rewards?")
    create_tab(tab2, AutoClanBoss, "Activate Clan Boss?")
    create_tab(tab3, AutoClassicArena, "Activate Classic Arenas?")
    create_tab(tab4, AutoTagTeamArena, "Activate Tag Team Arena?")
    create_tab(tab5, BlackOutMonitors, "Activate Black Out your Monitor after?")

    root.mainloop()


if __name__ == "__main__":
    gui()
