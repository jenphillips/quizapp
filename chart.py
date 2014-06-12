import datetime
import random
import math
from itertools import chain

from dateutil.rrule import rrule, MONTHLY

from kivy.lang import Builder
from kivy.uix.scatterlayout import ScatterLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.properties import (ListProperty, ObjectProperty)

Builder.load_string(
"""
#: import c chart

<AxisLabel@Label>:
    size: self.texture_size
    size_hint: None, None
    color: c.AXIS_COLOR

<YAxisLabel@AxisLabel>:
    x: c.AXIS_MARGIN - 10 - self.width

<XAxisLabel@AxisLabel>:
    y:  c.AXIS_MARGIN - 10
    canvas.before:
        PushMatrix
        Rotate:
            angle: 30
            origin: self.pos
        Translate:
            x: -1 * self.width
            y: -1 * self.height
    canvas.after:
        PopMatrix

<NameLabel@AxisLabel>:
    y_index: 0
    axis_top: 0
    x: c.AXIS_MARGIN / 2 - self.width
    y: self.axis_top - (self.y_index + 1) * self.height
    font_size: "20dp"

<TimeSeriesChart>:
    do_rotation: False
    do_translation_y: False
    size_hint_x: None
    FloatLayout:
        canvas:
            # AXIS
            Color:
                rgba: c.AXIS_COLOR
            Line:
                points:[c.AXIS_MARGIN, self.height, c.AXIS_MARGIN, c.AXIS_MARGIN, self.width, c.AXIS_MARGIN]
                width: 1

<TimeSeries>:
    pos: c.AXIS_MARGIN + 1, c.AXIS_MARGIN + 1
    canvas:
        Color:
            rgb: self.line_color
        Line:
            points: self.pixel_points
            width: 1
"""
)

AXIS_MARGIN = dp(75)
AXIS_COLOR = [1.0, 1.0, 1.0, 0.50]
DATE_ROTATION = 30

def random_color_byte():
    return random.random() * 0.7 + 0.3

def random_color():
    return (
        random_color_byte(),
        random_color_byte(),
        random_color_byte(),
        )


class TimeSeries(RelativeLayout):
    '''
    Represents a single line in the chart.
    The data_points list is a list of 2-tuples of
    (datetime, value). The y axis is always a range from
    zero to the maximum value. If no maximum is supplied,
    it is inferred to be a round number higher than the highest
    value.

    pixel_points is the list of x, y locations at which the line should
    be drawn.
    '''
    data_points = ListProperty([])
    pixel_points = ListProperty([])
    line_color = ListProperty([1, 1, 1])
    chart = ObjectProperty()

    def __init__(self, **kwargs):
        self.bind(data_points=self.update_chart, chart=self.update_chart)
        super(TimeSeries, self).__init__(**kwargs)

    def update_chart(self, obj, value):
        if not self.chart:
            return

        self.width = self.chart.width - AXIS_MARGIN - 1
        self.height = self.chart.height - AXIS_MARGIN - 1 - AXIS_MARGIN / 2

        points = [
            ((
                (x - self.chart.min_date).days * self.chart.pixels_per_day,
                min(max((y - self.chart.min_y) * self.chart.pixels_per_step, 0), self.height)
            ))
            for x, y in self.data_points
            if x <= self.chart.max_date and x >= self.chart.min_date
        ]

        # flatten the list
        self.pixel_points = [x for t in points for x in t]


