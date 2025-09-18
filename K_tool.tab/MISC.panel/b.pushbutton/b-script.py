import clr

clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')
from System.Windows.Forms import Form, ComboBox, Button, Label, DialogResult
from System.Drawing import Point, Size

from Autodesk.Revit.DB import *  # This imports most classes, but not always Rebar!
from Autodesk.Revit.DB.Structure import Rebar  # <-- Add this line
from Autodesk.Revit.UI import TaskDialog

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# Collect selected rebars
selected_ids = uidoc.Selection.GetElementIds()
rebars = [doc.GetElement(id) for id in selected_ids if isinstance(doc.GetElement(id), Rebar)]

if not rebars:
    TaskDialog.Show("Error", "Please select at least one Rebar element before running this script.")
    raise Exception("No Rebar selected.")

# Collect Multi-Rebar Annotation Types
annotation_types = list(FilteredElementCollector(doc).OfClass(MultiReferenceAnnotationType))
if not annotation_types:
    TaskDialog.Show("Error", "No Multi-Rebar Annotation Types found in the project.")
    raise Exception("No annotation types found.")


# Windows Form for selection
class AnnotationForm(Form):
    def __init__(self, annotation_types):
        Form.__init__(self)  # Must be first!
        self.Text = "Select Multi-Rebar Annotation Type"
        self.Size = Size(350, 120)
        self.StartPosition = 1  # CenterScreen

        self.label = Label()
        self.label.Text = "Annotation Type:"
        self.label.Location = Point(10, 20)
        self.label.Size = Size(100, 20)
        self.Controls.Add(self.label)

        self.combo = ComboBox()
        self.combo.Location = Point(120, 18)
        self.combo.Size = Size(200, 20)
        for t in annotation_types:
            self.combo.Items.Add(t.Name)
        self.combo.SelectedIndex = 0
        self.Controls.Add(self.combo)

        self.ok_button = Button()
        self.ok_button.Text = "OK"
        self.ok_button.Location = Point(120, 50)
        self.ok_button.Click += self.ok_clicked
        self.Controls.Add(self.ok_button)

        self.selected_index = 0

    def ok_clicked(self, sender, args):
        self.selected_index = self.combo.SelectedIndex
        self.DialogResult = DialogResult.OK
        self.Close()


# Show form
form = AnnotationForm(annotation_types)
result = form.ShowDialog()

if result == DialogResult.OK:
    selected_type = annotation_types[form.selected_index]
    TaskDialog.Show("Selection", "You selected: {}".format(selected_type.Name))
    # Here you can proceed to create the annotation using selected rebars and annotation type
else:
    TaskDialog.Show("Cancelled", "Operation cancelled by user.")
