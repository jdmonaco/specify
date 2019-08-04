"""
Base class for inheritable parameters.
"""

import copy

from pouty.console import printf, debug

from .utils import get_all_slots, get_occupied_slots, get_valued_slots


hilite_line = lambda line: printf(line + '\n', c='seafoam')
dim_line = lambda line: printf(line + '\n', c='dimgray')


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

    def __str__(self):
        indent = ' '*4
        r = f'{self.__class__.__name__}(\n'
        for a in get_valued_slots(self):
            if a in ('owner', 'name', 'constant', 'attrname'):
                continue
            lines = f'{a} = {getattr(self, a)!r},'.split('\n')
            for line in lines:
                r += indent + line + '\n'
        return r + ')'

    def __repr__(self):
        return str(self)

    def pprint(self, hilite=True):
        """
        Print a highlighted list of parameter properties with current values.
        """
        all_slots = get_all_slots(type(self))
        col = max(map(len, all_slots))
        for slot in all_slots:
            line = '    - ' + slot.ljust(col) + ' = '
            val = None
            if hasattr(self, slot):
                val = getattr(self, slot)
                line += repr(val)
            else:
                line += '<unset slot>'
            if hilite:
                if val is None:
                    dim_line(line)
                else:
                    hilite_line(line)
            else:
                print(line)

    def update(self, p):
        """
        Update slots with values from another Param instance.
        """
        for slot in get_all_slots(type(self)):
            if hasattr(p, slot):
                setattr(self, slot, getattr(p, slot))

    def copy(self):
        """
        Create a shallow copy of this Param instance.
        """
        newparam = type(self)(**{slot:copy.copy(getattr(self, slot))
                                 for slot in get_all_slots(type(self))
                                 if slot != 'owner'})
        newparam.owner = self.owner
        return newparam

    @classmethod
    def _attrname(cls, name):
        """
        Name mangling for instance attributes of the parameter's current value.
        """
        return f'_{name}_specified_value'

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
        self.attrname = type(self)._attrname(name)
        debug(f'set names: {self.name!r} and {self.attrname!r}')

    def __get__(self, obj, type_=None):
        """
        Return the Parameter value (default for classes, value for instances).

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L768
        """
        if obj is None:
            if self.default is None:
                raise TypeError(f'No default value set for {self.name!r}')
            result = self.default
        else:
            result = obj.__dict__.get(self.attrname, self.default)
        return result

    def __set__(self, obj, value):
        """
        Set the Param value on the Specified instance.

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L791
        """
        if self.constant:
            if obj is None:
                self.default = value
            elif not obj._initialized:
                oldval = obj.__dict__[self.attrname]
                if oldval != value:
                    obj.debug(f'set {self.name!r} from {oldval!r} to '
                              f'{value!r}')
                obj.__dict__[self.attrname] = value
            else:
                raise TypeError(f'Constant parameter {self.name!r} cannot be '
                                 'modified')
        else:
            if obj is None:
                self.default = value
            else:
                oldval = obj.__dict__[self.attrname]
                if oldval != value:
                    obj.debug(f'set {self.name!r} from {oldval!r} to '
                              f'{value!r}')
                obj.__dict__[self.attrname] = value

        if hasattr(obj, '_widgets') and self.name in obj._widgets:
            widget = obj._widgets[self.name]
            if widget.value != value:
                widget.value = value
                widget.param.trigger('value')
                obj.debug(f'updated widget {self.name!r} to {value!r}')

    def __getstate__(self):
        state = {}
        for slot in get_occupied_slots(self):
            state[slot] = getattr(self, slot)
        return state

    def __setstate__(self, state):
        for k, v in state.items():
            setattr(self, k, v)
