__title__ = "Show All Worksets"
__author__ = "Khoa Le"
__doc__ = "Make all worksets visible in the current view"

# Import necessary modules
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

# Get the active document and UI document
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# Start transaction
t = Transaction(doc, "Show All Worksets")
t.Start()

try:
    # Get all user worksets
    worksets = FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)
    
    # Make all worksets visible
    for workset in worksets:
        workset_id = WorksetId(workset.Id.IntegerValue)
        doc.ActiveView.SetWorksetVisibility(workset_id, WorksetVisibility.Visible)
    
    t.Commit()
    TaskDialog.Show("Success", "All worksets are now visible in this view")
    
except Exception as e:
    t.RollBack()
    TaskDialog.Show("Error", str(e))