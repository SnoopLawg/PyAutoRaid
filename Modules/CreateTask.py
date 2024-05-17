import subprocess
import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
import pyautogui

def generate_time_options():
    times = []
    for hour in range(24):
        for minute in [0, 30]:
            if hour < 12:
                suffix = "AM"
                display_hour = hour if hour > 0 else 12
            else:
                suffix = "PM"
                display_hour = hour - 12 if hour > 12 else 12
            times.append(f"{display_hour:02d}:{minute:02d} {suffix}")
    return times

def convert_to_military_time(time_str):
    time, meridiem = time_str.split()
    hour, minute = map(int, time.split(':'))
    if meridiem == "PM" and hour < 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"

def sched_setup(task_name, script_path, start_time):
    # Correctly escape the double quotes around the script path
    command = f'schtasks /Create /SC DAILY /TN "{task_name}" /TR \"{script_path}\" /ST {start_time} /RL HIGHEST'
    # Execute the command
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result

def on_submit():
    # Convert the selected time to 24-hour format
    start_time_24hr = convert_to_military_time(start_time_combo.get())
    # Extract the first four digits (HHMM) from the 24-hour time format
    time_prefix = start_time_24hr.replace(":", "")
    # Determine the executable name based on the user's choice
    exe_name = "DailyQuests" if exe_choice.get() == "DailyQuests" else "PyAutoRaid"
    # Construct the task name using the time prefix and executable name
    task_name = f"{time_prefix}{exe_name}"
    start_time = convert_to_military_time(start_time_combo.get())
    if exe_choice.get() == "DailyQuests":
        script_path = "C:\\Program Files (x86)\\PyAutoRaid\\DailyQuests.exe"
    else:
        script_path = "C:\\Program Files (x86)\\PyAutoRaid\\PyAutoRaid.exe"
    result = sched_setup(task_name, script_path, start_time)
    if result.returncode == 0:
        update_message(f"The task for {exe_choice.get()} was successfully created to run at {start_time_combo.get()}.")
    else:
        update_message(f"Failed to create the task. Error: {result.stderr}")

def update_message(message):
    global scrollable_frame
    ttk.Label(scrollable_frame, text=message).pack()

root = ThemedTk(theme="equilux")
root.title("Task Scheduler Setup")

container = ttk.Frame(root, padding=30)
canvas = tk.Canvas(container)
scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
scrollable_frame = ttk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

container.grid(row=4, column=0, columnspan=2, sticky="nsew")
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

ttk.Label(root, text="Start Time: ",padding=(5,0),font=('Helvetica', 12, 'bold')).grid(row=0, column=0, sticky='e',padx=5)
start_time_options = generate_time_options()
start_time_combo = ttk.Combobox(root, values=start_time_options, width=15)
start_time_combo.grid(row=0, column=1, sticky='w',padx=15)
start_time_combo.set(start_time_options[0])

exe_choice = tk.StringVar(value="DailyQuests")
ttk.Radiobutton(root, text='DailyQuests.exe', value='DailyQuests', variable=exe_choice).grid(row=2, column=0,pady=10)
ttk.Radiobutton(root, text='PyAutoRaid.exe', value='PyAutoRaid', variable=exe_choice).grid(row=2, column=1,sticky='w',padx=10,pady=10)

submit_button = ttk.Button(root, text="Submit", command=on_submit)
submit_button.grid(row=3, column=1, columnspan=2 ,pady=(10,0),sticky='w')

root.rowconfigure(4, weight=1)
root.columnconfigure(1, weight=1)
canvas.config(background='#464646')
root.configure(background='#464646')
root.mainloop()
