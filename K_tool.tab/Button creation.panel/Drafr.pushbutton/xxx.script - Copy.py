# -*- coding: utf-8 -*-
# Works in RevitPythonShell, pyRevit, or Dynamo's Python node (IronPython/.NET)

from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.UI import TaskDialog
from Autodesk.Revit.UI.Selection import ObjectType

# Get the active Revit document and UI document
uidoc = __revit__.ActiveUIDocument  # __revit__ is provided by pyRevit/RevitPythonShell
doc = uidoc.Document

try:
    # Prompt user to pick multiple elements
    picked_refs = uidoc.Selection.PickObjects(ObjectType.Element, "Select elements")

    if picked_refs:
        lines = []
        for r in picked_refs:
            elem = doc.GetElement(r.ElementId)
            elem_id = elem.Id.IntegerValue
            elem_name = elem.Name
            elem_cat = elem.Category.Name if elem.Category else "No Category"
            lines.append("ID: {} | Category: {} | Name: {}".format(elem_id, elem_cat, elem_name))

        TaskDialog.Show(
            "Selected Elements",
            "Count: {}\n\n{}".format(len(picked_refs), "\n".join(lines))
        )
    else:
        TaskDialog.Show("Selection", "No elements selected.")

except OperationCanceledException:
    # User pressed ESC or canceled selection
    TaskDialog.Show("Selection", "Selection canceled by user.")

except Exception as ex:
    # Any other unexpected error
    TaskDialog.Show("Error", str(ex))
