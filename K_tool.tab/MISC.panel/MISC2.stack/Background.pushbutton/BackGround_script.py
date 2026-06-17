# -*- coding: utf-8 -*-
__title__ = "change Background"
__author__ = "Khoa"
__helpurl__ = ""
__doc__ = """Version = 1.1
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
    colors = [Color(0, 0, 0), Color(200, 200, 200), Color(255, 255, 255)]
    
    # Convert current color to tuple for easier comparison
    current = (current_color.Red, current_color.Green, current_color.Blue)
    color_tuples = [(0, 0, 0), (200, 200, 200), (255, 255, 255)]
    
    # Find current color index and cycle to next
    try:
        idx = color_tuples.index(current)
        app.BackgroundColor = colors[(idx + 1) % len(colors)]
    except ValueError:
        # If current color doesn't match, default to black
        app.BackgroundColor = colors[0]
