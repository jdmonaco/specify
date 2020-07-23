"""
Test inheritance, etc., for the Param and Specified classes.
"""

from specify import Specified, Param
from specify.types import Slider


class ExampleModel(Specified):

    alpha = Param(default=1.0, units='a.u.')
    beta = Slider(default=0.5, start=0.0, end=10.0, step=1, units='MHz')

    def __init__(self, **keyvalues):
        super(ExampleModel, self).__init__(**keyvalues)
        self.out('Initialized!')
