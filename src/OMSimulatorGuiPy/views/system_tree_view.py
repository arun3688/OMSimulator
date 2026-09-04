# This file is part of OpenModelica.
#
# Copyright (c) 1998-2026, Open Source Modelica Consortium (OSMC),
# c/o Linköpings universitet, Department of Computer and Information Science,
# SE-58183 Linköping, Sweden.
#
# All rights reserved.
#
# THIS PROGRAM IS PROVIDED UNDER THE TERMS OF AGPL VERSION 3 LICENSE OR
# THIS OSMC PUBLIC LICENSE (OSMC-PL) VERSION 1.8.
# ANY USE, REPRODUCTION OR DISTRIBUTION OF THIS PROGRAM CONSTITUTES
# RECIPIENT'S ACCEPTANCE OF THE OSMC PUBLIC LICENSE OR THE GNU AGPL
# VERSION 3, ACCORDING TO RECIPIENTS CHOICE.
#
# The OpenModelica software and the OSMC (Open Source Modelica Consortium)
# Public License (OSMC-PL) are obtained from OSMC, either from the above
# address, from the URLs:
# http://www.openmodelica.org or
# https://github.com/OpenModelica/ or
# http://www.ida.liu.se/projects/OpenModelica,
# and in the OpenModelica distribution.
#
# GNU AGPL version 3 is obtained from:
# https://www.gnu.org/licenses/licenses.html#GPL
#
# This program is distributed WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE, EXCEPT AS EXPRESSLY SET FORTH
# IN THE BY RECIPIENT SELECTED SUBSIDIARY LICENSE CONDITIONS OF OSMC-PL.
#
# See the full OSMC Public License conditions for more details.

'''QTreeView subclass for the system tree.

Context menus emit request signals carrying the target TreeNode; MainWindow
owns the actual System/SSP API calls and the dialogs, keeping this view
free of editing-API specifics.
'''

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QTreeView

from OMSimulatorGui.models.system_tree_model import (
    KIND_COMPONENT,
    KIND_COMPONENT_TABLE,
    KIND_CONNECTOR,
    KIND_SYSTEM,
)


class SystemTreeView(QTreeView):
  addSystemRequested = Signal(object)     # TreeNode: parent system to add into
  addComponentRequested = Signal(object)  # TreeNode: parent system to add into
  addConnectorRequested = Signal(object)  # TreeNode: parent system to add into
  deleteRequested = Signal(object)        # TreeNode: element/connector to delete
  renameRequested = Signal(object)        # TreeNode: element to rename

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setHeaderHidden(False)
    self.setUniformRowHeights(True)
    self.setExpandsOnDoubleClick(True)
    self.setContextMenuPolicy(self.contextMenuPolicy().CustomContextMenu)
    self.customContextMenuRequested.connect(self._onContextMenuRequested)

  def _onContextMenuRequested(self, pos) -> None:
    index = self.indexAt(pos)
    if not index.isValid():
      return
    node = self.model().nodeFromIndex(index)
    if node is None:
      return

    menu = QMenu(self)

    if node.kind == KIND_SYSTEM:
      menu.addAction('Add System...', lambda: self.addSystemRequested.emit(node))
      menu.addAction('Add Component...', lambda: self.addComponentRequested.emit(node))
      menu.addAction('Add Connector...', lambda: self.addConnectorRequested.emit(node))
      menu.addSeparator()
      menu.addAction('Rename...', lambda: self.renameRequested.emit(node))
      deleteAction = menu.addAction('Delete', lambda: self.deleteRequested.emit(node))
      deleteAction.setEnabled(not self.model().isTopLevelSystem(node))
    elif node.kind in (KIND_COMPONENT, KIND_COMPONENT_TABLE):
      menu.addAction('Rename...', lambda: self.renameRequested.emit(node))
      menu.addAction('Delete', lambda: self.deleteRequested.emit(node))
    elif node.kind == KIND_CONNECTOR:
      menu.addAction('Delete', lambda: self.deleteRequested.emit(node))
    else:
      return

    menu.exec(self.viewport().mapToGlobal(pos))
