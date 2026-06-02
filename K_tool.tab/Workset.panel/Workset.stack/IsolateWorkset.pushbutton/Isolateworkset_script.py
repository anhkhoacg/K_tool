__title__ = "Show Active Workset"
__author__ = "Khoa Le"
__doc__ = "Set current active workset to visible in active view"


import clr
# Import the necessary modules
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import TaskDialog

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


# Define a function to show the active workset
def show_active_workset():
    active_ws_id = doc.GetWorksetTable().GetActiveWorksetId()

    t = Transaction(doc, "Show Active Workset")
    try:
        t.Start()
        doc.ActiveView.SetWorksetVisibility(active_ws_id, WorksetVisibility.Visible)
        t.Commit()
    except Exception as e:
        if t.HasStarted():
            t.RollBack()
        TaskDialog.Show("Error", str(e))


# Run
show_active_workset()