class TimeSeriesChart(ScatterLayout):
    '''
    Contains a collection of time series data. Draws the axes and labels.
    (Does not include a legend, yet). The maximum value can either be
    passed in or is calculated as the maximum of the maximum of each
    TimeSeries.
    '''
    date_steps = ListProperty([])
    y_steps = ListProperty([])
    time_series = ListProperty()
    legend = ListProperty()

    @property
    def min_date(self):
        return self.date_steps[0] if self.date_steps else datetime.date(1900, 1, 1)

    @property
    def max_date(self):
        return self.date_steps[-1] if self.date_steps else datetime.date(1900, 1, 1)

    @property
    def num_days(self):
        return (self.max_date - self.min_date).days

    @property
    def pixels_per_day(self):
        return float(self.width - AXIS_MARGIN) / (self.num_days or 1)

    @property
    def min_y(self):
        return self.y_steps[0] if self.y_steps else 0

    @property
    def max_y(self):
        return self.y_steps[-1] if self.y_steps else 0

    @property
    def num_steps(self):
        return self.max_y - self.min_y

    @property
    def pixels_per_step(self):
        return float(self.height - AXIS_MARGIN - AXIS_MARGIN / 2) / (self.num_steps or 1)

    def __init__(self, **kwargs):
        self.bind(
            date_steps=self.update_chart,
            y_steps=self.update_chart,
            legend=self.update_chart,
            width=self.update_chart,
            height=self.update_chart)

        super(TimeSeriesChart, self).__init__(**kwargs)

    def update_chart(self, obj, value):
        # Remove current axis labels if there are any
        children_to_remove = [c for c in self.content.children if isinstance(c, Factory.AxisLabel)]
        for child in children_to_remove:
            self.remove_widget(child)
        # Add the proper Axis labels
        self._add_axis_labels(Factory.XAxisLabel, self.date_steps, self.pixels_per_day, "x", "{:%Y%m%d}", lambda k: k.days)
        self._add_axis_labels(Factory.YAxisLabel, self.y_steps, self.pixels_per_step, "y")

        # Add the legend labels
        for i, (title, color) in enumerate(self.legend):
            label = Factory.NameLabel(text=title)
            label.color = list(color) + [1]
            label.axis_top = self.height - AXIS_MARGIN
            label.y_index = i
            self.add_widget(label)

        for time_series in self.time_series:
            time_series.update_chart(obj, value)

    def _add_axis_labels(self, label_class, steps, pixels_per_step, axis, format_string="{}", key=lambda k: k):
        '''
        As horrible as this method is, it's an overall reduction in total horrible.
        steps is known to have the minimum and maximum value at its extremes.
        margin_and_length is the height or width including axis margin
        '''
        for step in steps:
            label = label_class(
                text=format_string.format(step),
            )
            setattr(label, axis, AXIS_MARGIN + (key(step - steps[0])) * pixels_per_step)
            self.add_widget(label)

    def add_time_series(self, data_points, name, line_color=None):
        '''
        Adds a new time series to the graph.

        data_points is a list of 2-tuples of (datetime.date, value) pairs.
        line_color is either an rgb 3-tuple (0-1.0) or None, in which case a random
        color is generated.

        Does nothing to adjust the axes to take the new data into account.
        It is the caller's responsibility to ensure that date_range and y_axis_range
        are set on this object. This can be done before or after calling add_time_series.
        '''
        if not line_color:
            line_color = random_color()
        time_series = TimeSeries(
            chart=self,
            data_points=data_points,
            line_color=line_color,
            width=self.width - 51
        )

        self.time_series.append(time_series)
        self.legend.append((name, line_color))
        self.add_widget(time_series)

    def clear_time_series(self):
        '''
        Remove all time series from the graph. Does nothing to the axes.
        '''
        children_to_remove = [c for c in self.content.children if isinstance(c, TimeSeries)]
        for child in children_to_remove:
            self.remove_widget(child)
        del self.legend[:]


class AutoAxisTimeSeriesChart(TimeSeriesChart):
    '''
    A time series that sets the axis labels and min/max values automatically as timeseries
    are added.
    '''
    def add_time_series(self, data_points, name, line_color=None):
        super(AutoAxisTimeSeriesChart, self).add_time_series(data_points, name, line_color)

        new_min = min([t.data_points[0][0] for t in self.time_series if t.data_points])
        new_max = max([t.data_points[-1][0] for t in self.time_series if t.data_points])

        if new_min != self.min_date or new_max != self.max_date:
            interval = 2 if (new_max - new_min).days > 400 else 1
            self.date_steps = [d.date() for d in rrule(
                    MONTHLY,
                    interval=interval,
                    dtstart=new_min,
                    until=new_max
                )
            ]

            if (new_max - self.date_steps[-1]).days < 7 and len(self.date_steps) > 2:
                del self.date_steps[-1]

            if len(self.date_steps) == 1:
                self.date_steps.append(new_max)

            self.date_steps.append(new_max)

        self.width = max(dp(400), len(self.date_steps))

        all_data_points = set(chain(*[t.data_points for t in self.time_series]))

        new_min = min(all_data_points, key=lambda t: t[1])[1]
        new_max = max(all_data_points, key=lambda t: t[1])[1]

        if new_min != self.min_y or new_max != self.max_y:
            magnitude = int(math.log10(new_max - new_min + 1))
            y_steps = range(new_min, new_max + 1, 10 ** magnitude)
            if len(y_steps) < 3 and magnitude > 0:
                y_steps = range(new_min, new_max + 1, 10 ** (magnitude - 1))
            self.y_steps = y_steps
