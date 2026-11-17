# -*- coding: utf-8 -*-
"""Rebar Renumber - manage rebar numbering sequences (partitions).

Actions (all through Revit's NumberingSchema API, Revit 2015+):
  - Change number        : A -> B (offers a swap when B is already used)
  - Swap two numbers     : A <-> B, via a spare number, as one undo step
  - Close gaps           : RemoveGaps (lowest number is kept)
  - Shift start number   : ShiftNumbers (gaps are kept)
  - Move bars to partition: AssignElementsToSequence for picked/selected bars
"""

import clr
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("WindowsBase")

from System.Collections.Generic import HashSet, List
from System.Windows import Visibility
from System.Windows.Media import Brushes

from Autodesk.Revit.DB import (BuiltInCategory, BuiltInParameter, ElementId,
                               FilteredElementCollector, NumberingSchema,
                               NumberingSchemaTypes, Transaction, TransactionGroup)
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import forms

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

DEFAULT_PARTITION_LABEL = "(default)"

ACTION_CHANGE = "Change number"
ACTION_SWAP = "Swap two numbers"
ACTION_GAPS = "Close gaps in partition"
ACTION_SHIFT = "Shift start number"
ACTION_MOVE = "Move bars to partition"
ACTIONS = [ACTION_CHANGE, ACTION_SWAP, ACTION_GAPS, ACTION_SHIFT, ACTION_MOVE]

ACTION_HINTS = {
    ACTION_CHANGE: "Gives every bar with the selected number a new, unused number.",
    ACTION_SWAP: "Exchanges two numbers in this partition. Undoes as a single step.",
    ACTION_GAPS: "Renumbers so there are no gaps, e.g. 1,2,5,9 -> 1,2,3,4. The lowest number is kept.",
    ACTION_SHIFT: "Moves the whole sequence so it starts at the given number. Gaps are kept.",
    ACTION_MOVE: "Moves the bars to another (or a new) partition; Revit numbers them there. "
                 "Bars matching existing bars in the target get the same number.",
}


# --------------------------------------------------------------------------- helpers

def eid_int(eid):
    """ElementId -> int on all Revit versions (IntegerValue was removed in 2026)."""
    try:
        return eid.Value
    except AttributeError:
        return eid.IntegerValue


REBAR_CAT_ID = int(BuiltInCategory.OST_Rebar)


def is_rebar(element):
    return (element is not None and element.Category is not None
            and eid_int(element.Category.Id) == REBAR_CAT_ID)


def param_string(element, bip, fallback_name):
    param = element.get_Parameter(bip) or element.LookupParameter(fallback_name)
    if param is None or not param.HasValue:
        return None
    value = param.AsString()
    if value is None:
        value = param.AsValueString()
    return value


def parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def partition_label(partition):
    return partition if partition else DEFAULT_PARTITION_LABEL


def partition_key(label):
    label = (label or "").strip()
    return "" if label == DEFAULT_PARTITION_LABEL else label


def error_text(ex):
    text = getattr(ex, "Message", None) or str(ex)
    return text.strip().splitlines()[0] if text.strip() else ex.__class__.__name__


def get_schema():
    return NumberingSchema.GetNumberingSchema(
        doc, NumberingSchemaTypes.StructuralNumberingSchemas.Rebar)


def get_min_digits():
    try:
        return max(1, int(NumberingSchema.GetMinimumNumberOfDigits(doc)))
    except Exception:
        return 1


class RebarFilter(ISelectionFilter):
    def AllowElement(self, element):
        return is_rebar(element)

    def AllowReference(self, reference, point):
        return False


def get_selected_rebar_ids():
    ids = []
    for eid in uidoc.Selection.GetElementIds():
        if is_rebar(doc.GetElement(eid)):
            ids.append(eid)
    return ids


# --------------------------------------------------------------------------- model index

