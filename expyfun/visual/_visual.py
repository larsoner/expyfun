"""Tools for drawing shapes and text on the screen"""

# Authors: Dan McCloy <drmccloy@uw.edu>
#          Eric Larson <larsoner@uw.edu>
#
# License: BSD (3-clause)

# make RawImage work

import numpy as np
import pyglet
from matplotlib.colors import colorConverter

from .._utils import _check_units


def _convert_color(color):
    """Convert 3- or 4-element color into OpenGL usable color"""
    color = 255 * np.array(colorConverter.to_rgba(color))
    color = color.astype(np.uint8)
    return color


def _replicate_color(color, pts):
    """Convert single color to color array for OpenGL trianglulations"""
    return np.tile(color, len(pts) / 2)


##############################################################################
# Text

class Text(object):
    def __init__(self, ec, text, pos=[0, 0], color='white',
                 font_name='Arial', font_size=24, height=None,
                 v_align='center'):
        pos = np.array(pos)[:, np.newaxis]
        pos = ec._convert_units(pos, 'norm', 'pix')
        width = float(ec.window_size_pix[0]) * 0.8
        #pos -= np.array([width / 2., height / 2.])[:, np.newaxis]
        self._text = pyglet.text.HTMLLabel(text + ' ', x=pos[0], y=pos[1],
                                           width=width, height=None,
                                           multiline=True, dpi=int(ec.dpi),
                                           anchor_x='center',
                                           anchor_y='center')
        self._text.color = tuple(_convert_color(color))
        self._text.font_name = font_name
        self._text.font_size = font_size

    def draw(self):
        self._text.draw()


##############################################################################
# Triangulations

class _Triangular(object):
    """Super class for objects that use trianglulations"""
    def __init__(self, ec, fill_color, line_color, line_width, line_loop):
        self._ec = ec
        self.set_fill_color(fill_color)
        self.set_line_color(line_color)
        self._line_width = line_width
        self._line_loop = line_loop  # whether or not lines drawn are looped

    def set_fill_color(self, fill_color):
        """Set the object color

        Parameters
        ----------
        fill_color : matplotlib Color | None
            The fill color. Use None for no fill.
        """
        if fill_color is not None:
            self._fill_color = _convert_color(fill_color)
        else:
            self._fill_color = None

    def set_line_color(self, line_color):
        """Set the object color

        Parameters
        ----------
        fill_color : matplotlib Color | None
            The fill color. Use None for no fill.
        """
        if line_color is not None:
            self._line_color = _convert_color(line_color)
        else:
            self._line_color = None

    def set_line_width(self, line_width, units='norm'):
        """Set the line width in pixels

        Parameters
        ----------
        line_width : float
            The line width. Must be given in pixels. Due to OpenGL
            limitations, it must be `0.0 <= line_width <= 10.0`.
        """
        line_width = float(line_width)
        if not (0.0 <= line_width <= 10.0):
            raise ValueError('line_width must be between 0 and 10')
        self._line_width = line_width

    def draw(self):
        """Draw the object to the display buffer"""
        if self._fill_color is not None:
            color = _replicate_color(self._fill_color, self._points)
            pyglet.graphics.draw_indexed(len(self._points) / 2,
                                         pyglet.gl.GL_TRIANGLES,
                                         self._tris,
                                         ('v2f', self._points),
                                         ('c4B', color))
        if self._line_color is not None and self._line_width > 0.0:
            color = _replicate_color(self._line_color, self._line_points)
            pyglet.gl.glLineWidth(self._line_width)
            if self._line_loop:
                gl_cmd = pyglet.gl.GL_LINE_LOOP
            else:
                gl_cmd = pyglet.gl.GL_LINES
            pyglet.graphics.draw(len(self._line_points) / 2,
                                 gl_cmd,
                                 ('v2f', self._line_points),
                                 ('c4B', color))


class Line(_Triangular):
    def __init__(self, ec, coords, units='norm', line_color='white',
                 line_width=1.0):
        _Triangular.__init__(self, ec, fill_color=None, line_color=line_color,
                             line_width=line_width, line_loop=False)
        self._points = None
        self._tris = None
        self.set_coords(coords, units)
        self.set_line_color(line_color)

    def set_coords(self, coords, units='norm'):
        coords = np.array(coords, dtype=float)
        if coords.ndim == 1:
            coords = coords[:, np.newaxis]
        if coords.ndim != 2 or coords.shape[0] != 2:
            raise ValueError('coords must be a vector of length 2, or an '
                             'array with 2 dimensions (with first dimension '
                             'having length 2')
        self._line_points = coords


