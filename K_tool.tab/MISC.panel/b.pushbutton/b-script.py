# -*- coding: utf-8 -*-
# pyRevit script: Get user input in a single form

from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import revit, DB
from pyrevit import script
from pyrevit.forms import ProgressBar

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


def get_param_value(element, param_name):
    """Helper function to get parameter value"""
    param = element.LookupParameter(param_name)
    if not param:
        # Try to get parameter by built-in parameter
        if param_name == "Partition":
            param = element.get_Parameter(BuiltInParameter.NUMBER_PARTITION_PARAM)
        elif param_name == "Number":
            param = element.get_Parameter(BuiltInParameter.REBAR_NUMBER)

    if param:
        if param.StorageType == StorageType.String:
            return param.AsString()
        elif param.StorageType == StorageType.Integer:
            return str(param.AsInteger())
        elif param.StorageType == StorageType.Double:
            return str(param.AsDouble())
    return None


def get_all_rebar_partitions():
    """Get all unique rebar partitions in the model using parameter name"""
    all_rebars = FilteredElementCollector(doc).OfCategory(
        BuiltInCategory.OST_Rebar).WhereElementIsNotElementType().ToElements()
    partitions = set()

    # Debug information
    if not all_rebars:
        forms.alert("No rebars found in the model!")
        return []

    for rebar in all_rebars:
        partition = get_param_value(rebar, "Partition")
        if partition:
            partitions.add(partition)

    # Debug information
    if not partitions:
        forms.alert("No partitions found in the rebars. Check parameter names.")

    return sorted(list(partitions))


def get_rebar_numbers_in_partition(partition):
    """Get all rebar numbers in a specific partition"""
    all_rebars = FilteredElementCollector(doc).OfCategory(
        BuiltInCategory.OST_Rebar).WhereElementIsNotElementType().ToElements()
    rebar_data = []

    # Debug information
    if not all_rebars:
        forms.alert("No rebars found while getting numbers!")
        return []

    for rebar in all_rebars:
        current_partition = get_param_value(rebar, "Partition")
        if current_partition == partition:
            number = get_param_value(rebar, "Number")
            if number:
                # Store both the number and ElementId for later use
                rebar_data.append({
                    'number': str(number),
                    'id': rebar.Id.IntegerValue,
                    'rebar': rebar
                })

    # Debug information
    if not rebar_data:
        forms.alert("No rebar numbers found in partition: " + partition)

    # Sort by number
    sorted_data = sorted(rebar_data, key=lambda x: int(x['number']))
    return sorted_data


def get_selected_rebar():
    """Get the currently selected rebar element if any"""
    selection = list(uidoc.Selection.GetElementIds())
    if len(selection) == 1:
        element = doc.GetElement(selection[0])
        if element and element.Category and element.Category.Id.IntegerValue == int(BuiltInCategory.OST_Rebar):
            return element
    return None


class InputForm(forms.WPFWindow):
    def __init__(self):
        forms.WPFWindow.__init__(self, 'input_form.xaml')

        # Set up event handlers
        self.ok_button.Click += self.save_values
        self.cancel_button.Click += self.window_close
        self.Select_partition.SelectionChanged += self.on_partition_changed

        # Store rebar data
        self.rebar_data = []

        # Get all partitions
        self.partitions = get_all_rebar_partitions()
        if not self.partitions:
            forms.alert("No rebar partitions found in the model.", exitscript=True)

        # Set up partition dropdown
        self.Select_partition.ItemsSource = self.partitions

        # Check for selected rebar
        selected_rebar = get_selected_rebar()
        if selected_rebar:
            # Set default partition from selection
            partition = get_param_value(selected_rebar, "Partition")
            if partition in self.partitions:
                self.Select_partition.SelectedItem = partition

            # Store default rebar number from selection (apply after items are populated)
            current_number = get_param_value(selected_rebar, "Number")
            if current_number:
                self.default_current_number = str(current_number)
        else:
            # No selection, set first partition
            self.Select_partition.SelectedIndex = 0

        # Initialize rebar numbers for selected partition
        self.update_rebar_numbers()

        # If a rebar was selected when the form opened, apply that number selection now
        if hasattr(self, 'default_current_number') and self.rebar_data:
            # ItemsSource contains unique number strings; check against that list
            unique_numbers = [str(n) for n in
                              sorted({int(d['number']) for d in self.rebar_data})] if self.rebar_data else []
            if self.default_current_number in unique_numbers:
                self.Select_rebar_number.SelectedItem = self.default_current_number

        # Set up default value for new rebar number
        self.New_Rebar_number.Text = ""

    def on_partition_changed(self, sender, e):
        self.update_rebar_numbers()

    def update_rebar_numbers(self):
        selected_partition = self.Select_partition.SelectedItem
        if selected_partition:
            # Get rebar data for the selected partition
            self.rebar_data = get_rebar_numbers_in_partition(selected_partition)

            # Update the dropdown with unique numbers (numerically sorted)
            if self.rebar_data:
                # build a set of integer numbers (fall back to string if parsing fails)
                unique_ints = set()
                unique_others = set()
                for d in self.rebar_data:
                    try:
                        unique_ints.add(int(d['number']))
                    except Exception:
                        unique_others.add(str(d['number']))

                # create sorted list: numeric first, then other strings
                numbers_list = [str(n) for n in sorted(unique_ints)]
                if unique_others:
                    numbers_list.extend(sorted(unique_others))

                self.Select_rebar_number.ItemsSource = numbers_list
                self.Select_rebar_number.SelectedIndex = 0

    def save_values(self, sender, e):
        # Get values from input form
        self.current_number = self.Select_rebar_number.SelectedItem  # Changed from .Text to .SelectedItem
        self.new_number = self.New_Rebar_number.Text
        self.selected_partition = self.Select_partition.SelectedItem

        # Find selected rebar data
        self.selected_rebar_data = next(
            (data for data in self.rebar_data if data['number'] == self.current_number),
            None
        )

        # Validate new rebar number is an integer
        try:
            int(self.new_number)
            if self.selected_rebar_data:  # Make sure we have valid rebar data
                self.DialogResult = True
                self.Close()
            else:
                forms.alert("Please select a valid rebar number.", exitscript=False)
        except ValueError:
            forms.alert("New rebar number must be an integer.", exitscript=False)

    def window_close(self, sender, e):
        self.DialogResult = False
        self.Close()


def get_user_inputs():
    # Create and show the form
    input_form = InputForm()
    result = input_form.show_dialog()

    # If user cancelled
    if not result:
        forms.alert("Operation cancelled by user.", exitscript=True)

    # Validate number inputs
    try:
        current_num = int(input_form.current_number)
        new_num = int(input_form.new_number)
    except ValueError:
        forms.alert("Please enter valid numbers for current and new rebar numbers.", exitscript=True)

    return {
        'partition': input_form.selected_partition,
        'current_number': current_num,
        'new_number': new_num
    }


# Main execution
try:
    user_inputs = get_user_inputs()

    # Show the results
    forms.alert(
        "You entered:\n"
        "Partition: {0}\n"
        "Current Rebar Number: {1}\n"
        "New Rebar Number: {2}".format(
            user_inputs['partition'],
            user_inputs['current_number'],
            user_inputs['new_number']
        ),
        title="Summary"
    )
except Exception as e:
    forms.alert("An error occurred: {}".format(str(e)), exitscript=True)
