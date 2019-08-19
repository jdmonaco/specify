"""
Base class for objects with inheritable parameter specifications.
"""

import copy

try:
    import panel as pn
except ImportError:
    print('Warning: install `panel` to use interactive dashboards.')

from toolbox.numpy import log10
from pouty.anybar import AnyBar
from pouty.console import debug, ConsolePrinter, orange
from roto.dicts import AttrDict, Tree, hilite, midlite, lolite
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
                        debug(f'copied {key!r} ancestor from {superclass!r} '
                              f'as {p!r}')
                    else:
                        specs[key] = value
                        debug(f'found {key!r} ancestor in {superclass!r}')

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

    def _add_param(cls, pname, param, default=None):
        """
        Add a Param object to this class instance.
        """
        if pname in cls.__dict__:
            raise ValueError(f'Param {pname!r} conflicts with existing '
                             f'attribute with value {cls.__dict__[pname]!r}')

        param._set_names(pname)
        cls.__param_inheritance(pname, param)
        if default is not None:
            param.default = copy.deepcopy(default)
        type.__setattr__(cls, pname, param)
        cls.spec[pname] = param
        debug(f'added Param {pname!r} with value {param!r}')

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
        # Find out if there's a Parameter with the given `name` as a class
        # attribute of this class. If not, `parameter` is None.
        parameter, owner = cls.get_param_descriptor(name)

        if parameter and not is_param(value):
            if owner != cls:
                parameter = copy.copy(parameter)
                parameter.owner = cls
                type.__setattr__(cls, name, parameter)
                cls.spec[name] = parameter
            debug(f'{cls!r}.__setattr__ for value {value!r}')
            cls.__dict__[name].__set__(None, value)

        else:
            debug(f'{cls!r}.__setattr__ for Param {value!r}')
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

    def __init__(self, *, spec_produce=False, spec_consume=True, **kwargs):
        """
        Class-scope parameter default values are instantiated in the object.
        """
        self._initialized = False
        self._widgets = {}
        self._watchers = {}
        self.spec_local = Specs()
        prefix = kwargs.get('name', 'specified')

        # Build list from Specified hierarchy of Param names to instantiate
        to_instantiate = {}
        for cls in classlist(type(self)):
            if not is_specified(cls):
                continue
            for name, value in vars(cls).items():
                if is_param(value) and name != 'name':
                    to_instantiate[name] = value

        # Set the internal instance attribute values to copied Param defaults
        for param in to_instantiate.values():
            key = param.attrname
            new_value_from_default = copy.deepcopy(param.default)
            self.__dict__[key] = new_value_from_default
            debug(f'init {key!r} to default {new_value_from_default!r}',
                  prefix=prefix)

        # Set the value of keyword arguments
        to_consume = []
        for key, value in kwargs.items():
            if key == '_spec_class' and value != self.__class__.__name__:
                debug(f'serialized type name {value!r} does not match',
                      f'class {self.klass!r}', prefix=prefix)
                continue
            if key not in self.spec or value is None:
                debug(f'skipping key {key!r} with value {value!r}')
                continue
            setattr(self, key, value)
            to_consume.append(key)
            debug(f'init {key!r} to {value!r} from kwargs', prefix=prefix)

        # From keyword options, either consume kwargs for Param values that
        # were set and/or produce kwargs for all specs (`spec_produce=True`) or
        # a subset of specs (`spec_produce=('spec1',...)`).
        if spec_consume:
            for key in to_consume:
                del kwargs[key]
        if spec_produce:
            if spec_produce == True:
                to_produce = tuple(self.spec.keys())
            else:
                to_produce = tuple(spec_produce)
            for key in to_produce:
                if key in kwargs:
                    continue
                kwargs[key] = getattr(self, key)

        super().__init__(**kwargs)
        self._initialized = True

    def __str__(self):
        indent = 4
        prefix = ' '*indent
        r = midlite(f'{self.name}(')
        if len(self.spec):
            r += '\n'
        for k, param in self.params():
            dflt = param.default
            val = getattr(self, param.attrname)
            l = hilite(f'{k}') + midlite(' = ') + lolite(f'{val!r}')
            if val != dflt:
                l += orange(f' [default: {dflt!r}]')
            lines = l.split('\n')
            for line in lines:
                r += prefix + line + '\n'
        return r + midlite(')') + '\n'

    def __contains__(self, name):
        return name in self.spec or name in self.spec_local

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __iter__(self):
        for key, _ in self.params():
            yield key

    def add_param(self, pname, param, *, value=None):
        """
        Add a instance-local Param object to this Specified instance.
        """
        cls = self.__class__
        if pname in cls.__dict__:
            self.out(f'Instance Param {pname!r} will override class Param with '
                     f'value {cls.__dict__[pname]!r}', warning=True)
        if pname in self.__dict__:
            self.out(f'Instance Param {pname!r} conflicts with instance Param '
                     f'with value {self.__dict__[pname]!r}', error=True)
            raise ValueError('instance Param conflict')

        param._set_names(pname)
        param.owner = self
        param.default = copy.deepcopy(param.default)
        self.spec_local[pname] = param
        type.__setattr__(self.__class__, pname, param) # install the descriptor

        if value is not None:
            self.__dict__[param.attrname] = copy.deepcopy(value)
        elif param.attrname in self.__dict__:
            pass
        else:
            self.__dict__[param.attrname] = copy.deepcopy(param.default)

        self.debug(f'added instance Param {pname!r} with value {param!r}')

    def params(self):
        """
        Iterate over (name, Param object) tuples for all parameters.
        """
        for name, p in self.spec.items():
            yield (name, p)
        for name, p in self.spec_local.items():
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
        for name, param in self.params():
            yield (name, param.default)

    def update(self, *args, **kwargs):
        """
        Update parameter values from a positional mapping or keyword arguments.
        """
        assert len(args) < 2, 'up to 1 positional argument allowed'
        d = {}
        if args: d.update(args[0])
        if kwargs: d.update(kwargs)
        for key, value in d.items():
            setattr(self, key, value)

    def copy(self, **kwargs):
        """
        Return new instance with same spec values, but with kwargs overrides.
        """
        specvalues = dict(self.items())
        for key in specvalues.keys():
            if key in kwargs:
                specvalues[key] = kwargs[key]
        newobj = self.__class__(**specvalues)
        return newobj

    def reset(self):
        """
        Reset parameters to default values.
        """
        Specified.update(self, dict(self.defaults()))

    def get_widgets(self, include=None, exclude=None):
        """
        Return a tuple of Panel widget objects for Param values.

        Note: Keyword arguments `include` and `exclude` should be tuples or
        lists of Param names.
        """
        # Prune list of attr names that do not correspond to known Params with
        # a non-None widget attribute
        names = list(self) if include is None else list(include)
        to_remove = []
        for n in names:
            if n in self:
                if n in self.spec and hasattr(self.spec[n], 'widget') and \
                        self.spec[n].widget is not None:
                    continue
                if n in self.spec_local and \
                        hasattr(self.spec_local[n], 'widget') and \
                            self.spec_local[n].widget is not None:
                    continue
            to_remove.append(n)
            self.debug(f'ignoring Param {n!r} which has no widget')
        for n in to_remove:
            names.remove(n)

        # If exclusions were specified, remove those items from the list
        if exclude is not None:
            for exc in exclude:
                if exc in names:
                    names.remove(exc)
                    self.debug(f'excluding Param {n!r} from widget list')

        # Remove handles to old widgets that are about to be replaced
        to_remove = list(filter(lambda n: n in names, self._widgets.keys()))
        for name in to_remove:
            del self._widgets[name]

        if not names:
            self.out('Empty list of widget names after filters', warning=True)
            return ()

        # Construct the widgets
        new_widgets = []
        for name in sorted(names):
            if name in self.spec:
                p = self.spec[name]
            elif name in self.spec_local:
                p = self.spec_local[name]
            if p.widget in ('slider', 'logslider'):
                value = getattr(self, name)
                slider = pn.widgets.FloatSlider(
                        name            = p.name,
                        value           = value,
                        start           = p.start,
                        end             = p.end,
                        step            = p.step,
                        callback_policy = 'mouseup',
                )
                self._widgets[name] = slider
                new_widgets.append(slider)
                self.debug(f'created {p.widget} {slider.name!r} with value '
                           f'{slider.value!r}')
            else:
                self.out(f'Widget type {p.widget!r} not currently supported',
                         warning=True)

        # Define an event-based callback function
        prev_event = None
        def callback(*events):
            nonlocal prev_event
            AnyBar.toggle()
            for event in events:
                widget = event.obj
                new_value = event.new
                if (widget, new_value) == prev_event:
                    continue
                setattr(self, widget.name, new_value)
                prev_event = (widget, new_value)
                self.debug(f'widget {widget.name!r} {event.type} from '
                           f'{event.old:g} to {new_value:g}')

        # Register the callback with each of the sliders
        for name, widget in self._widgets.items():
            self._watchers[name] = widget.param.watch(callback, 'value')

        return tuple(new_widgets)

    def unlink_widgets(self, *names):
        """
        Remove callbacks from Panel widget objects and then remove the widgets.
        """
        names = list(self) if not names else list(names)
        for n in names:
            if n in self._widgets and self._widgets[n] is not None:
                widget = self._widgets[n]
                widget.param.unwatch(self._watchers[n])
                del self._widgets[name]
                self.debug(f'unlinked and removed {n!r} widget')

    def to_dict(self, subtree=None, T=None):
        """
        Return a copy of the spec as a nested dict object.
        """
        if T is None:
            T = Tree()
        if subtree is None:
            subtree = self
        for name, value in subtree.items():
            if hasattr(value, 'items'):
                self.to_dict(value, T[name])
                continue
            T[name] = value
        if is_specified(subtree):
            T['_spec_class'] = self.klass
        return T
