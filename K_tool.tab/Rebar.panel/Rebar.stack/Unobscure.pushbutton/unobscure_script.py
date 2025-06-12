__doc__ = "Make all bars unobscured in view."
__title__ = "Unobscure Bars"
__author__ = "MWolinski"
import Autodesk
from Autodesk.Revit import DB
from Autodesk.Revit.UI import *
from Autodesk.Revit.DB import *
"from rebar_selector import RebarSelector"

'''
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView

rs = RebarSelector(doc, uidoc)
rebar_collector = rs.get_all_rebars()
'''


# Get the current document
doc = DocumentManager.Instance.CurrentDBDocument

# Get the active view
active_view = doc.ActiveView

collector = FilteredElementCollector(doc, active_view.Id)
rebar_elements = collector.OfCategory(BuiltInCategory.OST_Rebar).ToElements()



x = True

t = DB.Transaction(doc, "Unobscured")
t.Start()
for rebar in rebar_elements:
    rebar.SetUnobscuredInView(view, x)
t.Commit()
