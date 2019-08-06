"""
Base class for inheritable parameters.
"""

import copy

from pouty.console import printf, debug, dimgray
from roto.dicts import hilite, midlite, lolite

from .utils import get_all_slots, get_occupied_slots, get_valued_slots


class Param(object):

    """
    A class attribute instance defining properties of inheritable values.
    """

    __slots__ = ['name', 'default', 'units', 'doc', 'constant', 'owner',
                 'attrname']

    def __init__(self, default=None, units=None, doc=None, constant=False):
        self.name = None
        self.default = default
        self.units = units
        self.doc = doc
        self.constant = constant
        self.owner = None
        self.attrname = None

    def __repr__(self):
        indent = ' '*4
        r = f'{self.__class__.__name__}('
        empty = True
        for a in get_valued_slots(self):
            if a in ('owner', 'name', 'constant', 'attrname'):
                continue
            r += f'{a}={getattr(self, a)!r}, '
            empty = False
        if empty:
            return r + ')'
        return r[:-2] + ')'

    def __str__(self):
        return self.pprint()

    def pprint(self, indent=4):
        """
        Print a highlighted list of parameter properties with current values.
        """
        all_slots = get_all_slots(type(self))
        prefix = ' '*indent
        r = midlite(f'{self.name}(\n')
        comma = midlite(',')
        for k in all_slots:
            if hasattr(self, k):
                v = getattr(self, k)
                if v is None:
                    l = dimgray(f'{k} = {v!r},')
                else:
                    l = hilite(k) + midlite(' = ') + lolite(f'{v!r}') + comma
            else:
                l = dimgray(f'{k} = <unset slot>,')
            lines = l.split('\n')
            for line in lines:
                r += prefix + line + '\n'
        return r + midlite(')') + '\n'

    def _set_names(self, name):
        """
        Set public and internal names based on class-given name.

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L878
        """
        if None not in (self.name, self.owner) and name != self.name:
            raise AttributeError(f'Trying to assign name {name!r} to Param '
                                 f'{self.name!r}, which was already assigned '
                                 f'by class {self.owner!r}. Param instances '
                                  'should only be owned by a single class.')
        self.name = name
        self.attrname = f'_{name}_specified_value'
        debug(f'set names: {self.name!r} and {self.attrname!r}')

    def __get__(self, obj, cls):
        """
        Return the Parameter value (default for classes, value for instances).

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L768
        """
        if obj is None:
            if self.default is None:
                raise TypeError(f'No default value set for {self.name!r}')
            return self.default
        return obj.__dict__.get(self.attrname, self.default)

    def __set__(self, obj, value):
        """
        Set the Param value on the Specified instance.

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L791
        """
        if obj is None:
            self.default = value
            return
        if self.constant and obj._initialized:
            raise TypeError(f'Cannot modify constant parameter {self.name!r}')
        if value == obj.__dict__[self.attrname]:
            return

        obj.__dict__[self.attrname] = value

        if hasattr(obj, '_widgets') and self.name in obj._widgets:
            widget = obj._widgets[self.name]
            if widget.value != value:
                widget.value = value
                # widget.param.trigger('value')
                # debug(f'updated widget {self.name!r} to {value!r}')

    def __getstate__(self):
        state = {}
        for slot in get_occupied_slots(self):
            state[slot] = getattr(self, slot)
        return state

    def __setstate__(self, state):
        for k, v in state.items():
            setattr(self, k, v)
