__doc__ = "Make all bars Uobscured in view."
__title__ = "UNObscure Bars"
__author__ = "Wolinski"










import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Structure import *
from Autodesk.Revit.UI import TaskDialog

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView

# Collect rebar elements visible in current view
rebar_collector = FilteredElementCollector(doc, view.Id).OfClass(Rebar)

x = True
t = Transaction(doc, "ObscuredBars")
t.Start()
for rebar in rebar_collector:
    rebar.SetUnobscuredInView(view, x)
t.Commit()
