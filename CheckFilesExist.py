#Check if all the py files were downloaded

import os.path
import tkinter
from tkinter import messagebox

def CheckFilesExist():
    Needed_Files=['AutoRewards.py','BlackOutMonitor.py','CBauto.py','CheckFilesExist.py','ClassicArena.py','log.txt','LoopFindImage.py','Main.py','NightMareAttemptText.py','OpenRaid.py','quitAll.py']
    Total_files =0
    for file in Needed_Files:
        file_exists=os.path.exists(file)
        if file_exists == True:
            print('Have',file)
            Total_files+= 1
        elif file_exists == False:
            print('Dont have',file)
    missing=int(11-Total_files)
    if Total_files == 11:
        print(Total_files,'files were downloaded')
    else:
        print('All 11 files were not downloaded. Only',Total_files,'were')
        tkinter.messagebox.showerror(title='ALL FILES NOT DOWNLOADED',message='You are missing files')
        exit()
if __name__=='__main__':
    CheckFilesExist()