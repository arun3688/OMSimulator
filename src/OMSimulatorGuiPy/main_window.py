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

'''MainWindow: owns the one live SSP instance and wires it to the views.

M1: File > Open loads an existing .ssp and shows its root System in a
read-only tree (the tree always shows the full nested hierarchy).
M2: adds a read-only diagram canvas showing one System level at a time,
with its own drill-down/"Up" navigation, kept in sync with the tree
selection.
M3: File > New, Save As, and structured editing (add/delete/rename systems,
components, connectors) via the tree's context menu. Every edit goes
through SSP-level methods (never System directly) so resource registration
(addResource) and connector auto-population from FMU modelDescription stay
correct; every edit is followed by one shared _onModelChanged() refresh so
the tree and diagram never drift apart.
Simulation and the XML viewer land in later milestones (see the plan this
was built from).
'''

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
)

from OMSimulator import SSP, Connector, CRef, System

from OMSimulatorGui.dialogs.add_connector_dialog import AddConnectorDialog
from OMSimulatorGui.dialogs.add_submodel_dialog import AddSubModelDialog
from OMSimulatorGui.dialogs.add_system_dialog import AddSystemDialog
from OMSimulatorGui.dialogs.create_model_dialog import CreateModelDialog
from OMSimulatorGui.dialogs.element_properties_dialog import ElementPropertiesDialog
from OMSimulatorGui.dialogs.simulation_settings_dialog import SimulationSettingsDialog
from OMSimulatorGui.models.system_tree_model import (
    KIND_COMPONENT,
    KIND_COMPONENT_TABLE,
    KIND_CONNECTOR,
    KIND_MODEL,
    KIND_SYSTEM,
    SystemTreeModel,
)
from OMSimulatorGui.views.diagram_canvas import DiagramView
from OMSimulatorGui.views.system_tree_view import SystemTreeView


class _RootBoxProxy:
  '''Represents the real root System as a single box at the model level,
  without writing its position/size into the real System's own
  elementgeometry -- a root system has no parent to be positioned within,
  so doing that would leak a meaningless <ssd:ElementGeometry> onto the
  <ssd:System> root element itself when the file is exported. The box's
  position/size lives on the proxy instead (session-local: it resets to a
  fallback layout on the next file open, since it was never real data to
  begin with).

  DiagramView resolves double-clicks on a box back to the real system via
  duck-typing (`getattr(item.element, 'system', item.element)`), so this
  needs no special-casing anywhere else.'''

  def __init__(self, system: System):
    self.system = system
    self.elementgeometry = None

  @property
  def name(self):
    return self.system.name

  @property
  def connectors(self):
    return self.system.connectors


