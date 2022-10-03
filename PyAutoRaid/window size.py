from turtle import width
import win32gui

from screeninfo import Monitor, get_monitors


def get_screen():
    for m in get_monitors():
        width = m.width
        height = m.height
        main = m.is_primary
        if main == True:
            center_width = int((width / 2) - 450)
            center_height = int((height / 2) - 300)
            return (center_width, center_height)


get_screen()
print(get_screen())