class RebarIndex(object):
    """One pass over the model: partition -> number -> [ElementId]."""

    def __init__(self):
        self.schema = get_schema()
        self.digits = get_min_digits()
        self.by_partition = {}
        self.partition_of = {}
        bars = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rebar) \
            .WhereElementIsNotElementType()
        for bar in bars:
            partition = param_string(bar, BuiltInParameter.NUMBER_PARTITION_PARAM, "Partition") or ""
            raw = param_string(bar, BuiltInParameter.REBAR_NUMBER, "Rebar Number")
            if raw is None or not raw.strip():
                continue
            number = parse_int(raw)
            key = number if number is not None else raw.strip()
            self.by_partition.setdefault(partition, {}).setdefault(key, []).append(bar.Id)
            self.partition_of[eid_int(bar.Id)] = partition

    def partitions(self):
        names = set(self.by_partition.keys())
        try:
            names.update(self.schema.GetNumberingSequences())
        except Exception:
            pass
        return sorted(names, key=lambda p: (p != "", p.lower()))

    def numbers(self, partition):
        keys = list(self.by_partition.get(partition, {}).keys())
        ints = sorted(k for k in keys if isinstance(k, int))
        others = sorted(k for k in keys if not isinstance(k, int))
        return ints + others

    def int_numbers(self, partition):
        return [k for k in self.numbers(partition) if isinstance(k, int)]

    def ids(self, partition, number=None):
        numbers = self.by_partition.get(partition, {})
        if number is not None:
            return list(numbers.get(number, []))
        result = []
        for ids in numbers.values():
            result.extend(ids)
        return result

    def fmt(self, number):
        return str(number).zfill(self.digits) if isinstance(number, int) else number

    def max_number(self, partition):
        high = 0
        try:
            for rng in self.schema.GetNumbers(partition):
                high = max(high, rng.High)
        except Exception:
            pass
        ints = self.int_numbers(partition)
        return max([high] + ints)

    def next_free(self, partition):
        return self.max_number(partition) + 1

    def gaps(self, partition):
        ints = self.int_numbers(partition)
        if not ints:
            return 0
        return (ints[-1] - ints[0] + 1) - len(ints)

    def summary(self, partition):
        ints = self.int_numbers(partition)
        bars = len(self.ids(partition))
        if not ints:
            return "{} bars".format(bars)
        gaps = self.gaps(partition)
        return "{} bars | {} numbers | {}-{} | {}".format(
            bars, len(self.numbers(partition)), self.fmt(ints[0]), self.fmt(ints[-1]),
            "no gaps" if gaps == 0 else "{} missing number{}".format(gaps, "" if gaps == 1 else "s"))


# --------------------------------------------------------------------------- operations
# Each returns a short success message or raises with a readable message.

class ActionError(Exception):
    pass


def run_transaction(name, func):
    t = Transaction(doc, name)
    t.Start()
    try:
        result = func()
        t.Commit()
        return result
    except Exception:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        raise


def op_change(index, partition, old, new):
    run_transaction("Renumber Rebar {} -> {}".format(old, new),
                    lambda: index.schema.ChangeNumber(partition, old, new))
    return "Changed {} -> {}.".format(index.fmt(old), index.fmt(new))


def op_swap(index, partition, a, b):
    spare = index.next_free(partition)
    group = TransactionGroup(doc, "Swap Rebar Numbers {} <-> {}".format(a, b))
    group.Start()
    try:
        for old, new in ((a, spare), (b, a), (spare, b)):
            run_transaction("Swap step", lambda o=old, n=new: index.schema.ChangeNumber(partition, o, n))
        group.Assimilate()
    except Exception:
        if group.HasStarted() and not group.HasEnded():
            group.RollBack()
        raise
    return "Swapped {} <-> {}.".format(index.fmt(a), index.fmt(b))


