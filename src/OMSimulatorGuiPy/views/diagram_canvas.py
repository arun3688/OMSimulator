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

import math
from collections import defaultdict

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsScene, QGraphicsView, QMenu

from OMSimulator import System
from OMSimulator.component import Component
from OMSimulator.connector import ConnectorGeometry
from OMSimulator.elementgeometry import ElementGeometry
from OMSimulator.variable import Causality

from OMSimulatorGui.views.diagram_items import ConnectionItem, ElementIconItem, PortItem, SystemBoundaryItem, defaultRoute, geometryToSceneRect

_FALLBACK_COLS = 4
_FALLBACK_CELL_W = 80.0
_FALLBACK_CELL_H = 60.0
_FALLBACK_ELEMENT_W = 50.0
_FALLBACK_ELEMENT_H = 35.0
_BOUNDARY_MARGIN = 40.0


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


_GRID_SPACING = 10.0
_GRID_COLOR = QColor(225, 225, 225)
_CANVAS_BORDER_COLOR = QColor(160, 160, 160)
_CANVAS_OUTSIDE_COLOR = QColor(235, 235, 235)
_DEFAULT_CANVAS_WIDTH = 400.0
_DEFAULT_CANVAS_HEIGHT = 250.0
_CANVAS_MARGIN = 20.0  # keeps content from touching the canvas edge as it expands


