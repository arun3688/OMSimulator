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

'''DiagramView/DiagramScene: renders one System level at a time (M2), with
structured editing (M3: add/delete/rename via the tree) and, as of M4,
connection drawing (plain drag from a port to another) and moving elements
(dragging an icon commits its new position into elementgeometry) or ports
(Shift+drag a port commits its new position into connectorGeometry).

Elements/connectors without authored geometry get a real one assigned on
first render (a simple grid layout for elements; connectors of the same
causality spread evenly along their edge instead of all defaulting to the
same spot) so moving/connecting them works the same as authored ones --
this is the one place the view mutates the model outside of an explicit
user edit, and it's purely a position, not a structural change.
'''

from collections import defaultdict

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsView, QMenu

from OMSimulator import System
from OMSimulator.connector import ConnectorGeometry
from OMSimulator.elementgeometry import ElementGeometry
from OMSimulator.variable import Causality

from OMSimulatorGui.views.diagram_items import ConnectionItem, ElementIconItem, PortItem, SystemBoundaryItem, geometryToSceneRect

_FALLBACK_COLS = 4
_FALLBACK_CELL_W = 130.0
_FALLBACK_CELL_H = 100.0
_FALLBACK_ELEMENT_W = 90.0
_FALLBACK_ELEMENT_H = 60.0
_BOUNDARY_MARGIN = 60.0


def _assignFallbackConnectorGeometry(connectors) -> None:
  '''Spreads input/output connectors lacking a connectorGeometry evenly
  along their edge (x=0 for input, x=1 for output) so multiple GUI-added
  connectors of the same causality don't all collide at one default
  position -- without this every such connector defaults to the same
  (edge, 0.5) spot and they render as a single overlapping dot.

  Since connectors get fallback-assigned incrementally (one diagram render
  per add, not all at once), the index used to space a newly-added
  connector out must come from its position within the *full* same-causality
  group -- not just the (usually one-element) subset still lacking geometry
  -- otherwise every new addition independently computes the same "only
  one in the group" midpoint and they still collide.'''
  groups = defaultdict(list)
  for connector in connectors:
    causality = connector.getCausality()
    if causality in (Causality.input, Causality.output):
      groups[0.0 if causality == Causality.input else 1.0].append(connector)

  for x, group in groups.items():
    count = len(group)
    for index, connector in enumerate(group):
      if connector.connectorGeometry is None:
        connector.connectorGeometry = ConnectorGeometry(x=x, y=(index + 1) / (count + 1))


class DiagramScene(QGraphicsScene):
  def __init__(self, parent=None):
    super().__init__(parent)
    self._system: System | None = None
    self._elementItems: dict[str, ElementIconItem] = {}
    self._boundaryItem: SystemBoundaryItem | None = None

  def setSystem(self, system: System | None) -> None:
    self.clear()
    self._elementItems.clear()
    self._boundaryItem = None
    self._system = system

    if system is None:
      self.setSceneRect(QRectF(0, 0, 100, 100))
      return

    rects: list[QRectF] = []
    fallbackIndex = 0
    for name, element in system.elements.items():
      if element.elementgeometry is None:
        row, col = divmod(fallbackIndex, _FALLBACK_COLS)
        fallbackIndex += 1
        x1 = col * _FALLBACK_CELL_W
        y2 = -(row * _FALLBACK_CELL_H)  # Y-up: later rows sit lower, i.e. more negative
        element.elementgeometry = ElementGeometry(
            x1=x1, y1=y2 - _FALLBACK_ELEMENT_H, x2=x1 + _FALLBACK_ELEMENT_W, y2=y2)

      _assignFallbackConnectorGeometry(element.connectors)
      rect = geometryToSceneRect(element.elementgeometry)
      rects.append(rect)
      item = ElementIconItem(str(name), element, rect, onMoved=self._onElementMoved)
      self.addItem(item)
      self._elementItems[str(name)] = item

    union = rects[0] if rects else QRectF(0, 0, 200, 200)
    for rect in rects[1:]:
      union = union.united(rect)

    if system.connectors:
      _assignFallbackConnectorGeometry(system.connectors)
      boundaryRect = union.adjusted(-_BOUNDARY_MARGIN, -_BOUNDARY_MARGIN, _BOUNDARY_MARGIN, _BOUNDARY_MARGIN)
      self._boundaryItem = SystemBoundaryItem(system, boundaryRect, onMoved=self._onElementMoved)
      self.addItem(self._boundaryItem)

    for connection in system.connections:
      startPos = self._resolvePortPos(connection.startElement, connection.startConnector)
      endPos = self._resolvePortPos(connection.endElement, connection.endConnector)
      if startPos is not None and endPos is not None:
        self.addItem(ConnectionItem(connection, startPos, endPos))

    self.setSceneRect(self.itemsBoundingRect().adjusted(-40, -40, 40, 40))

  def _resolvePortPos(self, elementName, connectorName):
    elementName = str(elementName)
    connectorName = str(connectorName)
    if elementName == '':
      return None if self._boundaryItem is None else self._boundaryItem.portScenePos(connectorName)
    item = self._elementItems.get(elementName)
    return None if item is None else item.portScenePos(connectorName)

  def _onElementMoved(self) -> None:
    '''An icon settled after a drag: rebuild so connections (baked in as
    static polylines, not live-tracked mid-drag) snap to the new position.'''
    self.setSystem(self._system)


