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

'''QGraphicsItem subclasses for the diagram canvas.

Coordinate convention: SSD/ElementGeometry is Y-up (Modelica convention);
Qt's QGraphicsView is Y-down. `geometryToSceneRect` is the one place that
flips Y -- everything downstream works in already-flipped Qt scene
coordinates, so item-local painting (including text) never needs its own
flip.

ElementGeometry.x1/y1/x2/y2 units are whatever the authoring tool chose
(dcmotor.ssp uses low hundreds) -- QGraphicsView handles arbitrary float
ranges fine via fitInView, so no rescaling is needed here.
'''

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem, QGraphicsSimpleTextItem

from OMSimulator.variable import Causality

PORT_RADIUS = 5.0

CAUSALITY_COLORS = {
  Causality.input: QColor(60, 120, 220),
  Causality.output: QColor(40, 160, 90),
}


def geometryToSceneRect(geometry) -> QRectF:
  '''Maps an ElementGeometry/SystemGeometry-shaped object (x1,y1,x2,y2, Y-up)
  to a Qt scene rect (Y-down).'''
  top = -max(geometry.y1, geometry.y2)
  bottom = -min(geometry.y1, geometry.y2)
  left = min(geometry.x1, geometry.x2)
  right = max(geometry.x1, geometry.x2)
  return QRectF(QPointF(left, top), QPointF(right, bottom))


class PortItem(QGraphicsEllipseItem):
  '''A connector port, positioned at connector.connectorGeometry.(x,y) --
  relative [0,1] within `localRect` (the parent icon/boundary's own (0,0)..
  (w,h) frame). y=1 is icon-top (Y-up convention), consistent with
  geometryToSceneRect's flip. connector.connectorGeometry is always real by
  construction time (DiagramScene spreads out fallback positions for
  connectors that don't have one, so same-causality ports never collide).

  Draggable with Shift held (plain drag from a port means "start a
  connection" -- see DiagramView.mousePressEvent); dropping commits the new
  position back into connectorGeometry, clamped to [0,1].

  `onMoved`, if given, is called (no args) once such a drag completes, so
  the owning scene can rebuild -- connections aren't live-tracked mid-drag.
  '''

  def __init__(self, connector, localRect: QRectF, parent: QGraphicsItem, onMoved=None):
    super().__init__(-PORT_RADIUS, -PORT_RADIUS, 2 * PORT_RADIUS, 2 * PORT_RADIUS, parent)
    self.connector = connector
    self._localRect = localRect
    self._onMoved = onMoved

    geometry = connector.connectorGeometry
    self.setPos(localRect.left() + geometry.x * localRect.width(),
                localRect.top() + (1.0 - geometry.y) * localRect.height())
    self._dragStartScenePos = self.pos()

    color = CAUSALITY_COLORS.get(connector.getCausality(), QColor(130, 130, 130))
    self.setBrush(QBrush(color))
    self.setPen(QPen(color.darker(150)))
    self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
    self.setZValue(2)
    self.setToolTip(f'{connector.name} ({connector.getCausality().name}, {connector.getSignalType().name})')

  def mouseReleaseEvent(self, event) -> None:
    super().mouseReleaseEvent(event)
    self.commitPositionIfMoved()

  def commitPositionIfMoved(self) -> None:
    '''Writes self.pos() back into connectorGeometry.(x,y) (clamped to
    [0,1] of the parent's local rect) and notifies onMoved. Split out from
    mouseReleaseEvent so it can be exercised without a real Qt mouse-event
    sequence.'''
    newPos = self.pos()
    if newPos == self._dragStartScenePos:
      return
    self._dragStartScenePos = newPos

    width = self._localRect.width() or 1.0
    height = self._localRect.height() or 1.0
    fx = (newPos.x() - self._localRect.left()) / width
    fy = 1.0 - (newPos.y() - self._localRect.top()) / height

    geometry = self.connector.connectorGeometry
    geometry.x = max(0.0, min(1.0, fx))
    geometry.y = max(0.0, min(1.0, fy))

    if self._onMoved is not None:
      self._onMoved()


_WIREABLE_CAUSALITIES = (Causality.input, Causality.output)


def _createPorts(hostItem: QGraphicsItem, connectors, localRect: QRectF, onMoved=None) -> dict:
  '''Only input/output connectors are drawn as ports -- parameters (and
  calculatedParameter/local/independent) aren't valid connection endpoints
  (Connection.is_validConnection never accepts them), they're set via the
  properties dialog (M5) instead.'''
  wireable = [c for c in connectors if c.getCausality() in _WIREABLE_CAUSALITIES]
  return {str(connector.name): PortItem(connector, localRect, hostItem, onMoved) for connector in wireable}


def _portScenePos(hostItem: QGraphicsItem, ports: dict, connectorName: str) -> QPointF | None:
  port = ports.get(connectorName)
  return None if port is None else hostItem.mapToScene(port.pos())