class MainWindow(QMainWindow):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle('OMSimulatorGui')
    self.resize(1200, 800)

    self._ssp: SSP | None = None
    # Navigation stack for the diagram canvas only -- the tree always shows
    # the full hierarchy; this is a list of (System, displayName) from the
    # synthetic model level down to whatever level is currently shown on the
    # canvas. Index 0 is always the model-level wrapper (see _makeModelWrapper)
    # and is excluded from cref paths -- see _diagramLevelPath.
    self._diagramStack: list[tuple[System, str]] = []
    self._modelWrapperSystem: System | None = None
    self._modelName = 'Model'

    self._treeModel = SystemTreeModel(self)
    self._treeView = SystemTreeView(self)
    self._treeView.setModel(self._treeModel)
    # `clicked` (not `currentChanged`) deliberately: currentChanged fires for
    # ANY current-index change, including Qt's own internal bookkeeping --
    # e.g. QTreeView silently auto-selecting row 0 the first time it becomes
    # visible with no explicit selection, sometimes deferred until the next
    # time Qt processes events (which can coincide with an unrelated
    # interaction, like starting a canvas drag) -- which would otherwise
    # reset the diagram's navigation out from under the user. `clicked` only
    # fires for a genuine user mouse click on a row.
    self._treeView.clicked.connect(self._onTreeItemClicked)
    self._treeView.addSystemRequested.connect(self._onAddSystemRequested)
    self._treeView.addComponentRequested.connect(self._onAddComponentRequested)
    self._treeView.addConnectorRequested.connect(self._onAddConnectorRequested)
    self._treeView.deleteRequested.connect(self._onDeleteRequested)
    self._treeView.renameRequested.connect(self._onRenameRequested)
    self._treeView.propertiesRequested.connect(self._onPropertiesRequested)

    self._diagramView = DiagramView(self)
    self._diagramView.systemDrillDownRequested.connect(self._onDrillDownRequested)
    self._diagramView.connectionRequested.connect(self._onConnectionRequested)
    self._diagramView.connectionDeleteRequested.connect(self._onConnectionDeleteRequested)
    self._diagramView.addSystemRequested.connect(self._onCanvasAddSystemRequested)
    self._diagramView.addComponentRequested.connect(self._onCanvasAddComponentRequested)
    self._diagramView.addConnectorRequested.connect(self._onCanvasAddConnectorRequested)
    self._diagramView.elementPropertiesRequested.connect(self._onCanvasPropertiesRequested)
    # Fits/centers the empty default canvas immediately -- without this,
    # DiagramView.setSystem() (the only place that ever calls setSceneRect
    # and fitInView) never runs until a model is actually loaded, so the
    # blank canvas would sit wherever Qt's unfit default transform happens to
    # place it instead of centered in the view.
    #
    # Must be deferred, not called inline: at this point in __init__ the view
    # isn't parented into any layout yet, so its viewport reports Qt's tiny
    # pre-layout default size -- nonzero, so _fitIfNeeded's own "not sized
    # yet" guard (which only checks .isEmpty()) doesn't catch it, and it
    # happily "succeeds" against that wrong tiny size. Once _hasFitCurrentLevel
    # is set, _fitIfNeeded never retries, so that undersized fit would stick
    # even after the window reaches its real size. Deferring via
    # QTimer.singleShot(0, ...) runs this after the window construction below
    # has finished and the caller's show() has run, so the *first* fit
    # attempt already sees the real viewport.
    QTimer.singleShot(0, lambda: self._diagramView.setSystem(None))

    splitter = QSplitter(self)
    splitter.addWidget(self._treeView)
    splitter.addWidget(self._diagramView)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([300, 900])
    self.setCentralWidget(splitter)

    self._breadcrumbLabel = QLabel(self)
    diagramToolbar = QToolBar('Diagram', self)
    diagramToolbar.setMovable(False)
    self._upAction = diagramToolbar.addAction('Up')
    self._upAction.setEnabled(False)
    self._upAction.triggered.connect(self._onUpTriggered)
    diagramToolbar.addSeparator()
    diagramToolbar.addWidget(self._breadcrumbLabel)
    self.addToolBar(diagramToolbar)

    self.setStatusBar(QStatusBar(self))

    self._buildMenus()

  def _buildMenus(self) -> None:
    fileMenu = self.menuBar().addMenu('&File')

    newAction = fileMenu.addAction('&New SSP Model...')
    newAction.setShortcut('Ctrl+N')
    newAction.triggered.connect(self._onNewTriggered)

    openAction = fileMenu.addAction('&Open...')
    openAction.setShortcut('Ctrl+O')
    openAction.triggered.connect(self._onOpenTriggered)

    saveAsAction = fileMenu.addAction('Save &As...')
    saveAsAction.setShortcut('Ctrl+Shift+S')
    saveAsAction.triggered.connect(self._onSaveAsTriggered)

    fileMenu.addSeparator()

    exitAction = fileMenu.addAction('E&xit')
    exitAction.setShortcut('Ctrl+Q')
    exitAction.triggered.connect(self.close)

    modelMenu = self.menuBar().addMenu('&Model')
    simulationSettingsAction = modelMenu.addAction('&Simulation Settings...')
    simulationSettingsAction.triggered.connect(self._onSimulationSettingsTriggered)

  # --- File actions ----------------------------------------------------------

  def _onNewTriggered(self) -> None:
    dialog = CreateModelDialog(self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
      return

    ssp = SSP()
    # SSD.name has no owning-SSP awareness: a plain assignment leaves
    # ssp.variants' dict key and ssp.activeVariantName pointing at the old
    # ('default') name, and SSP.export() decides which SSD becomes the
    # required SystemStructure.ssd by comparing ssd.name == activeVariantName
    # -- so an un-re-keyed rename silently breaks export/reload. Re-key by
    # hand since the library has no renameVariant().
    ssd = ssp.activeVariant
    oldVariantName = ssd.name
    ssd.name = dialog.modelName()
    del ssp.variants[oldVariantName]
    ssp.variants[ssd.name] = ssd
    ssp.activeVariantName = ssd.name

    ssd.system.name = dialog.rootSystemName()
    self._ssp = ssp
    self._loadFromSsp()
    self.setWindowTitle(f'OMSimulatorGui - {dialog.modelName()}')
    self.statusBar().showMessage('New model created', 5000)

  def _onOpenTriggered(self) -> None:
    path, _ = QFileDialog.getOpenFileName(self, 'Open SSP', '', 'SSP files (*.ssp)')
    if path:
      self.openFile(path)

  def openFile(self, path: str) -> None:
    '''Loads `path` as the active SSP and refreshes the tree and diagram.'''
    try:
      ssp = SSP(path)
    except Exception as e:
      QMessageBox.critical(self, 'Failed to open', f'Could not open "{path}":\n{e}')
      return

    self._ssp = ssp
    self._loadFromSsp()

    self.setWindowTitle(f'OMSimulatorGui - {Path(path).name}')
    self.statusBar().showMessage(f'Loaded {path}', 5000)

  def _onSaveAsTriggered(self) -> None:
    if self._ssp is None:
      return
    path, _ = QFileDialog.getSaveFileName(self, 'Save SSP', '', 'SSP files (*.ssp)')
    if not path:
      return
    try:
      self._ssp.export(path)
    except Exception as e:
      QMessageBox.critical(self, 'Save failed', f'Could not save "{path}":\n{e}')
      return
    self.setWindowTitle(f'OMSimulatorGui - {Path(path).name}')
    self.statusBar().showMessage(f'Saved {path}', 5000)

  def _loadFromSsp(self) -> None:
    '''(Re)initializes the tree/diagram from self._ssp's active variant.
    The tree shows the model (SSD) name as a wrapper above the root system's
    own row; the diagram mirrors that with a synthetic "model level" showing
    the root system as a single box (its own connectors as ports) -- double-
    clicking it drills in exactly like any nested subsystem, reusing the same
    ElementIconItem/drill-down machinery. The model level is never part of
    any cref -- see _diagramLevelPath.'''
    variant = self._ssp.activeVariant if self._ssp is not None else None
    rootSystem = variant.system if variant is not None else None
    modelName = variant.name if variant is not None else 'Model'

    self._treeModel.setSystem(rootSystem, modelName)
    self._treeView.expandAll()

    self._modelName = modelName
    self._modelWrapperSystem = self._makeModelWrapper(rootSystem) if rootSystem is not None else None
    self._diagramStack = [(self._modelWrapperSystem, modelName)] if rootSystem is not None else []
    self._updateDiagram()

  @staticmethod
  def _makeModelWrapper(rootSystem: System) -> System:
    '''A throwaway System whose only "element" is a _RootBoxProxy wrapping
    the real root system -- never exported, purely so DiagramScene.setSystem()
    can render the root system as a single box (with its own ports) the same
    way it renders any other element. Rebuilt whenever the SSP is (re)loaded;
    edits to rootSystem's own contents are visible through it automatically
    since the proxy delegates to the same live object.'''
    wrapper = System(str(rootSystem.name))
    wrapper.elements = {str(rootSystem.name): _RootBoxProxy(rootSystem)}
    return wrapper

  # --- Shared refresh after any edit -----------------------------------------

  def _onModelChanged(self) -> None:
    self._treeModel.refresh()
    self._treeView.expandAll()
    self._updateDiagram()

  # --- Diagram navigation ------------------------------------------------------

  def _updateDiagram(self) -> None:
    system = self._diagramStack[-1][0] if self._diagramStack else None
    self._diagramView.setSystem(system)
    self._breadcrumbLabel.setText(' > '.join(name for _, name in self._diagramStack))
    self._upAction.setEnabled(len(self._diagramStack) > 1)

  def _onDrillDownRequested(self, system: System, name: str) -> None:
    self._diagramStack.append((system, name))
    self._updateDiagram()

  def _onUpTriggered(self) -> None:
    if len(self._diagramStack) > 1:
      self._diagramStack.pop()
      self._updateDiagram()

  def _diagramLevelPath(self) -> list[str]:
    '''The [rootSystemName, ..., currentLevelName] path for whatever system
    is currently shown on the diagram canvas, skipping the synthetic model
    level at index 0 (the API never sees the model name, only system names).'''
    return [name for _, name in self._diagramStack[1:]]

  def _connectionCref(self, elementName: str, connectorName: str) -> CRef:
    basePath = self._diagramLevelPath()
    if elementName:
      return CRef(*basePath, elementName, connectorName)
    return CRef(*basePath, connectorName)

  def _onConnectionRequested(self, elem1: str, conn1: str, elem2: str, conn2: str) -> None:
    try:
      self._ssp.addConnection(self._connectionCref(elem1, conn1), self._connectionCref(elem2, conn2))
    except Exception as e:
      QMessageBox.critical(self, 'Add Connection failed', str(e))
      return
    self._onModelChanged()

  def _onConnectionDeleteRequested(self, elem1: str, conn1: str, elem2: str, conn2: str) -> None:
    label1 = f'{elem1}.{conn1}' if elem1 else conn1
    label2 = f'{elem2}.{conn2}' if elem2 else conn2
    if QMessageBox.question(self, 'Delete Connection', f'Delete connection {label1} -> {label2}?') != QMessageBox.StandardButton.Yes:
      return
    try:
      self._ssp.deleteConnection(self._connectionCref(elem1, conn1), self._connectionCref(elem2, conn2))
    except Exception as e:
      QMessageBox.critical(self, 'Delete Connection failed', str(e))
      return
    self._onModelChanged()

  def _onTreeItemClicked(self, index) -> None:
    '''Clicking a tree item navigates the diagram to show that item *in
    context* -- as a box at its parent's level -- rather than drilling into
    its own contents (that's what double-clicking its box on the canvas is
    for). So clicking the model row or the root system both land on the
    model level (where the root system appears as a box); clicking a nested
    system lands one level up, wherever its own box lives.'''
    node = self._treeModel.nodeFromIndex(index)
    if node is None:
      return

    if node.kind == KIND_MODEL:
      self._diagramStack = [(self._modelWrapperSystem, self._modelName)]
      self._updateDiagram()
      return

    if node.kind != KIND_SYSTEM:
      return

    path: list[tuple[System, str]] = []
    n = node
    while n is not None and n.kind == KIND_SYSTEM:
      path.append((n.obj, str(n.obj.name)))
      n = n.parent
    path.reverse()

    parentPath = path[:-1]  # show the clicked system itself, not its insides
    self._diagramStack = [(self._modelWrapperSystem, self._modelName), *parentPath]
    self._updateDiagram()

  # --- Structured editing ------------------------------------------------------

  def _crefPath(self, node) -> list[str]:
    '''Builds the [rootName, ..., thisNodeName] path SSP/SSD/System methods
    expect, by walking the TreeNode ancestor chain. Stops at the KIND_SYSTEM
    boundary -- the tree's model-name wrapper row (KIND_MODEL) sits above the
    root system but is never part of the path; the API always operates on
    system names.'''
    if node.kind == KIND_SYSTEM:
      segments = []
      n = node
      while n is not None and n.kind == KIND_SYSTEM:
        segments.append(str(n.obj.name))
        n = n.parent
      segments.reverse()
      return segments
    if node.kind in (KIND_COMPONENT, KIND_COMPONENT_TABLE):
      return self._crefPath(node.parent) + [str(node.obj.name)]
    if node.kind == KIND_CONNECTOR:
      # node.parent is the "Connectors" group node; its parent is the owning system.
      return self._crefPath(node.parent.parent) + [str(node.obj.name)]
    raise ValueError(f'Cannot build a path for node kind {node.kind!r}')

  def _requireNonEmptyPath(self, path: list[str]) -> bool:
    '''Right-clicking empty canvas at the model level (viewing the root
    system as a box, before drilling into it) has no valid container to add
    into -- _diagramLevelPath() is empty there by design (the model level
    isn't a real, addressable system). Tree-triggered calls never hit this,
    since _crefPath always includes at least the root system's own name.'''
    if path:
      return True
    QMessageBox.information(self, 'Nothing to add to',
                             'Double-click into the root system first, then add to its contents.')
    return False

  def _onAddSystemRequested(self, node) -> None:
    self._addSystemAtPath(self._crefPath(node))

  def _onCanvasAddSystemRequested(self) -> None:
    self._addSystemAtPath(self._diagramLevelPath())

  def _addSystemAtPath(self, path: list[str]) -> None:
    if not self._requireNonEmptyPath(path):
      return
    dialog = AddSystemDialog(self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
      return
    try:
      # SSD.addSystem validates the cref's first segment against the SSD
      # variant's own name (self._name), not the root System's name -- unlike
      # every sibling method (addComponent/addConnector/delete/rename), which
      # validate via _validateCref against self.system.name. Substitute the
      # variant name for the first segment so this still works even when the
      # root system has been renamed away from the variant name.
      path = [*path]
      path[0] = self._ssp.activeVariant.name
      self._ssp.addSystem(CRef(*path, dialog.name()))
    except Exception as e:
      QMessageBox.critical(self, 'Add System failed', str(e))
      return
    self._onModelChanged()

  def _onAddComponentRequested(self, node) -> None:
    self._addComponentAtPath(self._crefPath(node))

  def _onCanvasAddComponentRequested(self) -> None:
    self._addComponentAtPath(self._diagramLevelPath())

  def _addComponentAtPath(self, path: list[str]) -> None:
    if not self._requireNonEmptyPath(path):
      return
    dialog = AddSubModelDialog(self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
      return
    try:
      resourceName = f'resources/{Path(dialog.fmuPath()).name}'
      if resourceName not in self._ssp.resources:
        self._ssp.addResource(dialog.fmuPath())
      self._ssp.addComponent(CRef(*path, dialog.name()), resourceName)
    except Exception as e:
      QMessageBox.critical(self, 'Add Component failed', str(e))
      return
    self._onModelChanged()

  def _onAddConnectorRequested(self, node) -> None:
    self._addConnectorAtPath(self._crefPath(node))

  def _onCanvasAddConnectorRequested(self) -> None:
    self._addConnectorAtPath(self._diagramLevelPath())

  def _addConnectorAtPath(self, path: list[str]) -> None:
    if not self._requireNonEmptyPath(path):
      return
    dialog = AddConnectorDialog(self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
      return
    try:
      connector = Connector(dialog.name(), dialog.causality(), dialog.signalType())
      self._ssp.addConnector(CRef(*path), connector)
    except Exception as e:
      QMessageBox.critical(self, 'Add Connector failed', str(e))
      return
    self._onModelChanged()

  def _onDeleteRequested(self, node) -> None:
    if QMessageBox.question(self, 'Delete', f'Delete "{node.label}"?') != QMessageBox.StandardButton.Yes:
      return
    try:
      self._ssp.delete(CRef(*self._crefPath(node)))
    except Exception as e:
      QMessageBox.critical(self, 'Delete failed', str(e))
      return
    self._onModelChanged()

  def _onRenameRequested(self, node) -> None:
    currentName = str(node.obj.name)
    newName, ok = QInputDialog.getText(self, 'Rename', 'New name:', text=currentName)
    newName = newName.strip()
    if not ok or not newName or newName == currentName:
      return
    try:
      self._ssp.rename(CRef(*self._crefPath(node)), CRef(newName))
    except Exception as e:
      QMessageBox.critical(self, 'Rename failed', str(e))
      return
    self._onModelChanged()

  def _onPropertiesRequested(self, node) -> None:
    self._showElementProperties(node.obj)

  def _onCanvasPropertiesRequested(self, component) -> None:
    self._showElementProperties(component)

  def _showElementProperties(self, component) -> None:
    dialog = ElementPropertiesDialog(component, self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
      self._onModelChanged()

  # --- Simulation settings -----------------------------------------------------

  def _onSimulationSettingsTriggered(self) -> None:
    if self._ssp is None:
      QMessageBox.information(self, 'No model', 'Create or open a model first.')
      return
    ssd = self._ssp.activeVariant
    dialog = SimulationSettingsDialog(ssd, self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
      return
    ssd.startTime = dialog.startTime()
    ssd.stopTime = dialog.stopTime()
    ssd.tolerance = dialog.tolerance()
    ssd.maximumStepSize = dialog.stepSize()
    ssd.resultFile = dialog.resultFile()
