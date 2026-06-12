"""
xxx.script.py

Purpose:
 - Allow the user to create a chain dimension between elements that are parallel to a picked base element.
 - Prompts:
    1) Pick the first (base) element.
    2) Pick other elements (must be parallel to the base).
    3) Pick a point to place the dimensions.
 - Builds a ReferenceArray by extracting a geometry line Reference where possible, falls back to the element Reference.
 - Creates a new Dimension in the active view flattened to that view's sketch plane.

High-level flow:
 - Define Parallel selection filter to accept elements parallel to base.
 - Compute a dimension placement line flattened to the active view.
 - Extract geometry references, then create the dimension inside a Transaction.
"""

from Autodesk.Revit.DB import (
    Transaction, ReferenceArray, Reference,
    Line, XYZ, Options, ElementId,
    Dimension, Grid,
)
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from System.Collections.Generic import List
from pyrevit import HOST_APP, forms, script


class Parallel(ISelectionFilter):
    def __init__(self, element):
        if hasattr(element, 'Normal'):
            self.Normal = element.Normal
        elif hasattr(element, 'Curve'):
            self.Normal = element.Curve.Direction
        elif hasattr(element, 'Location'):
            self.Normal = element.Location.Curve.Direction
        else:
            raise ValueError('Element does not have known direction attribute')

    def AllowElement(self, element):
        if isinstance(element, Dimension):
            return False

        if hasattr(element, 'Normal'):
            if element.Normal.CrossProduct(self.Normal).IsAlmostEqualTo(XYZ.Zero):
                return True
            else:
                return False
        elif hasattr(element, 'Curve'):
            return element.Curve.Direction.CrossProduct(self.Normal).IsAlmostEqualTo(XYZ.Zero)
        elif hasattr(element, 'Location'):
            return element.Location.Curve.Direction.CrossProduct(self.Normal).IsAlmostEqualTo(XYZ.Zero)
        return False

    def AllowReference(self, reference, point):
        return False


# projection of u onto v
def project(u, v):
    return v.Multiply(u.DotProduct(v) / v.DotProduct(v))


def reject(u, v):
    return u.Subtract(project(u, v))


def get_curve(element):
    if hasattr(element, 'Curve'):
        return element.Curve
    elif hasattr(element, 'Location'):
        return element.Location.Curve
    else:
        raise ValueError('Element does not have known direction attribute')


uidoc = HOST_APP.uiapp.ActiveUIDocument
doc = uidoc.Document
sel = uidoc.Selection

base_ref = sel.PickObject(ObjectType.Element, 'Select first element to dimension')
base_element = doc.GetElement(base_ref)
try:
    refs = sel.PickObjects(ObjectType.Element, Parallel(base_element), 'Select elements to dimension',
                           List[Reference]([base_ref]))
except Exception as e:
    print(e)
    script.exit()

if len(refs) < 2:
    forms.alert('Please select at least two elements.')
    script.exit()

elements = [(x, doc.GetElement(x)) for x in refs]

dimension_point = sel.PickPoint('Select where to place the dimensions')
view_normal = uidoc.ActiveView.UpDirection.CrossProduct(uidoc.ActiveView.RightDirection)

first_curve = get_curve(doc.GetElement(refs[0]))
r1 = reject(dimension_point.Subtract(first_curve.Origin), first_curve.Direction)

rejection = reject(r1, view_normal)

# get line along which to place dimensions
# hack to flatten into current view
# TODO: fix this so it works for elevations
z = uidoc.ActiveView.SketchPlane.GetPlane().Origin.Z
pt = XYZ(dimension_point.X, dimension_point.Y, z)
rejection = XYZ(rejection.X, rejection.Y, 0)
the_line = Line.CreateUnbound(pt, rejection)

# build reference array of elements to dimension
ref_array = ReferenceArray()
for ref, element in elements:
    try:
        if isinstance(element, Grid):
            ref_array.Append(ref)
        else:
            options = Options()
            options.ComputeReferences = True
            options.IncludeNonVisibleObjects = True
            options.View = uidoc.ActiveView
            geometry = element.get_Geometry(options)
            geometry_instance = next(iter(geometry))
            instance_geometry = geometry_instance.GetInstanceGeometry()
            ig_list = list(instance_geometry)
            ig_lines = [x for x in ig_list if isinstance(x, Line)]
            ref_array.Append(ig_lines[0].Reference)
    except Exception as e:
        # print exception to give clearer debugging info instead of silent bare except
        print('error finding ', ref, e)
        ref_array.Append(ref)

with Transaction(doc, 'Create dimensions') as t:
    t.Start()
    the_dimension = doc.Create.NewDimension(uidoc.ActiveView, the_line, ref_array)
    t.Commit()

sel.SetElementIds(List[ElementId]([the_dimension.Id]))
print(the_dimension.Id)
