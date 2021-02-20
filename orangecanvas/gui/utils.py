"""
Helper utilities

"""
import sys
import traceback
import ctypes

from contextlib import contextmanager

from AnyQt.QtWidgets import (
    QWidget, QMessageBox, QStyleOption, QStyle, QTextEdit, QScrollBar,
    QApplication
)
from AnyQt.QtGui import (
    QGradient, QLinearGradient, QRadialGradient, QBrush, QPainter,
    QPaintEvent, QColor, QPixmap, QPixmapCache, QTextOption,
    QPalette
)
from AnyQt.QtCore import Qt, QPointF, QPoint, QRect, QRectF, Signal, QEvent

import sip

from orangecanvas.registry import NAMED_COLORS, DEFAULT_COLOR


@contextmanager
def updates_disabled(widget):
    """Disable QWidget updates (using QWidget.setUpdatesEnabled)
    """
    old_state = widget.updatesEnabled()
    widget.setUpdatesEnabled(False)
    try:
        yield
    finally:
        widget.setUpdatesEnabled(old_state)


@contextmanager
def signals_disabled(qobject):
    """Disables signals on an instance of QObject.
    """
    old_state = qobject.signalsBlocked()
    qobject.blockSignals(True)
    try:
        yield
    finally:
        qobject.blockSignals(old_state)


@contextmanager
def disabled(qobject):
    """Disables a disablable QObject instance.
    """
    if not (hasattr(qobject, "setEnabled") and hasattr(qobject, "isEnabled")):
        raise TypeError("%r does not have 'enabled' property" % qobject)

    old_state = qobject.isEnabled()
    qobject.setEnabled(False)
    try:
        yield
    finally:
        qobject.setEnabled(old_state)


def StyledWidget_paintEvent(self, event):
    # type: (QWidget, QPaintEvent) -> None
    """A default styled QWidget subclass  paintEvent function.
    """
    opt = QStyleOption()
    opt.initFrom(self)
    painter = QPainter(self)
    self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)


class StyledWidget(QWidget):
    """
    """
    paintEvent = StyledWidget_paintEvent  # type: ignore


class ScrollBar(QScrollBar):
    #: Emitted when the scroll bar receives a StyleChange event
    styleChange = Signal()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.StyleChange:
            self.styleChange.emit()
        super().changeEvent(event)


def is_transparency_supported():  # type: () -> bool
    """Is window transparency supported by the current windowing system.
    """
    if sys.platform == "win32":
        return is_dwm_compositing_enabled()
    elif sys.platform == "cygwin":
        return False
    elif sys.platform == "darwin":
        if has_x11():
            return is_x11_compositing_enabled()
        else:
            # Quartz compositor
            return True
    elif sys.platform.startswith("linux"):
        # TODO: wayland??
        return is_x11_compositing_enabled()
    elif sys.platform.startswith("freebsd"):
        return is_x11_compositing_enabled()
    elif has_x11():
        return is_x11_compositing_enabled()
    else:
        return False


def has_x11():  # type: () -> bool
    """Is Qt build against X11 server.
    """
    try:
        from AnyQt.QtX11Extras import QX11Info
        return True
    except ImportError:
        return False


def is_x11_compositing_enabled():  # type: () -> bool
    """Is X11 compositing manager running.
    """
    try:
        from AnyQt.QtX11Extras import QX11Info
    except ImportError:
        return False
    if hasattr(QX11Info, "isCompositingManagerRunning"):
        return QX11Info.isCompositingManagerRunning()
    else:
        # not available on Qt5
        return False  # ?


def is_dwm_compositing_enabled():  # type: () -> bool
    """Is Desktop Window Manager compositing (Aero) enabled.
    """
    enabled = ctypes.c_bool(False)
    try:
        DwmIsCompositionEnabled = \
            ctypes.windll.dwmapi.DwmIsCompositionEnabled  # type: ignore
    except (AttributeError, WindowsError):
        # dwmapi or DwmIsCompositionEnabled is not present
        return False

    rval = DwmIsCompositionEnabled(ctypes.byref(enabled))

    return rval == 0 and enabled.value


