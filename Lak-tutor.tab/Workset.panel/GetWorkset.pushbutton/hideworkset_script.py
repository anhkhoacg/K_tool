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


# Define a function to hide the workset of the selected elements
def hide_workset(selection):
    # Start a transaction
    t = Transaction(doc, 'Hide Workset')
    t.Start()

    # Loop through the selected elements
    for eid in selection:
        # Get the element and its workset id
        element = doc.GetElement(eid)
        workset_id = element.WorksetId

        # Get the workset visibility settings for the active view
        workset_visibility = doc.ActiveView.GetWorksetVisibility(workset_id)

        # If the workset is visible, hide it
        # if workset_visibility == WorksetVisibility.Visible:
        doc.ActiveView.SetWorksetVisibility(workset_id, WorksetVisibility.Hidden)

    # Commit the transaction
    t.Commit()


# Get the selected elements
selection = uidoc.Selection.GetElementIds()

# Call the function with the selected elements
hide_workset(selection)