def op_gaps(index, partition):
    gaps = index.gaps(partition)
    if gaps == 0:
        raise ActionError("This partition has no gaps.")
    run_transaction("Remove Rebar Number Gaps", lambda: index.schema.RemoveGaps(partition))
    return "Closed {} missing number{}.".format(gaps, "" if gaps == 1 else "s")


def op_shift(index, partition, first):
    try:
        maximum = index.schema.MaximumStartingNumber
    except Exception:
        maximum = None
    if first < 1 or (maximum and first > maximum):
        raise ActionError("Start number must be between 1 and {}.".format(maximum or "the maximum"))
    ints = index.int_numbers(partition)
    if ints and ints[0] == first:
        raise ActionError("The sequence already starts at {}.".format(index.fmt(first)))
    run_transaction("Shift Rebar Numbers", lambda: index.schema.ShiftNumbers(partition, first))
    return "Sequence now starts at {}.".format(index.fmt(first))


def op_move(index, ids, target):
    id_set = HashSet[ElementId]()
    for eid in ids:
        id_set.Add(eid)
    run_transaction("Move Rebar to Partition",
                    lambda: index.schema.AssignElementsToSequence(id_set, target))
    return "Moved {} bar{} to '{}'.".format(len(ids), "" if len(ids) == 1 else "s", partition_label(target))


# --------------------------------------------------------------------------- form

