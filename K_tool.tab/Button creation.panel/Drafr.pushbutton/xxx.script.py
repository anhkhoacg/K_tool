# Works in RevitPythonShell / pyRevit (IronPython) or CPython via Revit API
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    LinePatternElement,
    Transaction, BuiltInCategory, GraphicsStyleType
)
from System import Enum

doc = __revit__.ActiveUIDocument.Document  # pyRevit/RevitPythonShell
# If using RevitPythonShell without __revit__, use:
# doc = __revit__.ActiveUIDocument.Document

# Collect all LinePatternElements
patterns = FilteredElementCollector(doc).OfClass(LinePatternElement).ToElements()


def segment_type_to_str(seg_type):
    # LinePatternSegmentType is an enum: Dash, Dot, Space
    return str(seg_type)  # prints something like 'Dash', 'Dot', or 'Space'


if not patterns:
    print("No Line Patterns found in this project.")
else:
    lines_cat = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)
    t = Transaction(doc, "Create line styles from line patterns")
    t.Start()
    try:
        for lpe in sorted(patterns, key=lambda e: e.Name or ""):
            name = lpe.Name or ""
            if not name:
                continue
            subcat = None
            try:
                subcat = lines_cat.SubCategories.get_Item(name)
            except:
                subcat = None

            if subcat is None:
                subcat = doc.Settings.Categories.NewSubcategory(lines_cat, name)

            gs = subcat.GetGraphicsStyle(GraphicsStyleType.Projection)
            gs.GraphicsStyleCategory.SetLinePatternId(lpe.Id, GraphicsStyleType.Projection)
        t.Commit()
    except:
        t.RollBack()
        raise