def gradient_darker(grad, factor):
    # type: (QGradient, float) -> QGradient
    """Return a copy of the QGradient darkened by factor.

    .. note:: Only QLinearGradeint and QRadialGradient are supported.

    """
    if type(grad) is QGradient:
        if grad.type() == QGradient.LinearGradient:
            grad = sip.cast(grad, QLinearGradient)
        elif grad.type() == QGradient.RadialGradient:
            grad = sip.cast(grad, QRadialGradient)

    if isinstance(grad, QLinearGradient):
        new_grad = QLinearGradient(grad.start(), grad.finalStop())
    elif isinstance(grad, QRadialGradient):
        new_grad = QRadialGradient(grad.center(), grad.radius(),
                                   grad.focalPoint())
    else:
        raise TypeError

    new_grad.setCoordinateMode(grad.coordinateMode())

    for pos, color in grad.stops():
        new_grad.setColorAt(pos, color.darker(factor))

    return new_grad


def brush_darker(brush: QBrush, factor: bool) -> QBrush:
    """Return a copy of the brush darkened by factor.
    """
    grad = brush.gradient()
    if grad:
        return QBrush(gradient_darker(grad, factor))
    else:
        brush = QBrush(brush)
        brush.setColor(brush.color().darker(factor))
        return brush


def relative_luminance(color: QColor):
    vR = color.redF()
    vG = color.greenF()
    vB = color.blueF()

    def sRGBtoLin(c):
        if c <= 0.04045:
            return c / 12.92
        else:
            return pow(((c + 0.055) / 1.055), 2.4)

    Y = (0.2126 * sRGBtoLin(vR) +
         0.7152 * sRGBtoLin(vG) +
         0.0722 * sRGBtoLin(vB))

    return Y


def lstar(color):
    Y = relative_luminance(color)
    if Y <= 216 / 24389:
        Lstar = Y * (24389 / 27)
    else:
        Lstar = pow(Y, (1 / 3)) * 116 - 16

    return Lstar


def contrast_ratio(c1, c2):
    v1 = relative_luminance(c1)
    v2 = relative_luminance(c2)
    if v1 < v2:
        _ = v2
        v2 = v1
        v1 = _
    return (v1 + 0.05) / (v2 + 0.05)


def foreground_for_background(bg: QColor):
    if lstar(bg) < 50:
        return QColor(Qt.white)
    else:
        return QColor(Qt.black)


def saturated(color, factor=150):
    # type: (QColor, int) -> QColor
    """Return a saturated color.
    """
    h = color.hsvHueF()
    s = color.hsvSaturationF()
    v = color.valueF()
    a = color.alphaF()
    s = factor * s / 100.0
    s = max(min(1.0, s), 0.0)
    return QColor.fromHsvF(h, s, v, a).convertTo(color.spec())


def create_palette(background):
    # type: (Any) -> QPalette
    """
    Return a new :class:`QPalette` from for the :class:`NodeBodyItem`.
    """
    app = QApplication.instance()
    darkMode = app.property('darkMode')

    defaults = {
        # Canvas widget background radial gradient
        QPalette.Light:
            lambda color: saturated(color, 50),
        QPalette.Midlight:
            lambda color: saturated(color, 90),
        QPalette.Button:
            lambda color: color,
        # Canvas widget shadow
        QPalette.Shadow:
            lambda color: saturated(color, 125) if darkMode else
                          saturated(color, 150),

        # Category tab color
        QPalette.Highlight:
            lambda color: color,

        QPalette.HighlightedText:
            lambda color: foreground_for_background(color),
    }

    palette = QPalette()

    if isinstance(background, dict):
        if app.property('darkMode'):
            background = background.get('dark', next(iter(background.values())))
        else:
            background = background.get('light', next(iter(background.values())))
        base_color = background[QPalette.Button]
        base_color = QColor(base_color)
    else:
        color = NAMED_COLORS.get(background, background)
        color = QColor(background)
        if color.isValid():
            base_color = color
        else:
            color = NAMED_COLORS[DEFAULT_COLOR]
            base_color = QColor(color)

    for role, default in defaults.items():
        if isinstance(background, dict) and role in background:
            v = background[role]
            color = NAMED_COLORS.get(v, v)
            color = QColor(color)
            if color.isValid():
                palette.setColor(role, color)
                continue
        color = default(base_color)
        palette.setColor(role, color)

    return palette