_RESIZE_MARGIN = 8.0
_MIN_ICON_SIZE = 24.0

_EDGE_CURSORS = {
  ('left',): Qt.CursorShape.SizeHorCursor,
  ('right',): Qt.CursorShape.SizeHorCursor,
  ('top',): Qt.CursorShape.SizeVerCursor,
  ('bottom',): Qt.CursorShape.SizeVerCursor,
  ('left', 'top'): Qt.CursorShape.SizeFDiagCursor,
  ('right', 'bottom'): Qt.CursorShape.SizeFDiagCursor,
  ('right', 'top'): Qt.CursorShape.SizeBDiagCursor,
  ('left', 'bottom'): Qt.CursorShape.SizeBDiagCursor,
}


class ElementIconItem(QGraphicsRectItem):
  '''One child element (System/Component/ComponentTable) of the currently
  displayed system, drawn as a labelled box with its connectors as ports on
  its border. `element.elementgeometry` is always a real ElementGeometry by
  the time this is constructed (DiagramScene assigns one to fallback-
  positioned elements before building items).

  Draggable from its middle (moves it) or from within _RESIZE_MARGIN of an
  edge/corner (resizes it, opposite edge(s) staying fixed) -- both commit
  straight back into elementgeometry, translated back to SSD's Y-up
  convention, so the model stays the single source of truth. Resizing also
  repositions the ports, whose fractional [0,1] placement is relative to
  this icon's current size.

  `onMoved`, if given, is called (no args) once a move or resize completes,
  so the owning scene can rebuild -- connections aren't live-tracked during
  the drag itself, only once it settles.
  '''

  def __init__(self, name: str, element, sceneRect: QRectF, onMoved=None, parent=None):
    super().__init__(0, 0, sceneRect.width(), sceneRect.height(), parent)
    self.setPos(sceneRect.topLeft())
    self.name = name
    self.element = element
    self._onMoved = onMoved
    self._dragStartScenePos = sceneRect.topLeft()
    self._resizeEdges: tuple[str, ...] | None = None
    self._resizeStartRect: QRectF | None = None
    self._resizeStartScenePos: QPointF | None = None
    self._resizeStartMouseScenePos: QPointF | None = None

    self.setBrush(QBrush(QColor(235, 238, 245)))
    self.setPen(QPen(QColor(90, 90, 90)))
    self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
    self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
    self.setAcceptHoverEvents(True)
    self.setZValue(1)
    self.setToolTip(name)

    self._label = QGraphicsSimpleTextItem(name, self)
    self._label.setPos(4, 4)

    self.ports = _createPorts(self, getattr(element, 'connectors', []), self.rect(), onMoved)

  def portScenePos(self, connectorName: str) -> QPointF | None:
    return _portScenePos(self, self.ports, connectorName)

  # --- move ------------------------------------------------------------------

  def mouseReleaseEvent(self, event) -> None:
    if self._resizeEdges is not None:
      self._commitResize()
      self._resizeEdges = None
      event.accept()
      return
    super().mouseReleaseEvent(event)
    self.commitPositionIfMoved()

  def commitPositionIfMoved(self) -> None:
    '''Writes self.pos()'s delta from the last commit into elementgeometry
    (translated back to SSD's Y-up convention) and notifies onMoved. Split
    out from mouseReleaseEvent so it can be exercised without a real Qt
    mouse-event sequence.'''
    newScenePos = self.pos()
    delta = newScenePos - self._dragStartScenePos
    self._dragStartScenePos = newScenePos
    if delta.isNull():
      return

    geometry = self.element.elementgeometry
    if geometry is None:
      return

    # Scene X maps directly to SSD x; scene Y is negated SSD y (see module
    # docstring), so a downward screen move (positive dy) is a decrease in y.
    geometry.x1 += delta.x()
    geometry.x2 += delta.x()
    geometry.y1 -= delta.y()
    geometry.y2 -= delta.y()

    if self._onMoved is not None:
      self._onMoved()

  # --- resize ------------------------------------------------------------------

  def _edgesNear(self, pos: QPointF) -> tuple[str, ...]:
    rect = self.rect()
    edges = []
    if abs(pos.x() - rect.left()) <= _RESIZE_MARGIN:
      edges.append('left')
    elif abs(pos.x() - rect.right()) <= _RESIZE_MARGIN:
      edges.append('right')
    if abs(pos.y() - rect.top()) <= _RESIZE_MARGIN:
      edges.append('top')
    elif abs(pos.y() - rect.bottom()) <= _RESIZE_MARGIN:
      edges.append('bottom')
    return tuple(edges)

  def hoverMoveEvent(self, event) -> None:
    edges = self._edgesNear(event.pos())
    self.setCursor(_EDGE_CURSORS.get(edges, Qt.CursorShape.SizeAllCursor))
    super().hoverMoveEvent(event)

  def hoverLeaveEvent(self, event) -> None:
    self.unsetCursor()
    super().hoverLeaveEvent(event)

  def mousePressEvent(self, event) -> None:
    edges = self._edgesNear(event.pos())
    if edges:
      self._resizeEdges = edges
      self._resizeStartRect = QRectF(self.rect())
      self._resizeStartScenePos = self.pos()
      self._resizeStartMouseScenePos = event.scenePos()
      event.accept()
      return
    self._resizeEdges = None
    super().mousePressEvent(event)

  def mouseMoveEvent(self, event) -> None:
    if self._resizeEdges is None:
      super().mouseMoveEvent(event)
      return

    delta = event.scenePos() - self._resizeStartMouseScenePos
    rect = QRectF(self._resizeStartRect)
    pos = QPointF(self._resizeStartScenePos)

    if 'right' in self._resizeEdges:
      rect.setWidth(max(_MIN_ICON_SIZE, self._resizeStartRect.width() + delta.x()))
    elif 'left' in self._resizeEdges:
      newWidth = max(_MIN_ICON_SIZE, self._resizeStartRect.width() - delta.x())
      pos.setX(self._resizeStartScenePos.x() + (self._resizeStartRect.width() - newWidth))
      rect.setWidth(newWidth)

    if 'bottom' in self._resizeEdges:
      rect.setHeight(max(_MIN_ICON_SIZE, self._resizeStartRect.height() + delta.y()))
    elif 'top' in self._resizeEdges:
      newHeight = max(_MIN_ICON_SIZE, self._resizeStartRect.height() - delta.y())
      pos.setY(self._resizeStartScenePos.y() + (self._resizeStartRect.height() - newHeight))
      rect.setHeight(newHeight)

    self.prepareGeometryChange()
    self.setRect(0, 0, rect.width(), rect.height())
    self.setPos(pos)
    self._repositionPorts()
    event.accept()

  def _repositionPorts(self) -> None:
    '''Re-derives each port's local position from its connector's fractional
    (x,y) against this icon's *current* rect -- called live during a resize
    so ports stay on the border instead of drifting into the icon.'''
    localRect = self.rect()
    for port in self.ports.values():
      geometry = port.connector.connectorGeometry
      port._localRect = localRect
      port.setPos(localRect.left() + geometry.x * localRect.width(),
                  localRect.top() + (1.0 - geometry.y) * localRect.height())

  def _commitResize(self) -> None:
    '''Writes the settled rect+position into elementgeometry (translated
    back to SSD's Y-up convention) and notifies onMoved.'''
    geometry = self.element.elementgeometry
    if geometry is not None:
      scenePos = self.pos()
      rect = self.rect()
      geometry.x1 = scenePos.x()
      geometry.x2 = scenePos.x() + rect.width()
      geometry.y1 = -(scenePos.y() + rect.height())
      geometry.y2 = -scenePos.y()

    self._dragStartScenePos = self.pos()
    for port in self.ports.values():
      port._dragStartScenePos = port.pos()

    if self._onMoved is not None:
      self._onMoved()