class RenumberForm(forms.WPFWindow):
    def __init__(self, state):
        forms.WPFWindow.__init__(self, "input_form.xaml")
        self.state = state
        self.pick_requested = False
        self.select_ids = None
        self.number_keys = []
        self._loading = True

        self.index = RebarIndex()
        self.partition_keys = self.index.partitions()
        if not self.partition_keys:
            forms.alert("No numbered rebar found in the model.", exitscript=True)

        self.move_ids = list(state.get("move_ids") or [])

        self.Select_partition.ItemsSource = [partition_label(p) for p in self.partition_keys]
        self.action_combo.ItemsSource = ACTIONS

        self.Select_partition.SelectionChanged += self.on_partition_changed
        self.action_combo.SelectionChanged += self.on_action_changed
        self.apply_button.Click += self.on_apply
        self.ok_button.Click += self.on_ok
        self.cancel_button.Click += self.on_close
        self.select_button.Click += self.on_select
        self.pick_button.Click += self.on_pick

        self.apply_initial_state()
        self._loading = False
        self.refresh(keep_number=state.get("number"))

    # ---- initial values
    def apply_initial_state(self):
        partition = self.state.get("partition")
        default_number = None
        if partition is None:
            selected = get_selected_rebar_ids()
            if selected:
                partitions = set(self.index.partition_of.get(eid_int(i), "") for i in selected)
                if len(partitions) == 1:
                    partition = partitions.pop()
                if len(selected) == 1 and partition is not None:
                    bar = doc.GetElement(selected[0])
                    raw = param_string(bar, BuiltInParameter.REBAR_NUMBER, "Rebar Number")
                    default_number = parse_int(raw) if raw else None
                if not self.move_ids:
                    self.move_ids = selected
        if partition not in self.partition_keys:
            partition = self.partition_keys[0]
        self.Select_partition.SelectedIndex = self.partition_keys.index(partition)
        self.state.setdefault("number", default_number)

        action = self.state.get("action", ACTION_CHANGE)
        self.action_combo.SelectedIndex = ACTIONS.index(action) if action in ACTIONS else 0
        if self.state.get("target") is not None:
            self.target_partition.Text = self.state["target"]

    # ---- state
    @property
    def partition(self):
        i = self.Select_partition.SelectedIndex
        return self.partition_keys[i] if 0 <= i < len(self.partition_keys) else None

    @property
    def action(self):
        return self.action_combo.SelectedItem or ACTION_CHANGE

    @property
    def number(self):
        i = self.Select_rebar_number.SelectedIndex
        return self.number_keys[i] if 0 <= i < len(self.number_keys) else None

    def get_state(self):
        return {"partition": self.partition, "action": self.action, "number": self.number,
                "target": self.target_partition.Text, "move_ids": self.move_ids}

    # ---- UI refresh
    def refresh(self, keep_number=None):
        partition = self.partition
        self.partition_info.Text = self.index.summary(partition) if partition is not None else ""

        self.number_keys = self.index.numbers(partition) if partition is not None else []
        items = []
        for key in self.number_keys:
            count = len(self.index.ids(partition, key))
            items.append("{}    ({} bar{})".format(self.index.fmt(key), count, "" if count == 1 else "s"))
        self.Select_rebar_number.ItemsSource = items
        if keep_number in self.number_keys:
            self.Select_rebar_number.SelectedIndex = self.number_keys.index(keep_number)
        elif items:
            self.Select_rebar_number.SelectedIndex = 0

        targets = [partition_label(p) for p in self.partition_keys]
        text = self.target_partition.Text
        self.target_partition.ItemsSource = targets
        self.target_partition.Text = text

        self.update_action_ui()

    def update_action_ui(self):
        action = self.action
        show = lambda ctrl, on: setattr(ctrl, "Visibility", Visibility.Visible if on else Visibility.Collapsed)
        show(self.row_number, action in (ACTION_CHANGE, ACTION_SWAP))
        show(self.row_value, action in (ACTION_CHANGE, ACTION_SWAP, ACTION_SHIFT))
        show(self.row_pick, action == ACTION_MOVE)
        show(self.row_target, action == ACTION_MOVE)
        self.action_hint.Text = ACTION_HINTS.get(action, "")

        partition = self.partition
        if action == ACTION_CHANGE:
            self.value_label.Text = "New number:"
            self.New_Rebar_number.Text = str(self.index.next_free(partition)) if partition is not None else ""
        elif action == ACTION_SWAP:
            self.value_label.Text = "Swap with:"
            self.New_Rebar_number.Text = ""
        elif action == ACTION_SHIFT:
            self.value_label.Text = "Start at:"
            ints = self.index.int_numbers(partition) if partition is not None else []
            self.New_Rebar_number.Text = str(ints[0]) if ints else "1"
        elif action == ACTION_MOVE:
            n = len(self.move_ids)
            self.pick_info.Text = "{} bar{} selected".format(n, "" if n == 1 else "s") if n else \
                "None - pick bars or preselect them"

        self.apply_button.IsEnabled = not (action == ACTION_MOVE and not self.move_ids)
        self.ok_button.IsEnabled = self.apply_button.IsEnabled

    def set_status(self, text, ok=True):
        self.status_text.Text = text or ""
        self.status_text.Foreground = Brushes.SeaGreen if ok else Brushes.Firebrick

    # ---- events
    def on_partition_changed(self, sender, e):
        if not self._loading:
            self.set_status("")
            self.refresh()

    def on_action_changed(self, sender, e):
        if not self._loading:
            self.set_status("")
            self.update_action_ui()

    def on_apply(self, sender, e):
        self.do_apply()

    def on_ok(self, sender, e):
        if self.do_apply():
            self.Close()

    def on_close(self, sender, e):
        self.Close()

    def on_pick(self, sender, e):
        self.pick_requested = True
        self.state = self.get_state()
        self.Close()

    def on_select(self, sender, e):
        partition = self.partition
        if self.action == ACTION_MOVE:
            ids = self.move_ids
        elif self.action in (ACTION_CHANGE, ACTION_SWAP) and self.number is not None:
            ids = self.index.ids(partition, self.number)
            other = parse_int(self.New_Rebar_number.Text) if self.action == ACTION_SWAP else None
            if other is not None:
                ids = ids + self.index.ids(partition, other)
        else:
            ids = self.index.ids(partition)
        if not ids:
            self.set_status("Nothing to select.", ok=False)
            return
        self.select_ids = ids
        self.Close()

    # ---- apply
    def read_int(self, what):
        value = parse_int(self.New_Rebar_number.Text)
        if value is None or value < 1:
            raise ActionError("{} must be a whole number of 1 or more.".format(what))
        return value

    def selected_int_number(self):
        number = self.number
        if number is None:
            raise ActionError("Select a rebar number.")
        if not isinstance(number, int):
            raise ActionError("'{}' is not numeric and cannot be renumbered.".format(number))
        return number

    def do_apply(self):
        partition = self.partition
        action = self.action
        keep = None
        try:
            if partition is None:
                raise ActionError("Select a partition.")

            if action == ACTION_CHANGE:
                old = self.selected_int_number()
                new = self.read_int("New number")
                if new == old:
                    raise ActionError("New number is the same as the current number.")
                if new in self.index.numbers(partition):
                    count = len(self.index.ids(partition, new))
                    if not forms.alert("Number {} is already used by {} bar{} in this partition.\n\n"
                                       "Swap {} and {} instead?".format(
                                           self.index.fmt(new), count, "" if count == 1 else "s",
                                           self.index.fmt(old), self.index.fmt(new)),
                                       yes=True, no=True):
                        return False
                    message = op_swap(self.index, partition, old, new)
                else:
                    message = op_change(self.index, partition, old, new)
                keep = new

            elif action == ACTION_SWAP:
                a = self.selected_int_number()
                b = self.read_int("Swap with")
                if a == b:
                    raise ActionError("Choose two different numbers.")
                if b not in self.index.numbers(partition):
                    raise ActionError("Number {} is not used in this partition - use '{}' instead."
                                      .format(self.index.fmt(b), ACTION_CHANGE))
                message = op_swap(self.index, partition, a, b)
                keep = b

            elif action == ACTION_GAPS:
                message = op_gaps(self.index, partition)

            elif action == ACTION_SHIFT:
                message = op_shift(self.index, partition, self.read_int("Start number"))

            elif action == ACTION_MOVE:
                target = partition_key(self.target_partition.Text)
                if not self.move_ids:
                    raise ActionError("Pick or preselect the bars to move.")
                if not target and DEFAULT_PARTITION_LABEL not in (self.target_partition.Text or ""):
                    raise ActionError("Enter a target partition name.")
                message = op_move(self.index, self.move_ids, target)
                self.move_ids = []
                self.state["partition"] = target
            else:
                raise ActionError("Unknown action.")

        except ActionError as ex:
            self.set_status(str(ex), ok=False)
            return False
        except Exception as ex:
            self.set_status("Revit refused the change: {}".format(error_text(ex)), ok=False)
            return False

        # Rebuild the index from the model and keep the user's place.
        self._loading = True
        self.index = RebarIndex()
        self.partition_keys = self.index.partitions()
        self.Select_partition.ItemsSource = [partition_label(p) for p in self.partition_keys]
        show_partition = self.state["partition"] if action == ACTION_MOVE else partition
        if show_partition in self.partition_keys:
            self.Select_partition.SelectedIndex = self.partition_keys.index(show_partition)
        elif self.partition_keys:
            self.Select_partition.SelectedIndex = 0
        self._loading = False
        self.refresh(keep_number=keep)
        self.set_status(message, ok=True)
        return True


# --------------------------------------------------------------------------- main

def main():
    state = {}
    while True:
        form = RenumberForm(state)
        form.show_dialog()

        if form.pick_requested:
            state = form.state
            try:
                refs = uidoc.Selection.PickObjects(
                    ObjectType.Element, RebarFilter(),
                    "Pick rebar to move to another partition, then click Finish")
                state["move_ids"] = [r.ElementId for r in refs]
            except OperationCanceledException:
                pass
            state["action"] = ACTION_MOVE
            continue

        if form.select_ids:
            uidoc.Selection.SetElementIds(List[ElementId](form.select_ids))
        break


try:
    main()
except Exception as ex:
    forms.alert("Rebar Renumber failed:\n{}".format(error_text(ex)))