def default_palette():
    # type: () -> QPalette
    """
    Create and return a default palette for a node.
    """
    return create_palette(DEFAULT_COLOR)


def create_gradient(base_color: QColor, stop=QPointF(0, 0),
                    finalStop=QPointF(0, 1)) -> QLinearGradient:
    """
    Create a default linear gradient using `base_color` .
    """
    grad = QLinearGradient(stop, finalStop)
    grad.setStops([(0.0, base_color),
                   (0.5, base_color),
                   (0.8, base_color.darker(105)),
                   (1.0, base_color.darker(110)),
                   ])
    grad.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
    return grad


def create_css_gradient(base_color: QColor, stop=QPointF(0, 0),
                        finalStop=QPointF(0, 1)) -> str:
    """
    Create a Qt css linear gradient fragment based on the `base_color`.
    """
    gradient = create_gradient(base_color, stop, finalStop)
    return css_gradient(gradient)


def css_gradient(gradient: QLinearGradient) -> str:
    """
    Given an instance of a `QLinearGradient` return an equivalent qt css
    gradient fragment.
    """
    stop, finalStop = gradient.start(), gradient.finalStop()
    x1, y1, x2, y2 = stop.x(), stop.y(), finalStop.x(), finalStop.y()
    stops = gradient.stops()
    stops = "\n".join("    stop: {0:f} {1}".format(stop, color.name())
                      for stop, color in stops)
    return ("qlineargradient(\n"
            "    x1: {x1}, y1: {y1}, x2: {x2}, y2: {y2},\n"
            "{stops})").format(x1=x1, y1=y1, x2=x2, y2=y2, stops=stops)


def message_critical(text, title=None, informative_text=None, details=None,
                     buttons=None, default_button=None, exc_info=False,
                     parent=None):
    """Show a critical message.
    """
    if not text:
        text = "An unexpected error occurred."

    if title is None:
        title = "Error"

    return message(QMessageBox.Critical, text, title, informative_text,
                   details, buttons, default_button, exc_info, parent)


def message_warning(text, title=None, informative_text=None, details=None,
                    buttons=None, default_button=None, exc_info=False,
                    parent=None):
    """Show a warning message.
    """
    if not text:
        import random
        text_candidates = ["Death could come at any moment.",
                           "Murphy lurks about. Remember to save frequently."
                           ]
        text = random.choice(text_candidates)

    if title is not None:
        title = "Warning"

    return message(QMessageBox.Warning, text, title, informative_text,
                   details, buttons, default_button, exc_info, parent)


def message_information(text, title=None, informative_text=None, details=None,
                        buttons=None, default_button=None, exc_info=False,
                        parent=None):
    """Show an information message box.
    """
    if title is None:
        title = "Information"
    if not text:
        text = "I am not a number."

    return message(QMessageBox.Information, text, title, informative_text,
                   details, buttons, default_button, exc_info, parent)


def message_question(text, title, informative_text=None, details=None,
                     buttons=None, default_button=None, exc_info=False,
                     parent=None):
    """Show an message box asking the user to select some
    predefined course of action (set by buttons argument).

    """
    return message(QMessageBox.Question, text, title, informative_text,
                   details, buttons, default_button, exc_info, parent)


