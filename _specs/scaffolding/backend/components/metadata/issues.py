from backend.components.metadata.schema import Schema
from backend.components.metadata.concerns import Concern
from backend.components.metadata.typos import Typo
from backend.components.metadata.problems import Problem
from backend.components.metadata.blanks import Blank

metadata_map = {'schema':Schema, 'blank':Blank, 'concern':Concern, 'problem':Problem, 'typo':Typo}
