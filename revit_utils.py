import traceback

import Autodesk.Revit.DB as DB


def resolve_reference(ref, doc):
    """
    Try multiple safe ways to get an Element from a Reference.
    Returns a tuple (element_or_None, message_str).
    Call this inside Revit where `doc` is a Document.
    """
    if ref is None:
        return None, "reference is None"

    # common quick attempt
    try:
        elem = doc.GetElement(ref)
        if elem is not None:
            return elem, "resolved via doc.GetElement(ref)"
    except Exception:
        # swallow and try other strategies
        pass

    # try using ElementId stored on Reference
    try:
        eid = getattr(ref, "ElementId", None)
        if eid is not None:
            elem = doc.GetElement(eid)
            if elem is not None:
                return elem, "resolved via doc.GetElement(ref.ElementId)"
            # if ElementId is an int-like value, try constructing ElementId
            try:
                intval = int(getattr(eid, "IntegerValue", eid))
                elem = doc.GetElement(DB.ElementId(intval))
                if elem is not None:
                    return elem, "resolved via ElementId(IntegerValue)"
            except Exception:
                pass
    except Exception:
        pass

    # Try stable representation (useful for linked docs), if available
    try:
        sr = getattr(ref, "ConvertToStableRepresentation", None)
        if callable(sr):
            stable = ref.ConvertToStableRepresentation(doc)
            if stable:
                return None, "has stable representation: {}".format(stable)
    except Exception:
        pass

    # Last-resort: dump minimal ref info for debugging
    try:
        ref_type = type(ref).__name__
        ref_attrs = []
        for a in ("HostElementId", "LinkedElementId", "LinkedElement", "LinkedElementId", "GlobalOffset"):
            if hasattr(ref, a):
                ref_attrs.append(f"{a}={getattr(ref, a)}")
        msg = "unable to resolve reference; type={}, attrs=[{}]".format(ref_type, ", ".join(ref_attrs))
    except Exception:
        msg = "unable to resolve reference; and failed to introspect"
    return None, msg


def resolve_references(refs, doc, limit=None):
    """
    Iterate over an iterable of Reference objects and yield (index, ref, element, message).
    Use this to produce clearer logging than repeated 'error finding' messages.
    """
    count = 0
    for i, ref in enumerate(refs):
        if limit is not None and count >= limit:
            break
        try:
            elem, msg = resolve_reference(ref, doc)
            yield i, ref, elem, msg
        except Exception:
            tb = traceback.format_exc()
            yield i, ref, None, "exception during resolve: " + tb
        count += 1