def message(icon, text, title=None, informative_text=None, details=None,
            buttons=None, default_button=None, exc_info=False, parent=None):
    """Show a message helper function.
    """
    if title is None:
        title = "Message"
    if not text:
        text = "I am neither a postman nor a doctor."

    if buttons is None:
        buttons = QMessageBox.Ok

    if details is None and exc_info:
        details = traceback.format_exc(limit=20)

    mbox = QMessageBox(icon, title, text, buttons, parent)

    if informative_text:
        mbox.setInformativeText(informative_text)

    if details:
        mbox.setDetailedText(details)
        dtextedit = mbox.findChild(QTextEdit)
        if dtextedit is not None:
            dtextedit.setWordWrapMode(QTextOption.NoWrap)

    if default_button is not None:
        mbox.setDefaultButton(default_button)

    return mbox.exec_()


def innerGlowBackgroundPixmap(light_color, dark_color, size, radius=10):
    """ Draws radial gradient pixmap, then uses that to draw
    a rounded-corner gradient rectangle pixmap.

    Args:
        light_color (QColor): used as inner color
        dark_color (QColor): used as outer color
        size (QSize): size of output pixmap
        radius (int): radius of inner glow rounded corners
    """
    key = "InnerGlowBackground " + \
          light_color.name() + " " + \
          dark_color.name() + " " + \
          str(radius)

    bg = QPixmapCache.find(key)
    if bg:
        return bg

    # initialize radial gradient
    center = QPoint(radius, radius)
    pixRect = QRect(0, 0, radius * 2, radius * 2)
    gradientPixmap = QPixmap(radius * 2, radius * 2)
    gradientPixmap.fill(dark_color)

    # draw radial gradient pixmap
    pixPainter = QPainter(gradientPixmap)
    pixPainter.setPen(Qt.NoPen)
    gradient = QRadialGradient(center, radius - 1)
    gradient.setColorAt(0, light_color)
    gradient.setColorAt(1, dark_color)
    pixPainter.setBrush(gradient)
    pixPainter.drawRect(pixRect)
    pixPainter.end()

    # set tl and br to the gradient's square-shaped rect
    tl = QPoint(0, 0)
    br = QPoint(size.width(), size.height())

    # fragments of radial gradient pixmap to create rounded gradient outline rectangle
    frags = [
        # top-left corner
        QPainter.PixmapFragment.create(
            QPointF(tl.x() + radius / 2, tl.y() + radius / 2),
            QRectF(0, 0, radius, radius)
        ),
        # top-mid 'linear gradient'
        QPainter.PixmapFragment.create(
            QPointF(tl.x() + (br.x() - tl.x()) / 2, tl.y() + radius / 2),
            QRectF(radius, 0, 1, radius),
            scaleX=(br.x() - tl.x() - 2 * radius)
        ),
        # top-right corner
        QPainter.PixmapFragment.create(
            QPointF(br.x() - radius / 2, tl.y() + radius / 2),
            QRectF(radius, 0, radius, radius)
        ),
        # left-mid 'linear gradient'
        QPainter.PixmapFragment.create(
            QPointF(tl.x() + radius / 2, tl.y() + (br.y() - tl.y()) / 2),
            QRectF(0, radius, radius, 1),
            scaleY=(br.y() - tl.y() - 2 * radius)
        ),
        # mid solid
        QPainter.PixmapFragment.create(
            QPointF(tl.x() + (br.x() - tl.x()) / 2, tl.y() + (br.y() - tl.y()) / 2),
            QRectF(radius, radius, 1, 1),
            scaleX=(br.x() - tl.x() - 2 * radius),
            scaleY=(br.y() - tl.y() - 2 * radius)
        ),
        # right-mid 'linear gradient'
        QPainter.PixmapFragment.create(
            QPointF(br.x() - radius / 2, tl.y() + (br.y() - tl.y()) / 2),
            QRectF(radius, radius, radius, 1),
            scaleY=(br.y() - tl.y() - 2 * radius)
        ),
        # bottom-left corner
        QPainter.PixmapFragment.create(
            QPointF(tl.x() + radius / 2, br.y() - radius / 2),
            QRectF(0, radius, radius, radius)
        ),
        # bottom-mid 'linear gradient'
        QPainter.PixmapFragment.create(
            QPointF(tl.x() + (br.x() - tl.x()) / 2, br.y() - radius / 2),
            QRectF(radius, radius, 1, radius),
            scaleX=(br.x() - tl.x() - 2 * radius)
        ),
        # bottom-right corner
        QPainter.PixmapFragment.create(
            QPointF(br.x() - radius / 2, br.y() - radius / 2),
            QRectF(radius, radius, radius, radius)
        ),
    ]

    # draw icon background to pixmap
    outPix = QPixmap(size.width(), size.height())
    outPainter = QPainter(outPix)
    outPainter.setPen(Qt.NoPen)
    outPainter.drawPixmapFragments(frags,
                                   gradientPixmap,
                                   QPainter.PixmapFragmentHints(QPainter.OpaqueHint))
    outPainter.end()

    QPixmapCache.insert(key, outPix)

    return outPix


