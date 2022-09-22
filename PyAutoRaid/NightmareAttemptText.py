# Just ad NM in Log.txt
from datetime import datetime
import pathlib


def NightmareAttemptText():
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    with open("log.txt", mode="w") as file:
        file.write("CB NIGHTMARE ATTEMPT\n")
        file.write(dt_string)


if __name__ == "__main__":
    NightmareAttemptText()
