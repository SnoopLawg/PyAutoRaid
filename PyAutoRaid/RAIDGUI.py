# Tkinter gui to activate certain parts of PyAutoRaid

import tkinter as tk
from tkinter import ttk
from tkinter import *


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

var1 = tk.BooleanVar(value=True)
var2 = tk.BooleanVar(value=True)
var3 = tk.BooleanVar(value=True)
var4 = tk.BooleanVar(value=True)
var5 = tk.BooleanVar(value=True)


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

    root.mainloop()


if __name__ == "__main__":
    gui()