class SystemBoundaryItem(QGraphicsRectItem):
  '''The currently displayed system's own boundary -- a dashed frame hosting
  ports for the system's own (top-level) connectors, i.e. the ports that
  connect this system to its parent.'''

  def __init__(self, system, sceneRect: QRectF, onMoved=None, parent=None):
    super().__init__(0, 0, sceneRect.width(), sceneRect.height(), parent)
    self.setPos(sceneRect.topLeft())

    pen = QPen(QColor(160, 160, 160))
    pen.setStyle(Qt.PenStyle.DashLine)
    self.setPen(pen)
    self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
    self.setZValue(-1)

    localRect = QRectF(0, 0, sceneRect.width(), sceneRect.height())
    self.ports = _createPorts(self, system.connectors, localRect, onMoved)

  def portScenePos(self, connectorName: str) -> QPointF | None:
    return _portScenePos(self, self.ports, connectorName)


class ConnectionItem(QGraphicsPathItem):
  '''A connection between two resolved port scene positions. Honors
  connectionGeometry.pointsX/pointsY waypoints when present (same Y-up
  convention as ElementGeometry), otherwise draws a straight line.'''

  def __init__(self, connection, startPos: QPointF, endPos: QPointF, parent=None):
    super().__init__(parent)
    self.connection = connection

    path = QPainterPath(startPos)
    geometry = connection.connectionGeometry
    if geometry is not None and geometry.pointsX and len(geometry.pointsX) == len(geometry.pointsY):
      for px, py in zip(geometry.pointsX, geometry.pointsY):
        path.lineTo(px, -py)
    path.lineTo(endPos)
    self.setPath(path)

    self.setPen(QPen(QColor(60, 60, 60), 1.5))
    self.setZValue(0)
    self.setToolTip(f'{connection.startElement}.{connection.startConnector} -> '
                     f'{connection.endElement}.{connection.endConnector}')
