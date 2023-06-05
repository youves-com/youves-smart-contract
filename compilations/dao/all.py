import smartpy as sp

import utils.constants as Constants
from utils.fa2 import AdministrableFA2
from utils.viewer import Viewer

from contracts.dao.dao import DAOContract

sp.add_compilation_target("DAOContract", DAOContract())