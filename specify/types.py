"""
Parameter subclasses with different attributes, including associated widgets.
"""

__all__ = ('is_param', 'is_specified', 'ValueType', 'Widget', 'Range',
           'Slider', 'LogParam', 'LogSlider', 'Checkbox')


from .utils import classlist
from .param import Param


def is_param(obj):
    """
    Test whether an object is an instance of a Param subclass, but use string
    matching on the object's class' superclasses.

    This approach is invariant to module reloading unlike `type()` checking.
    """
    for klass in classlist(type(obj)):
        if klass.__name__ == 'Param':
            return True
    return False


def is_specified(obj):
    """
    Test whether an object is an instance of a Specified subclass, but use
    string matching on the object's class' superclasses.

    This approach is invariant to module reloading unlike `type()` checking.
    """
    for klass in classlist(type(obj)):
        if klass.__name__ in ('Specified', 'SpecifiedMetaclass'):
            return True
    return False


class ValueType(Param):

    """
    A parameter with a value whose type may be checked.
    """

    __slots__ = ['dtype']

    def __init__(self, default=None, dtype=None, **kwargs):
        super().__init__(default=default, **kwargs)
        self.dtype = dtype

    def check_type(self):
        """
        Return whether the current instance value is the correct type.
        """
        if self.owner is None: return False
        if not hasattr(self.owner, self.attrname): return False
        return type(getattr(self.owner, self.attrname)) is self.dtype


class Widget(Param):

    """
    Base class for parameters that may be controlled with widgets.
    """

    __slots__ = ['widget']

    def __init__(self, default=None, widget=None, **kwargs):
        super().__init__(default=default, **kwargs)
        self.widget = widget


class Range(Param):

    """
    A parameter with a range (lower and/or upper bounds).
    """

    __slots__ = ['start', 'end']

    def __init__(self, default=None, start=None, end=None, **kwargs):
        super().__init__(default=default, **kwargs)
        self.start = start
        self.end = end

    def check_range(self):
        """
        Return whether the current instance value is the correct range.
        """
        if self.owner is None: return False
        if not hasattr(self.owner, self.attrname): return False
        val = getattr(self.owner, self.attrname)
        if self.start is not None and val < self.start:
            return False
        if self.end is not None and val > self.end:
            return False
        return True


class Slider(Range):

    """
    A parameter with a range and step size for a slider widget.
    """

    __slots__ = ['step', 'widget']

    def __init__(self, default=None, step=None, **kwargs):
        super().__init__(default=default, **kwargs)
        self.step = step
        self.widget = 'slider'


class LogParam(Param):

    """
    A parameter that represents the base-10 exponent of an underlying value.
    """

    pass


class LogSlider(Slider):

    """
    A slider widget that controls a log-scale value.
    """

    __slots__ = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.widget = 'logslider'


class Checkbox(Widget):

    """
    A checkbox widget that controls a boolean parameter.
    """

    __slots__ = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.widget = 'checkbox'
