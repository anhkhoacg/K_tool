import clr
clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import *

# Get the active view
doc = __revit__.ActiveUIDocument.Document
activeView = doc.ActiveView

# Create a FilteredElementCollector for the active view
collector = FilteredElementCollector(doc, activeView.Id)

# Get all elements in the active view
elements = collector.ToElements()

# Initialize an empty set to store unique category names
unique_categories = set()

# Iterate over each element and get its category
for element in elements:
    type_id = element.GetTypeId()
    if type_id != ElementId.InvalidElementId:
        category = doc.GetElement(type_id).Category
        if category is not None:
            unique_categories.add(category.Name)

# Print the unique category names
#for cat_name in unique_categories:
print(unique_categories)