class Rectangle(_Triangular):
    def __init__(self, ec, pos, units='norm', fill_color='white',
                 line_color=None, line_width=1.0):
        _Triangular.__init__(self, ec, fill_color=fill_color,
                             line_color=line_color, line_width=line_width,
                             line_loop=True)
        self.set_pos(pos, units)

    def set_pos(self, pos, units='norm'):
        """Set the position of the rectangle

        Parameters
        ----------
        pos : array-like
            X, Y, width, height of the rectangle.
        units : str
            Units to use.
        """
        _check_units(units)
        # do this in normalized units, then convert
        pos = np.array(pos)
        if not pos.ndim == 1 and pos.size == 4:
            raise ValueError('pos must be a 4-element array-like vector')
        self._pos = pos
        w = self._pos[2]
        h = self._pos[3]
        points = np.array([[-w / 2., -h / 2.],
                           [-w / 2., h / 2.],
                           [w / 2., h / 2.],
                           [w / 2., -h / 2.]]).T
        points += np.array(self._pos[:2])[:, np.newaxis]
        points = self._ec._convert_units(points, units, 'pix')
        self._points = points.T.ravel()
        self._tris = np.array([0, 1, 2, 0, 2, 3])
        self._line_points = self._points  # all 4 points used for line drawing


class Circle(_Triangular):
    def __init__(self, ec, radius=1, pos=[0, 0], units='norm',
                 n_edges=200, fill_color='white', line_color=None,
                 line_width=1.0):
        _Triangular.__init__(self, ec, fill_color=fill_color,
                             line_color=line_color, line_width=line_width,
                             line_loop=True)
        if not isinstance(n_edges, int):
            raise TypeError('n_edges must be an int')
        if n_edges < 4:
            raise ValueError('n_edges must be >= 4 for a reasonable circle')
        self._n_edges = n_edges

        # need to set a dummy value here so recalculation doesn't fail
        self._radius = np.array([1., 1.])
        self.set_pos(pos, units)
        self.set_radius(radius, units)

        # construct triangulation (never changes so long as n_edges is fixed)
        tris = [[0, ii + 1, ii + 2] for ii in range(n_edges)]
        tris = np.concatenate(tris)
        tris[-1] = 1  # fix wrap for last triangle
        self._tris = tris

    def set_radius(self, radius, units='norm'):
        """Set the position and radius of the circle

        Parameters
        ----------
        radius : array-like | float
            X- and Y-direction extents (radii) of the circle / ellipse.
            A single value (float) will be replicated for both directions.
        units : str
            Units to use.
        """
        _check_units(units)
        radius = np.atleast_1d(radius).astype(float)
        if not radius.ndim == 1 or radius.size > 2:
            raise ValueError('pos must be a 2-element array-like vector')
        if radius.size == 1:
            radius = np.r_[radius, radius]
        # convert to pixel (OpenGL) units
        self._radius = self._ec._convert_units(radius[:, np.newaxis],
                                               units, 'pix')[:, 0]
        # need to subtract center position
        ctr = self._ec._convert_units(np.zeros((2, 1)), units, 'pix')[:, 0]
        self._radius -= ctr
        self._recalculate()

    def set_pos(self, pos, units='norm'):
        """Set the position and radius of the circle

        Parameters
        ----------
        pos : array-like
            X, Y center of the circle.
        units : str
            Units to use.
        """
        _check_units(units)
        pos = np.array(pos, dtype=float)
        if not pos.ndim == 1 and pos.size == 2:
            raise ValueError('pos must be a 2-element array-like vector')
        # convert to pixel (OpenGL) units
        self._pos = self._ec._convert_units(pos[:, np.newaxis],
                                            units, 'pix')[:, 0]
        self._recalculate()

    def _recalculate(self):
        """Helper to recalculate point coordinates"""
        edges = self._n_edges
        arg = 2 * np.pi * (np.arange(edges) / float(edges))
        points = np.array([self._radius[0] * np.cos(arg),
                           self._radius[1] * np.sin(arg)])
        points = np.c_[np.zeros((2, 1)), points]  # prepend the center
        points += np.array(self._pos[:2], dtype=float)[:, np.newaxis]
        self._points = points.T.ravel()
        self._line_points = self._points[2:]  # omit center point for lines


##############################################################################
# Image display

class RawImage(object):
    def __init__(self, ec, image_buffer, pos=(0, 0), size=(1, 1),
                 units='norm'):
        pass

    def draw(self):
        pass
