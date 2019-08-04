"""
Base class for objects with inheritable parameter specifications.
"""

import copy

try:
    import panel as pn
except ImportError:
    print('Warning: install `panel` to use interactive dashboards.')

from pouty.anybar import AnyBar
from pouty.console import debug, ConsolePrinter, snow as hilite
from roto.dicts import AttrDict, Tree
from tenko.base import TenkoObject

from .types import is_param, is_specified
from .utils import classlist
from .param import Param


class Specs(AttrDict):
    pass


class SpecifiedMetaclass(type):

    """
    From the Param project:

    The metaclass overrides type.__setattr__ to allow us to set
    Parameter values on classes without overwriting the attribute
    descriptor.  That is, for a Parameterized class of type X with a
    Parameter y, the user can type X.y=3, which sets the default value
    of Parameter y to be 3, rather than overwriting y with the
    constant value 3 (and thereby losing all other info about that
    Parameter, such as the doc string, bounds, etc.).

    Based on:
    https://github.com/pyviz/param/blob/master/param/parameterized.py#L1848
    """

    def __new__(metacls, name, bases, clsdict):
        """
        For each class, create a class attribute `spec` object that holds
        references to all Param objects that will be accessible to the class
        and its instances across the inheritance hierarchy.
        """
        specs = clsdict['spec'] = Specs()
        for base in bases:
            for superclass in classlist(base)[::-1]:
                if not isinstance(superclass, metacls):
                    continue
                for key, value in vars(superclass).items():
                    if key == 'name': continue
                    if not is_param(value):
                        continue
                    if key in clsdict:
                        clsvalue = clsdict[key]
                        if is_param(clsvalue):
                            continue
                        p = type(value)(default=copy.deepcopy(clsvalue))
                        specs[key] = clsdict[key] = p
                        debug(f'copied ancestor for {key!r} in '
                              f'{superclass!r} as {p!r}')
                    else:
                        specs[key] = value
                        debug(f'found ancestor {key!r} in {superclass!r}')

        return super().__new__(metacls, name, bases, clsdict)

    def __init__(cls, name, bases, clsdict):
        """
        Initializes all Params in the class __dict__ by looking up appropriate
        default values (__param_inheritance) and setting both the 'external'
        descriptor name and 'internal' attribute name (_set_names).
        """
        type.__init__(cls, name, bases, clsdict)
        cls.name = name

        # Initialize all Params by setting names and inheriting properties
        for pname, param in clsdict.items():
            if not is_param(param) or pname == 'name':
                continue
            param._set_names(pname)
            cls.__param_inheritance(pname, param)
            cls.spec[pname] = param
            debug(f'initialized Param {pname!r} to {param!r}')

    def __param_inheritance(cls, pname, param):
        """
        Look for Param values in superclasses of the Specified class.

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L2024
        """
        # Get all relevant slots in superclasses of this parameter
        slots = {}
        for p_class in classlist(type(param))[1::]:
            slots.update(dict.fromkeys(p_class.__slots__))

        # Set the owner slot as an instance attribute and prevent inheriting it
        setattr(param, 'owner', cls)
        del slots['owner']

        # For each slot, search for the nearest superclass with a Param object
        # with the same name and a non-None value for the slot. If found, set
        # the Param object's slot to the new value. This ensures that Param
        # properties will propagate through the hierarchy of Specified classes.

        for slot in slots.keys():
            superclasses = iter(classlist(cls)[::-1])

            while getattr(param, slot) is None:
                try:
                    param_super_class = next(superclasses)
                except StopIteration:
                    break

                ancestor = param_super_class.__dict__.get(pname)
                if ancestor is not None and hasattr(ancestor, slot):
                    setattr(param, slot, getattr(ancestor, slot))

    def __setattr__(cls, name, value):
        """
        Implements `self.name = value` in a way that supports Param[eters].
        If there is already a descriptor named name, and that
        descriptor is a Parameter, and the new value is *not* a Parameter,
        then call that Parameter's __set__ method with the specified value.

        In all other cases set the attribute normally (i.e., overwrite the
        descriptor). If the new value is a Parameter, once it has been set we
        make sure that the value is inherited from Parameterized superclasses
        as described in __param_inheritance().

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L1973
        """
        # Find out if there's a Parameter called name as a class attribute
        # of this class. If not, parameter is None.
        parameter, owner = cls.get_param_descriptor(name)

        if parameter and not is_param(value):
            if owner != cls:
                parameter = copy.copy(parameter)
                parameter.owner = cls
                type.__setattr__(cls, name, parameter)
                cls.spec[name] = parameter
            cls.__dict__[name].__set__(None, value)

        else:
            type.__setattr__(cls, name, value)

            if is_param(value):
                cls.__param_inheritance(name, value)
                cls.spec[name] = value
            else:
                if not (name.startswith('_') or \
                        name in ('name', 'spec')):
                    debug('setting non-Param class attribute '
                         f'{cls.__name__}.{name} to value {value!r}')

    def get_param_descriptor(cls, pname):
        """
        Goes up the class hierarchy (starting from the current class) looking
        for a Parameter class attribute `pname`. As soon as one is found as
        a class attribute, that Parameter is returned along with the class in
        which it is declared.

        Based on:
        https://github.com/pyviz/param/blob/master/param/parameterized.py#L2098
        """
        classes = classlist(cls)
        for c in classes[::-1]:
            attribute = c.__dict__.get(pname)
            if is_param(attribute):
                return attribute, c
        return None, None


