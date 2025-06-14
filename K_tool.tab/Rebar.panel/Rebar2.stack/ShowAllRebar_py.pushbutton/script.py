__title__ = "Show All Rebar"
__author__ = "Khoa"
__helpurl__ = ""
__doc__ = """Version = 1.0
Date    = 10.10.2023
_____________________________________________________________________
Description:
Show all rebar bars in current view
_____________________________________________________________________
How-to:
- Click on the button Show All Rebar.
_____________________________________________________________________
"""
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Structure import *
from Autodesk.Revit.UI import TaskDialog

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# Start a transaction
t = Transaction(doc, "Show All Rebar Bars")
t.Start()

try:
    # Get all rebar elements in the CURRENT VIEW
    collector = FilteredElementCollector(doc, doc.ActiveView.Id)
    rebars = collector.OfCategory(BuiltInCategory.OST_Rebar).WhereElementIsNotElementType().ToElements()

    # Get current view
    view = doc.ActiveView

    # Make all bars visible
    for rebar in rebars:
        try:
            if hasattr(rebar, 'NumberOfBarPositions'):
                for i in range(rebar.NumberOfBarPositions):
                    rebar.SetBarHiddenStatus(view, i, False)
        except:
            continue  # Skip any bars that cause errors
    
    t.Commit()
    #TaskDialog.Show("Success", "All rebar bars have been made visible in view: {}".format(view.Name))
    
except Exception as e:
    t.RollBack()
    TaskDialog.Show("Error", "Failed to process bars in view {}: {}".format(view.Name, str(e)))