__title__ = " ISO Workset"
__author__ = " Khoa Le"
__doc__ = " set workset to Isolate"


# Import the necessary modules
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

# Get the active document and the user interface
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


def hide_all_user_worksets(doc):
    """
    This function collects all user worksets in the given Revit document and sets them to hidden.

    Parameters:
    doc (Document): The active Revit document.
    """
    # Collect all user worksets
    worksets = FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)

    # Start a transaction to hide worksets
    t = Transaction(doc, "Hide Worksets")
    t.Start()

    # Loop through each workset and set it to hidden
    for workset in worksets:
        workset_id = workset.Id
        doc.ActiveView.SetWorksetVisibility(workset_id, WorksetVisibility.Hidden)

    # Commit the transaction
    t.Commit()

# Define a function to hide the workset of the selected elements
def iso_workset(selection):
    # Start a transaction
    t = Transaction(doc, 'ISO Workset')
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
        doc.ActiveView.SetWorksetVisibility(workset_id, WorksetVisibility.Visible)

    # Commit the transaction
    t.Commit()


# Call the function to hide all user worksets
hide_all_user_worksets(doc)
# Get the selected elements


selection = uidoc.Selection.GetElementIds()


# Call the function with the selected elements
iso_workset(selection)