class Specified(TenkoObject, metaclass=SpecifiedMetaclass):

    """
    Self-validating attribute stores of restricted key-value sets.
    """

    def __init__(self, **kwargs):
        """
        Class-scope parameter default values are instantiated in the object.
        """
        super().__init__()
        self._initialized = False
        self._widgets = {}
        self._watchers = {}

        # Build list from Specified hierarchy of Param names to instantiate
        to_instantiate = {}
        for cls in classlist(type(self)):
            if not is_specified(cls):
                continue
            for name, value in vars(cls).items():
                if is_param(value) and name != 'name':
                    to_instantiate[name] = value
                    self.spec[name] = value

        # Set the internal instance attribute values to copied Param defaults
        for param in to_instantiate.values():
            key = param.attrname
            new_value_from_default = copy.deepcopy(param.default)
            self.__dict__[key] = new_value_from_default
            self.debug(f'init {key!r} to default {new_value_from_default!r}')

        # Set the value of keyword arguments
        for key, value in kwargs.items():
            if key == '_spec_class' and value != self.klass:
                self.out(f'Serialized type name {value!r} does not match',
                         f'class {self.klass!r}', warning=True)
                continue
            descriptor, _ = type(self).get_param_descriptor(key)
            if not descriptor:
                self.out(f'Non-Param attribute {key!r} set to {value!r}',
                         warning=True)
            setattr(self, key, value)
            debug(f'init {key!r} to {value!r} from kwargs')

        self._initialized = True

    def __str__(self):
        indent = ' '*4
        r = f'{self.name}('
        if len(self.spec):
            r += '\n'
        for k, param in self.items():
            dflt = param.default
            val = getattr(self, param.attrname)
            if val == dflt:
                line = f'{k} = {val!r}'
            else:
                line = hilite(f'{k} = {val!r} [default: {dflt!r}]')
            lines = line.split('\n')
            for line in lines:
                r += indent + line + '\n'
        return r + ')'

    def __contains__(self, name):
        return name in self.spec

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __iter__(self):
        return iter(self.spec.keys())

    def params(self):
        """
        Iterate over (name, Param object) tuples for all parameters.
        """
        for name, p in self.spec.items():
            yield (name, p)

    def items(self):
        """
        Iterate over (name, value) tuples for all current parameter values.
        """
        for name in self:
            yield (name, getattr(self, name))

    def defaults(self):
        """
        Iterate over (name, default) tuples for all parameters.
        """
        for name, p in self.params():
            yield (name, p.default)

    def update(self, **kwargs):
        """
        Update parameter values from keyword arguments.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)

    def reset(self):
        """
        Reset parameters to default values.
        """
        self.update(**dict(self.defaults()))

    def get_widgets(self, *names, exclude=None):
        """
        Return a tuple of Panel widget objects for Param values.
        """
        # Use arguments or gather full list of parameter names with widgets
        if names:
            names = list(filter(lambda n: n in self, names))
        else:
            names = [name for name, p in self.params() if hasattr(p, 'widget')
                     and p.widget is not None]

        # If exclusions were specified, remove those items from the list
        if exclude is not None:
            exclude = tuple((exclude,))
            for exc in exclude:
                if exc in names:
                    names.remove(exc)

        # Remove handles to old widgets that are about to be replaced
        for name in self._widgets.keys():
            if name in names:
                del self._widgets[name]

        if not names:
            self.out('Empty list of names after exclusions', warning=True)
            return ()

        # Construct the widgets
        new_widgets = []
        for name in names:
            p = self.spec[name]
            if p.widget == 'slider':
                slider = pn.widgets.FloatSlider(
                        name            = p.name,
                        value           = getattr(self, name),
                        start           = p.start,
                        end             = p.end,
                        step            = p.step,
                        callback_policy = 'mouseup',
                )
                self._widgets[name] = slider
                new_widgets.append(slider)
            else:
                self.out('Widget type {p.widget!r} not currently supported',
                         warning=True)

        # Define an event-based callback function
        def callback(*events):
            AnyBar.toggle()
            for event in events:
                setattr(self, event.obj.name, event.new)

        # Register the callback with each of the sliders
        for name, widget in self._widgets.items():
            self._watchers[name] = widget.param.watch(callback, 'value')

        self.debug('created {} new widgets', len(new_widgets))
        return tuple(new_widgets)

    def unlink_widgets(self):
        """
        Remove callbacks from Panel widget objects.
        """
        for name, widget in self._widgets.items():
            widget.param.unwatch(self._watchers[name])

    def to_dict(self, subtree=None, T=None):
        """
        Return a copy of the spec as a nested dict object.
        """
        if T is None:
            T = Tree()
        if subtree is None:
            subtree = self.spec
        for name, value in subtree.items():
            if is_specified(subtree):
                value = subtree[name]
            if hasattr(value, 'items') or has:
                self.to_dict(value, T[name])
                continue
            if is_param(value):
                T[name] = getattr(self, value.name)
            else:
                T[name] = value
        if is_specified(subtree):
            T['_spec_class'] = self.klass
        return T