class DiagramScene(QGraphicsScene):
  def __init__(self, parent=None):
    super().__init__(parent)
    self._system: System | None = None
    self._elementItems: dict[str, ElementIconItem] = {}
    self._boundaryItem: SystemBoundaryItem | None = None
    self._canvasRect = QRectF(0, 0, _DEFAULT_CANVAS_WIDTH, _DEFAULT_CANVAS_HEIGHT)

  def drawBackground(self, painter, rect) -> None:
    # A bounded, fixed-size "page" like OMEdit's, not an endlessly-tiling
    # grid texture: starts at a sensible default size and only grows once
    # actual content (elements/the system's own boundary) needs more room --
    # see setSystem's canvasRect computation. Purely presentational either
    # way, since SSP itself has no diagram-extent/coordinate-system concept
    # to size a canvas from.
    painter.fillRect(rect, _CANVAS_OUTSIDE_COLOR)
    painter.fillRect(self._canvasRect, QColor(255, 255, 255))

    gridRect = self._canvasRect.intersected(rect)
    if not gridRect.isEmpty():
      pen = QPen(_GRID_COLOR)
      pen.setCosmetic(True)
      painter.setPen(pen)
      left = math.floor(gridRect.left() / _GRID_SPACING) * _GRID_SPACING
      top = math.floor(gridRect.top() / _GRID_SPACING) * _GRID_SPACING
      x = left
      while x < gridRect.right():
        painter.drawLine(QPointF(x, gridRect.top()), QPointF(x, gridRect.bottom()))
        x += _GRID_SPACING
      y = top
      while y < gridRect.bottom():
        painter.drawLine(QPointF(gridRect.left(), y), QPointF(gridRect.right(), y))
        y += _GRID_SPACING

    borderPen = QPen(_CANVAS_BORDER_COLOR)
    borderPen.setCosmetic(True)
    painter.setPen(borderPen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(self._canvasRect)

  def setSystem(self, system: System | None) -> None:
    self.clear()
    self._elementItems.clear()
    self._boundaryItem = None
    self._system = system
    self._canvasRect = QRectF(0, 0, _DEFAULT_CANVAS_WIDTH, _DEFAULT_CANVAS_HEIGHT)

    if system is None:
      self.setSceneRect(self._canvasRect.adjusted(-40, -40, 40, 40))
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
      union = union.united(boundaryRect)

    for connection in system.connections:
      startPos = self._resolvePortPos(connection.startElement, connection.startConnector)
      endPos = self._resolvePortPos(connection.endElement, connection.endConnector)
      if startPos is not None and endPos is not None:
        self.addItem(ConnectionItem(connection, startPos, endPos, onMoved=self._onElementMoved))

    if rects:
      # Union with the raw (unpadded) content first -- padding it before
      # comparing against the origin-anchored default would push even a
      # single small, comfortably-contained element's rect corner just
      # negative, making the canvas falsely "expand" for content that never
      # actually needed more room. Only pad afterwards, and only along
      # whichever edges the union actually grew past.
      grown = self._canvasRect.united(union)
      if grown != self._canvasRect:
        grown.adjust(-_CANVAS_MARGIN, -_CANVAS_MARGIN, _CANVAS_MARGIN, _CANVAS_MARGIN)
      self._canvasRect = grown

    self.setSceneRect(self.itemsBoundingRect().united(self._canvasRect).adjusted(-40, -40, 40, 40))

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


_UNSET = object()  # distinct from any real System *and* from None -- see DiagramView.__init__


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
  addSystemRequested = Signal()     # right-click on empty canvas -- adds to the level shown here
  addComponentRequested = Signal()
  addConnectorRequested = Signal()
  elementPropertiesRequested = Signal(object)  # Component: double-clicked on the canvas

  def __init__(self, parent=None):
    super().__init__(parent)
    self._scene = DiagramScene(self)
    self.setScene(self._scene)
    self.setRenderHint(QPainter.RenderHint.Antialiasing)
    self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
    self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    # _UNSET, not None: setSystem(None) is exactly what shows the empty
    # default canvas (no model loaded/created yet), and it still needs its
    # one-time fit/center -- comparing against a real None here would make
    # that first setSystem(None) look like a no-op ("already showing None")
    # and skip fitting entirely.
    self._currentSystem = _UNSET
    self._connectDragPort: PortItem | None = None
    self._connectDragLine: QGraphicsPathItem | None = None
    self._reshapingConnection: ConnectionItem | None = None
    # True once fitInView has actually run for the level currently shown.
    self._hasFitCurrentLevel = False

  def setSystem(self, system: System | None) -> None:
    '''Rebuilds the scene. Only re-fits the view when navigating to a
    different System (a fresh setSystem call after an edit to the SAME level
    -- e.g. from _onElementMoved or MainWindow's shared refresh -- must not
    reset the user's current pan/zoom).

    The retry-fit for "widget has no real size yet" is deferred via
    QTimer.singleShot rather than hooked into resizeEvent. resizeEvent fires
    for reasons that have nothing to do with the widget's own on-screen size
    changing -- e.g. a scene-rect change (from a drag moving an item far
    enough to toggle scrollbar visibility) can trigger a genuine viewport
    resizeEvent -- and re-fitting there would silently re-center the whole
    view, undoing the drag's visual effect (the committed geometry is
    unaffected, only the camera snaps back). Deferring via the event loop
    instead ties the retry purely to "give layout a chance to finish",
    with no dependency on resize events at all.'''
    isNewLevel = system is not self._currentSystem
    self._currentSystem = system
    self._scene.setSystem(system)
    if isNewLevel:
      self._hasFitCurrentLevel = False
      if not self._fitIfNeeded():
        QTimer.singleShot(0, self._fitIfNeeded)

  def _fitIfNeeded(self) -> bool:
    if self._hasFitCurrentLevel:
      return True
    if self._scene.sceneRect().isEmpty() or self.viewport().rect().isEmpty():
      return False
    self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    self._hasFitCurrentLevel = True
    return True

  def wheelEvent(self, event) -> None:
    factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
    self.scale(factor, factor)

  def mouseDoubleClickEvent(self, event) -> None:
    item = self.itemAt(event.pos())
    while item is not None and not isinstance(item, ElementIconItem):
      item = item.parentItem()

    if item is not None:
      # duck-typed: a plain System element resolves to itself; a
      # _RootBoxProxy (the model-level "root system as a box" stand-in,
      # see MainWindow) resolves to the real system it wraps.
      target = getattr(item.element, 'system', item.element)
      if isinstance(target, System):
        self.systemDrillDownRequested.emit(target, item.name)
        return
      if isinstance(target, Component):
        self.elementPropertiesRequested.emit(target)
        return

    super().mouseDoubleClickEvent(event)

  def _connectionAt(self, scenePos) -> ConnectionItem | None:
    '''Finds a ConnectionItem near scenePos regardless of z-order/what's
    drawn on top of it. Connections are deliberately drawn *behind* element
    icons, so a stretch of a connection's route that happens to pass
    underneath one is never the topmost item there -- itemAt() would only
    ever find the icon, making that stretch permanently ungrabbable. Scanning
    every connection's own (already hit-tolerance-widened) shape() directly
    sidesteps that, so a segment hidden under an icon can still be dragged
    out into free space.'''
    for item in self._scene.items():
      if isinstance(item, ConnectionItem) and item.shape().contains(item.mapFromScene(scenePos)):
        return item
    return None

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
      self._connectDragLine = QGraphicsPathItem()
      self._connectDragLine.setPath(QPainterPath(startPos))
      self._connectDragLine.setPen(QPen(QColor(200, 70, 70), 1.5, Qt.PenStyle.DashLine))
      self._connectDragLine.setZValue(3)
      self._scene.addItem(self._connectDragLine)
      event.accept()
      return

    if event.button() == Qt.MouseButton.LeftButton:
      connection = self._connectionAt(self.mapToScene(event.pos()))
      if connection is not None:
        self._reshapingConnection = connection
        connection.beginReshapeAt(connection.mapFromScene(self.mapToScene(event.pos())))
        event.accept()
        return

    super().mousePressEvent(event)

  def mouseMoveEvent(self, event) -> None:
    if self._connectDragPort is not None:
      # Elbow the in-progress preview the same way a finished connection with
      # no saved geometry would render (defaultRoute), so the shape the user
      # sees while dragging already matches the shape they'll get on release
      # instead of jumping from a straight preview line to a bent result.
      startPos = self._connectDragPort.scenePos()
      endPos = self.mapToScene(event.pos())
      route = defaultRoute(startPos, endPos)
      path = QPainterPath(route[0])
      for point in route[1:]:
        path.lineTo(point)
      self._connectDragLine.setPath(path)
      event.accept()
      return
    if self._reshapingConnection is not None:
      connection = self._reshapingConnection
      connection.updateReshape(connection.mapFromScene(self.mapToScene(event.pos())))
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
    if self._reshapingConnection is not None:
      connection = self._reshapingConnection
      self._reshapingConnection = None
      connection.endReshapeAt(connection.mapFromScene(self.mapToScene(event.pos())))
      event.accept()
      return
    super().mouseReleaseEvent(event)

  def contextMenuEvent(self, event) -> None:
    scenePos = self.mapToScene(event.pos())
    # Scanned via _connectionAt, not itemAt(): same reasoning as
    # mousePressEvent -- a connection stretch hidden under an icon should
    # still get "Delete Connection"/"Remove Waypoint", not be shadowed by
    # whatever icon happens to be drawn on top of it there.
    connectionItem = self._connectionAt(scenePos)
    if connectionItem is not None:
      waypointIndex = connectionItem.waypointIndexAt(scenePos)
      menu = QMenu(self)
      removeWaypointAction = menu.addAction('Remove Waypoint') if waypointIndex is not None else None
      deleteAction = menu.addAction('Delete Connection')
      chosen = menu.exec(event.globalPos())
      if removeWaypointAction is not None and chosen == removeWaypointAction:
        connectionItem.removeWaypoint(waypointIndex)
      elif chosen == deleteAction:
        connection = connectionItem.connection
        self.connectionDeleteRequested.emit(
            str(connection.startElement), str(connection.startConnector),
            str(connection.endElement), str(connection.endConnector))
      return

    item = self.itemAt(event.pos())

    if item is None or isinstance(item, SystemBoundaryItem):
      # Empty canvas: add to whatever level is currently shown here. The
      # dashed SystemBoundaryItem covers the whole scene, so a right-click
      # anywhere inside it (not just where nothing is drawn at all) counts
      # as "empty canvas" too.
      menu = QMenu(self)
      addSystemAction = menu.addAction('Add System...')
      addComponentAction = menu.addAction('Add Component...')
      addConnectorAction = menu.addAction('Add Connector...')
      chosen = menu.exec(event.globalPos())
      if chosen == addSystemAction:
        self.addSystemRequested.emit()
      elif chosen == addComponentAction:
        self.addComponentRequested.emit()
      elif chosen == addConnectorAction:
        self.addConnectorRequested.emit()
      return

    super().contextMenuEvent(event)
