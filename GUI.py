# Tkinter gui to activate certain parts of PyAutoRaid

import tkinter as tk
from tkinter import ttk
from tkinter import *

root = tk.Tk()
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
tab_control.pack(expand=1, fill="both")


var1 = tk.IntVar()
var2 = tk.IntVar()
var3 = tk.IntVar()
var4 = tk.IntVar()
var5 = tk.IntVar()


def establish_clicked():
    if var1.get() == False:
        print("False")
    elif var1.get() == True:
        print("True")
    elif var2.get() == False:
        print("False")
    elif var2.get() == True:
        print("True")
    elif var3.get() == False:
        print("False")
    elif var3.get() == True:
        print("True")
    elif var4.get() == False:
        print("False")
    elif var4.get() == True:
        print("True")
    elif var5.get() == False:
        print("False")
    elif var5.get() == True:
        print("True")


ttk.Checkbutton(
    tab1,
    text="Activate AutoRewards?",
    variable=var1,
    offvalue=False,
    onvalue=True,
    command=establish_clicked,
).grid(column=0, row=0, padx=30, pady=30)
ttk.Checkbutton(
    tab2,
    text="Activate Auto Clan Boss?",
    variable=var2,
    offvalue=False,
    onvalue=True,
    command=establish_clicked,
).grid(column=0, row=0, padx=30, pady=30)
ttk.Checkbutton(
    tab3,
    text="Activate Auto Classic Arena?",
    variable=var3,
    offvalue=False,
    onvalue=True,
    command=establish_clicked,
).grid(column=0, row=0, padx=30, pady=30)
ttk.Checkbutton(
    tab4,
    text="Activate Auto Tag Team Arena?",
    variable=var4,
    offvalue=False,
    onvalue=True,
    command=establish_clicked,
).grid(column=0, row=0, padx=30, pady=30)
ttk.Checkbutton(
    tab5,
    text="Activate Blackout Screen After?",
    variable=var5,
    offvalue=False,
    onvalue=True,
    command=establish_clicked,
).grid(column=0, row=0, padx=30, pady=30)


root.mainloop()
