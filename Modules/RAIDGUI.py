# Tkinter gui to activate certain parts of PyAutoRaid

import tkinter as tk
from tkinter import ttk
from tkinter import *
import sqlite3 as sql
import pathlib
import os
from tkinter import messagebox
from ttkthemes import ThemedTk

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


command1 = """CREATE TABLE IF NOT EXISTS
    PyAutoRaid(user_id INTEGER PRIMARY KEY, auto_cb TEXT, auto_ca TEXT, auto_tta TEXT, auto_r TEXT, blackout_monitor TEXT)"""

cursor.execute(command1)
##

###################################################
# The setup of the tkinter window and tabs
root = ThemedTk(theme="equilux")
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
#Check Toggle of Modules
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
    # define spinboxes

    def create_tab(tab, var, command, text):
        ttk.Checkbutton(
            tab,
            text=text,
            variable=var,
            offvalue=False,
            onvalue=True,
            command=command,
        ).grid(column=0, row=0, padx=30, pady=30)
        ttk.Button(tab, text="SUBMIT", command=submission).grid(
            column=0, row=1, padx=30, pady=30
        )
        # ttk.Button(tab, text="Restart PyAutoRaid", command=restart).grid(
        #     column=1, row=1, padx=30, pady=30
        # )
        ttk.Button(tab, text="Quit All", command=quit_everything).grid(
            column=2, row=1, padx=30, pady=30
        )

    def clanbosslevels(text, varr):
        label = ttk.Label(
            tab2,
            textvariable=varr,
        )

        ttk.Button(tab2, text="SUBMIT", command=submission).grid(
            column=0, row=1, padx=30, pady=30
        )
        # ttk.Button(tab2, text="Restart PyAutoRaid", command=restart).grid(
        #     column=1, row=1, padx=30, pady=30
        # )
        ttk.Button(tab2, text="Quit All", command=quit_everything).grid(
            column=2, row=1, padx=30, pady=30
        )

        return label

    cursor.execute(f"SELECT * FROM PyAutoRaid_DailyCompleted")
    total_battles = cursor.fetchall()[0][8:]

    spin1 = tk.Spinbox(tab2, from_=0, to=10)
    spin1.delete(0, "end")  # clear any default value
    spin1.insert(0, total_battles[0])  # set initial value

    spin2 = tk.Spinbox(tab2, from_=0, to=10)
    spin2.delete(0, "end")  # clear any default value
    spin2.insert(0, total_battles[1])  # set initial value

    spin3 = tk.Spinbox(tab2, from_=0, to=10)
    spin3.delete(0, "end")  # clear any default value
    spin3.insert(0, total_battles[2])  # set initial value

    spin4 = tk.Spinbox(tab2, from_=0, to=10)
    spin4.delete(0, "end")  # clear any default value
    spin4.insert(0, total_battles[3])  # set initial value

    spin5 = tk.Spinbox(tab2, from_=0, to=10)
    spin5.delete(0, "end")  # clear any default value
    spin5.insert(0, total_battles[4])  # set initial value

    spin6 = tk.Spinbox(tab2, from_=0, to=10)
    spin6.delete(0, "end")  # clear any default value
    spin6.insert(0, total_battles[5])  # set initial value

    easy_label = clanbosslevels(text="Easy:", varr=spin1)
    normal_label = clanbosslevels(text="Normal:", varr=spin2)
    hard_label = clanbosslevels(text="Hard:", varr=spin3)
    brutal_label = clanbosslevels(text="Brutal:", varr=spin4)
    nightmare_label = clanbosslevels(text="Nightmare:", varr=spin5)
    ultranightmare_label = clanbosslevels(text="UltraNightmare:", varr=spin6)

    # create spinboxes for the inputs
    ttk.Label(tab2, text="Easy: ").grid(row=2, column=0, padx=20)
    spin1.grid(row=2, column=1)
    easy_label.grid(row=2, column=0, sticky="w", pady=5)
    ttk.Label(tab2, text="Normal: ").grid(row=3, column=0, padx=20)
    spin2.grid(row=3, column=1)
    normal_label.grid(row=3, column=0, sticky="w", pady=5)
    ttk.Label(tab2, text="Hard: ").grid(row=4, column=0, padx=20)
    spin3.grid(row=4, column=1)
    hard_label.grid(row=4, column=0, sticky="w", pady=5)
    ttk.Label(tab2, text="Brutal: ").grid(row=5, column=0, padx=20)
    spin4.grid(row=5, column=1)
    brutal_label.grid(row=5, column=0, sticky="w", pady=5)
    ttk.Label(tab2, text="Nightmare: ").grid(row=6, column=0, padx=20)
    spin5.grid(row=6, column=1)
    nightmare_label.grid(row=6, column=0, sticky="w", pady=5)
    ttk.Label(tab2, text="UltraNightmare: ").grid(row=7, column=0, padx=20)
    spin6.grid(row=7, column=1)
    ultranightmare_label.grid(row=7, column=0, sticky="w", pady=5)

    def calculate_sum():
        # get the values of spinboxes and calculate their sum
        easy = int(spin1.get())
        normal = int(spin2.get())
        hard = int(spin3.get())
        brutal = int(spin4.get())
        nightmare = int(spin5.get())
        ultra_nightmare = int(spin6.get())
        total_sum = easy + normal + hard + brutal + nightmare + ultra_nightmare

        # check if the sum is greater than 4 and show a message box
        if total_sum > 4:
            tk.messagebox.showerror(
                "Warning",
                "Most accounts only have 4 keys in a day. If you mark more than four fights total, you must have the extra keys for the other fights. If you do not, the extra battles will not be fought. (Example: I mark 4 UNM and 2 NM. Only the first 4 UNM will be fought as their are only 4 keys generated in a day. Battles are prioritized descending from UNM --> Easy.) ",
            )
        else:
            tk.messagebox.showinfo("Result", f"The sum of inputs is {total_sum}.")

        # get the values of spinboxes and calculate their sum
        easy = int(spin1.get())
        normal = int(spin2.get())
        hard = int(spin3.get())
        brutal = int(spin4.get())
        nightmare = int(spin5.get())
        ultra_nightmare = int(spin6.get())

        print(easy, normal, hard, brutal, nightmare, ultra_nightmare)

        # insert some data into the tables
        table_name = "PyAutoRaid_DailyCompleted"
        sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                user_id INTEGER PRIMARY KEY,
                Easy_set INTEGER,
                Normal_set INTEGER,
                Hard_set INTEGER,
                Brutal_set INTEGER,
                Nightmare_set INTEGER,
                UltraNightmare_set INTEGER
            );
            """

        cursor.execute(sql)

        cursor.execute(
            "UPDATE PyAutoRaid_DailyCompleted SET Easy_set = ?, Normal_set = ?, Hard_set = ?, Brutal_set = ?, Nightmare_set = ?, UltraNightmare_set = ? WHERE user_id = 1",
            (easy, normal, hard, brutal, nightmare, ultra_nightmare),
        )
        
        connection.commit()


    ttk.Label(tab2, text="Set fight amounts and then click the button below").grid(
        row=4, column=2, padx=20
    )
    # create a button to calculate the sum of inputs
    ttk.Button(
        tab2,
        text="Set Number of Fights",
        command=calculate_sum,
    ).grid(row=6, column=2, padx=30)

    create_tab(tab1, var1, AutoReward, "Activate Auto Rewards?")
    create_tab(tab2, var2, AutoClanBoss, "Activate Clan Boss?")

    create_tab(tab3, var3, AutoClassicArena, "Activate Classic Arenas?")
    create_tab(tab4, var4, AutoTagTeamArena, "Activate Tag Team Arena?")
    create_tab(tab5, var5, BlackOutMonitors, "Activate Black Out your Monitor after?")
    submission()
    root.mainloop()


if __name__ == "__main__":
    gui()


# create labels for the options
