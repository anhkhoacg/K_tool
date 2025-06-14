__title__ = " hide Workset"
__author__ = " Khoa Le"
__doc__ = " set workset to hide"


# Import the necessary modules
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

# Get the active document and the user interface
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


# Define a function to hide all worksets except the workset of the selected elements
def hide_workset(selection):
    # Get all worksets in the document
    worksets = FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)
    
    # Get the workset of the selected elements
    selected_workset_ids = set()
    for elem_id in selection:
        elem = doc.GetElement(elem_id)
        if elem and elem.WorksetId:
            selected_workset_ids.add(elem.WorksetId)
    
    # Start transaction
    t = Transaction(doc, "Isolate Workset")
    t.Start()
    
    try:
        # Hide all worksets except the selected one
        for workset in worksets:
            workset_id = WorksetId(workset.Id.IntegerValue)
            if workset_id in selected_workset_ids:
                # Show the selected workset
                doc.ActiveView.SetWorksetVisibility(workset_id, WorksetVisibility.Visible)
            else:
                # Hide other worksets
                doc.ActiveView.SetWorksetVisibility(workset_id, WorksetVisibility.Hidden)
        
        t.Commit()
    except Exception as e:
        t.RollBack()
        TaskDialog.Show("Error", str(e))


# Get the selected elements
selection = uidoc.Selection.GetElementIds()

# Call the function with the selected elements
hide_workset(selection)
