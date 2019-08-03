"""
Utility functions for Specified and Param classes.
"""

import inspect

#
# These functions were derived from Param (PyViz) project code:
#
# https://github.com/pyviz/param/blob/master/param/parameterized.py#L147
#

def classlist(klass):
    """
    Return a list of the class hierarchy above (and including) the given class.
    """
    return inspect.getmro(klass)[::-1]

def get_all_slots(klass):
    """
    Return a list of unique names for slots defined in superclasses.

    Note: A subclass's __slots__ attribute does not contain slots defined in
    its superclass (the superclass' __slots__ end up as attributes of the
    subclass).
    """
    all_slots = []
    parent_param_classes = [c for c in classlist(klass)[1::]]
    for c in parent_param_classes:
        if hasattr(c, '__slots__'):
            all_slots += [s for s in c.__slots__ if s not in all_slots]
    return all_slots

def get_occupied_slots(instance):
    """
    Iterate through slot names of slots for which values have been set.

    Note: While a slot might be defined, if a value for that slot hasn't been
    set, then it's an AttributeError to request the slot's value.
    """
    for slot in get_all_slots(type(instance)):
        if hasattr(instance, slot):
            yield slot

def get_valued_slots(instance):
    """
    Iterate through slot names of slots for which nonNone values have been set.
    """
    for slot in get_occupied_slots(instance):
        if getattr(instance, slot) is not None:
            yield slot
