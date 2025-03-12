# -*- coding: utf-8 -*-
__title__ = "change Background"
__author__ = "Khoa"
__helpurl__ = ""
__doc__ = """Version = 1.0
Date    = 10.10.2023
_____________________________________________________________________
Description:
Change revit background in order: Black-> Gray -> White -> Black...
_____________________________________________________________________
How-to:
- Click on the button to change background colour in Revit.
_____________________________________________________________________
"""

# IMPORTS
from Autodesk.Revit.DB import Color

# VARIABLES
app = __revit__.Application

# MAIN
if __name__ == '__main__':
    # COLOURS
    current_color = app.BackgroundColor
    Black = Color(0, 0, 0)
    White = Color(255, 255, 255)
    Gray = Color(150, 150, 150)


    if current_color.Blue == 255 and current_color.Red == 255 and current_color.Green == 255:
        app.BackgroundColor = Black
    elif current_color.Blue == 0 and current_color.Red == 0 and current_color.Green == 0:
        app.BackgroundColor = Gray
    else:
        app.BackgroundColor = White
         