def shadowTemplatePixmap(color, length):
    """
    Returns 1 pixel wide, `length` pixels long linear-gradient.

    Args:
        color (QColor): shadow color
        length (int): length of cast shadow

    """
    key = "InnerShadowTemplate " + \
          color.name() + " " + \
          str(length)

    # get cached template
    shadowPixmap = QPixmapCache.find(key)
    if shadowPixmap:
        return shadowPixmap

    shadowPixmap = QPixmap(1, length)
    shadowPixmap.fill(Qt.transparent)

    grad = QLinearGradient(0, 0, 0, length)
    grad.setColorAt(0, color)
    grad.setColorAt(1, Qt.transparent)

    painter = QPainter()
    painter.begin(shadowPixmap)
    painter.fillRect(shadowPixmap.rect(), grad)
    painter.end()

    # cache template
    QPixmapCache.insert(key, shadowPixmap)

    return shadowPixmap


def innerShadowPixmap(color, size, pos, length=5):
    """
    Args:
        color (QColor): shadow color
        size (QSize): size of pixmap
        pos (int): shadow position int flag, use bitwise operations
            1 - top
            2 - right
            4 - bottom
            8 - left
        length (int): length of cast shadow
    """
    key = "InnerShadow " + \
          color.name() + " " + \
          str(size) + " " + \
          str(pos) + " " + \
          str(length)
    # get cached shadow if it exists
    finalShadow = QPixmapCache.find(key)
    if finalShadow:
        return finalShadow

    shadowTemplate = shadowTemplatePixmap(color, length)

    finalShadow = QPixmap(size)
    finalShadow.fill(Qt.transparent)
    shadowPainter = QPainter(finalShadow)
    shadowPainter.setCompositionMode(QPainter.CompositionMode_Darken)

    # top/bottom rect
    targetRect = QRect(0, 0, size.width(), length)

    # shadow on top
    if pos & 1:
        shadowPainter.drawPixmap(targetRect, shadowTemplate, shadowTemplate.rect())
    # shadow on bottom
    if pos & 4:
        shadowPainter.save()

        shadowPainter.translate(QPointF(0, size.height()))
        shadowPainter.scale(1, -1)
        shadowPainter.drawPixmap(targetRect, shadowTemplate, shadowTemplate.rect())

        shadowPainter.restore()

    # left/right rect
    targetRect = QRect(0, 0, size.height(), shadowTemplate.rect().height())

    # shadow on the right
    if pos & 2:
        shadowPainter.save()

        shadowPainter.translate(QPointF(size.width(), 0))
        shadowPainter.rotate(90)
        shadowPainter.drawPixmap(targetRect, shadowTemplate, shadowTemplate.rect())

        shadowPainter.restore()
    # shadow on left
    if pos & 8:
        shadowPainter.save()

        shadowPainter.translate(0, size.height())
        shadowPainter.rotate(-90)
        shadowPainter.drawPixmap(targetRect, shadowTemplate, shadowTemplate.rect())

        shadowPainter.restore()

    shadowPainter.end()

    # cache shadow
    QPixmapCache.insert(key, finalShadow)

    return finalShadow