def _elementNameForPort(port: PortItem) -> str:
  '''Empty string means the port belongs to the current system's own
  boundary, matching Connection.startElement/endElement's convention.'''
  parent = port.parentItem()
  return parent.name if isinstance(parent, ElementIconItem) else ''


class DiagramView(QGraphicsView):
  '''Emits systemDrillDownRequested(System, name) on double-clicking a
  system-type element; MainWindow owns the navigation stack and calls
  setSystem() for both drill-down and "up".

  Dragging from one port to another emits connectionRequested with both
  ports' (elementName, connectorName) -- MainWindow builds the crefs and
  calls SSP.addConnection, which already validates causality (including the
  flipped-direction case) internally. Right-clicking a connection emits
  connectionDeleteRequested the same way, for SSP.deleteConnection.
  '''

  systemDrillDownRequested = Signal(object, str)
  connectionRequested = Signal(str, str, str, str)       # elem1, conn1, elem2, conn2
  connectionDeleteRequested = Signal(str, str, str, str)  # elem1, conn1, elem2, conn2

  def __init__(self, parent=None):
    super().__init__(parent)
    self._scene = DiagramScene(self)
    self.setScene(self._scene)
    self.setRenderHint(QPainter.RenderHint.Antialiasing)
    self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
    self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    self._currentSystem: System | None = None
    self._connectDragPort: PortItem | None = None
    self._connectDragLine: QGraphicsLineItem | None = None

  def setSystem(self, system: System | None) -> None:
    '''Rebuilds the scene. Only re-fits the view when navigating to a
    different System (a fresh setSystem call after an edit to the SAME level
    -- e.g. from _onElementMoved or MainWindow's shared refresh -- must not
    reset the user's current pan/zoom).'''
    isNewLevel = system is not self._currentSystem
    self._currentSystem = system
    self._scene.setSystem(system)
    if isNewLevel and not self._scene.sceneRect().isEmpty():
      self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

  def resizeEvent(self, event) -> None:
    super().resizeEvent(event)
    if not self._scene.sceneRect().isEmpty():
      self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

  def wheelEvent(self, event) -> None:
    factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
    self.scale(factor, factor)

  def mouseDoubleClickEvent(self, event) -> None:
    item = self.itemAt(event.pos())
    while item is not None and not isinstance(item, ElementIconItem):
      item = item.parentItem()

    if item is not None and isinstance(item.element, System):
      self.systemDrillDownRequested.emit(item.element, item.name)
      return

    super().mouseDoubleClickEvent(event)

  def mousePressEvent(self, event) -> None:
    item = self.itemAt(event.pos())
    if isinstance(item, PortItem) and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
      # Shift+drag repositions the port itself (PortItem.ItemIsMovable takes
      # over via normal Qt item dragging); plain drag starts a connection.
      super().mousePressEvent(event)
      return
    if isinstance(item, PortItem):
      self._connectDragPort = item
      startPos = item.scenePos()
      self._connectDragLine = QGraphicsLineItem(startPos.x(), startPos.y(), startPos.x(), startPos.y())
      self._connectDragLine.setPen(QPen(QColor(200, 70, 70), 1.5, Qt.PenStyle.DashLine))
      self._connectDragLine.setZValue(3)
      self._scene.addItem(self._connectDragLine)
      event.accept()
      return
    super().mousePressEvent(event)

  def mouseMoveEvent(self, event) -> None:
    if self._connectDragPort is not None:
      startPos = self._connectDragPort.scenePos()
      endPos = self.mapToScene(event.pos())
      self._connectDragLine.setLine(startPos.x(), startPos.y(), endPos.x(), endPos.y())
      event.accept()
      return
    super().mouseMoveEvent(event)

  def mouseReleaseEvent(self, event) -> None:
    if self._connectDragPort is not None:
      startPort = self._connectDragPort
      self._connectDragPort = None
      self._scene.removeItem(self._connectDragLine)
      self._connectDragLine = None

      targetItem = self.itemAt(event.pos())
      if isinstance(targetItem, PortItem) and targetItem is not startPort:
        self.connectionRequested.emit(
            _elementNameForPort(startPort), str(startPort.connector.name),
            _elementNameForPort(targetItem), str(targetItem.connector.name))
      event.accept()
      return
    super().mouseReleaseEvent(event)

  def contextMenuEvent(self, event) -> None:
    item = self.itemAt(event.pos())
    if isinstance(item, ConnectionItem):
      menu = QMenu(self)
      deleteAction = menu.addAction('Delete Connection')
      if menu.exec(event.globalPos()) == deleteAction:
        connection = item.connection
        self.connectionDeleteRequested.emit(
            str(connection.startElement), str(connection.startConnector),
            str(connection.endElement), str(connection.endConnector))
      return
    super().contextMenuEvent(event)
