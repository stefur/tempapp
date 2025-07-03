import logging
from datetime import date, datetime, timedelta
from typing import Any

import polars as pl
import polars_xdt as xdt
from dateutil.relativedelta import relativedelta
from faicons import icon_svg as icon
from pyecharts import options as opts
from pyecharts.charts import HeatMap, Line
from shiny import App, reactive, render, ui

from . import utils

# Tap into the uvicorn logging
logger = logging.getLogger("uvicorn.error")

# Busy indicators
busy_indicators = (
    ui.busy_indicators.use(spinners=True, pulse=False, fade=True),
    ui.busy_indicators.options(spinner_type="bars3", spinner_delay="0s"),
)

# Load theme attributes from brand.yml, but skip type checking because I'm lazy
theme: Any = ui.Theme.from_brand(__file__)

app_ui = ui.page_navbar(
    ui.nav_panel(
        "Dashboard",
        ui.page_fluid(
            ui.HTML(
                '<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.js"></script>'
            ),
            ui.row(ui.h3(icon("clock", style="regular"), " Just nu")),
            ui.br(),
            ui.row(
                ui.h4(
                    ui.output_text("status_right_now"),
                ),
                ui.p(
                    ui.output_ui("temp_boxes", fillable=True),
                ),
            ),
            ui.tags.style(
                # Target the title in the navbar and the link items
                """
                .navbar-brand {
                    font-size: 1.5rem;
                    font-weight: 600;
                }
                .shiny-tab-input .nav-link {
                    font-size: 1.1rem !important;
                    font-weight: 600 !important;
                }
                """
            ),
            ui.br(),
            ui.row(ui.h3(icon("calendar-day", style="solid"), " Senaste dygnet")),
            ui.br(),
            ui.row(
                ui.card(
                    ui.output_ui("line_plot"),
                    style="background-color: #FFFFFF;",
                ),
            ),
            ui.br(),
            ui.row(ui.h3(icon("calendar-week", style="solid"), " Senaste 7 dygnen")),
            ui.br(),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.p("Medeltemperaturer timme för timme."),
                        ui.input_select(
                            "select_floor",
                            "Filtrera:",
                            {
                                "Huset": "Huset",
                                "Våning 1": "Våning 1",
                                "Våning 2": "Våning 2",
                                "Våning 3": "Våning 3",
                            },
                        ),
                        ui.output_ui("heatmap"),
                        style="background-color: #FFFFFF;",
                    ),
                ),
            ),
        ),
        busy_indicators,
    ),
    ui.nav_panel(
        "Långtidsdata",
        ui.page_fluid(
            ui.row(ui.h3(icon("calendar-days", style="solid"), " Långtidsdata")),
            ui.br(),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.p("Temperaturer över tid."),
                        ui.input_date_range(
                            id="daterange",
                            label="Datum:",
                            language="sv",
                            weekstart=1,
                            separator=" till ",
                        ),
                        ui.input_action_button(
                            id="reset", label="Återställ", width="200px"
                        ),
                        ui.output_ui("long_line_plot"),
                        style="background-color: #FFFFFF;",
                    ),
                )
            ),
        ),
        busy_indicators,
    ),
    id="main",
    title="TempApp",
    theme=theme,
    navbar_options=ui.navbar_options(
        bg=theme.brand.color.primary,
        theme="dark",
    ),
)


def server(input, output, session):
    logger.info("New session began at: " + datetime.now().strftime("%H:%M:%S"))
    logger.info("Loading data.")

    base = utils.load_data()

    max_timestamp: datetime = base.select("time_trunc").max().item()
    max_day: date = base.select("day").max().item().date()

    @session.on_ended
    def end():
        logger.info("Session ended at: " + datetime.now().strftime("%H:%M:%S"))

    @output
    @render.text
    def status_right_now():
        return f"""Kl {datetime.strftime(max_timestamp, "%H:%M (%-d/%-m)")}"""

    @reactive.effect
    @reactive.event(input.reset)
    def reset_date_filter():
        """Reset the date range upon a button click and ensure the filter is up to date"""
        ui.update_date_range(
            id="daterange",
            start=max_timestamp - relativedelta(months=1),
            end=max_timestamp,
        )

    @reactive.effect
    def _():
        """Make sure that the date filter in long term data is properly up to date"""
        ui.update_date_range(
            id="daterange",
            start=max_timestamp - relativedelta(months=1),
            end=max_timestamp,
        )

    @output
    @render.ui
    def temp_boxes():
        data = base.filter(pl.col("time_trunc") == max_timestamp).select(
            "floor", "temp"
        )

        # Split data for each floor
        floors = utils.split_floor_data(data)

        # Unpack the temps and round them
        floor_temps = {
            floor: df.with_columns(pl.col("temp").round(1).alias("temp"))
            .select("temp")
            .item()
            for floor, df in floors.items()
        }

        return ui.layout_column_wrap(
            *[
                # For each floor, return a value_box with the temp, colored based on
                # how high the temp is.
                ui.card(
                    floor,
                    ui.h3(utils.dot_to_comma(temp)).add_style(f"color:{fg_color};"),
                ).add_style(f"background-color:{bg_color};color:{fg_color};")
                for floor, temp in floor_temps.items()
                if (colors := utils.determine_colors(temp))
                and (bg_color := colors[0])
                and (fg_color := colors[1])
            ],
            fixed_width=True,
        )

    @render.ui
    def line_plot() -> ui.HTML:
        data = (
            base.filter(
                (pl.col("time_trunc") >= (max_timestamp - timedelta(hours=24)))
                & (pl.col("time_trunc") <= max_timestamp)
            )
            .select("floor", "temp", "time_trunc", "date_iso", "hour")
            .with_columns(
                locale_hour_day=pl.when(
                    pl.col("hour") == pl.col("time_trunc").min().dt.strftime("%H:%M")
                )
                .then(pl.col("time_trunc").dt.strftime("%H:%M - %-d/%-m"))
                .otherwise(pl.col("hour"))
            )
        )

        house_avg_hour = (
            data.select("locale_hour_day", "time_trunc", "temp")
            .group_by("locale_hour_day", "time_trunc")
            .agg(pl.col("temp").mean().round(1).alias("mean"))
            .sort("time_trunc", "locale_hour_day")
        )

        chart = (
            Line(init_opts=opts.InitOpts(width="100%", renderer="svg"))
            .add_xaxis(house_avg_hour["locale_hour_day"].to_list())
            .add_yaxis(
                "Husets medeltemperatur",
                house_avg_hour["mean"].to_list(),
                areastyle_opts=opts.AreaStyleOpts(color="lightgray", opacity=0.5),
                linestyle_opts=opts.LineStyleOpts(color="lightgray", width=2),
                symbol="none",
                label_opts=opts.LabelOpts(is_show=False),
                itemstyle_opts=opts.ItemStyleOpts(color="lightgray"),
            )
            .add_yaxis(
                "Våning 1",
                data.filter(pl.col("floor") == "Våning 1")["temp"].to_list(),
                symbol_size=12,
                symbol="circle",
                linestyle_opts=opts.LineStyleOpts(width=2),
            )
            .add_yaxis(
                "Våning 2",
                data.filter(pl.col("floor") == "Våning 2")["temp"].to_list(),
                symbol_size=12,
                symbol="circle",
                linestyle_opts=opts.LineStyleOpts(width=2),
            )
            .add_yaxis(
                "Våning 3",
                data.filter(pl.col("floor") == "Våning 3")["temp"].to_list(),
                symbol_size=12,
                symbol="circle",
                linestyle_opts=opts.LineStyleOpts(width=2),
            )
            .set_series_opts(
                label_opts=opts.LabelOpts(is_show=False),
                markline_opts=opts.MarkLineOpts(
                    data=[
                        {"yAxis": 21, "lineStyle": {"color": "#0000FF"}},
                        {"yAxis": 24, "lineStyle": {"color": "#FF0000"}},
                    ],
                    label_opts=opts.LabelOpts(is_show=False),
                ),
            )
            .set_global_opts(
                tooltip_opts=opts.TooltipOpts(
                    is_show=True,
                    trigger="axis",
                    axis_pointer_type="shadow",
                ),
                legend_opts=opts.LegendOpts(
                    orient="horizontal",
                    pos_bottom="0",
                    textstyle_opts=opts.TextStyleOpts(
                        font_size=14,
                        color="#313131",
                        font_family="Arial",
                    ),
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(
                        font_size=14,
                        font_family="Arial",
                        color="#313131",
                    )
                ),
                yaxis_opts=opts.AxisOpts(
                    min_=18 if min(data["temp"]) > 18 else min(data["temp"]),
                    max_=25 if max(data["temp"]) < 24 else max(data["temp"] + 1),
                    axislabel_opts=opts.LabelOpts(
                        formatter="{value} °C",
                        font_size=14,
                        font_family="Arial",
                        color="#313131",
                    ),
                    axisline_opts=opts.AxisLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(
                            color="#313131",
                        ),
                    ),
                ),
            )
        )
        return ui.HTML(chart.render_embed())

    @render.ui
    def heatmap() -> ui.HTML:
        data = base.filter(
            (pl.col("day") >= max_day - timedelta(days=6))
            & (pl.col("day") <= max_day + timedelta(days=1))
        ).select("day", "hour", "temp", "floor")

        if (selection := input.select_floor()) != "Huset":
            data = data.filter(pl.col("floor") == selection)

        avg_temp = (
            data.group_by("day", "hour")
            .agg(pl.col("temp").mean().round(1))
            .sort("day", "hour")
            .with_columns(
                locale_day=xdt.format_localized(pl.col("day"), "%-d %B", "sv_SE"),
                date_iso=pl.col("day").dt.strftime("%Y-%m-%d"),
            )
        )

        x_labels = (
            avg_temp.select("locale_day", "date_iso")
            .unique()
            .sort(by="date_iso")
            .select("locale_day")
            .to_series()
            .to_list()
        )
        y_labels = avg_temp["hour"].unique().sort(descending=True).to_list()

        full_grid = pl.DataFrame(
            {
                "locale_day": [x for x in x_labels for y in y_labels],
                "hour": [y for x in x_labels for y in y_labels],
            }
        )

        merged = full_grid.join(
            avg_temp.select(["locale_day", "hour", "temp"]),
            on=["locale_day", "hour"],
            how="left",
        )

        x_idx = {label: idx for idx, label in enumerate(x_labels)}
        y_idx = {label: idx for idx, label in enumerate(y_labels)}

        value = [
            [x_idx[row[0]], y_idx[row[1]], row[2]]
            for row in merged.iter_rows(named=False)
        ]

        chart = (
            HeatMap(init_opts=opts.InitOpts(width="100%", renderer="svg"))
            .add_xaxis(x_labels)
            .add_yaxis(
                "Temperatur",
                y_labels,
                value,
                label_opts=opts.LabelOpts(is_show=False),
            )
            .set_global_opts(
                tooltip_opts=opts.TooltipOpts(
                    is_show=True,
                    trigger="item",
                    axis_pointer_type="cross",
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(
                        font_size=14,
                        font_family="Arial",
                        color="#313131",
                    )
                ),
                yaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(
                        font_size=14,
                        font_family="Arial",
                        color="#313131",
                    ),
                    axisline_opts=opts.AxisLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(
                            color="#313131",
                        ),
                    ),
                ),
                legend_opts=opts.LegendOpts(is_show=False),
                visualmap_opts=opts.VisualMapOpts(
                    min_=18
                    if min(avg_temp["temp"]) > 18
                    else min(
                        avg_temp["temp"]
                    ),  # Set the minimum value for the color scale
                    max_=25
                    if max(avg_temp["temp"]) < 25
                    else max(
                        avg_temp["temp"]
                    ),  # Set the maximum value for the color scale
                    # ... other options
                    range_color=utils.palette,
                    is_show=False,
                ),
            )
        )
        return ui.HTML(chart.render_embed())

    @render.ui
    def long_line_plot() -> ui.HTML:
        if not input.daterange() or len(input.daterange()) < 2:
            raise ValueError("Invalid date range")

        data = base.filter(
            pl.col("time_trunc")
            .dt.date()
            .is_between(
                (input.daterange()[0]),
                input.daterange()[1] + timedelta(days=1),
            )
        ).select("day", "temp", "floor")

        data_grouped = (
            data.group_by(["day", "floor"])
            .agg(
                pl.col("temp").mean().round(1).alias("mean"),
                pl.col("temp").std().fill_null(0).alias("std"),
            )
            .vstack(
                data.group_by("day")
                .agg(
                    pl.col("temp").mean().round(1).alias("mean"),
                    pl.col("temp").std().fill_null(0).alias("std"),
                )
                .with_columns(floor=pl.lit("Huset"))
                .select("day", "floor", "mean", "std")
            )
            .with_columns(
                (pl.col("mean") + pl.col("std")).round(1).alias("std_plus"),
                (pl.col("mean") - pl.col("std")).round(1).alias("std_minus"),
            )
            .sort(["day", "floor"])
            .with_columns(
                locale_day=xdt.format_localized(pl.col("day"), "%-d %B %Y", "sv_SE")
            )
        )

        chart = (
            Line(init_opts=opts.InitOpts(width="100%", renderer="svg"))
            .add_xaxis(
                data_grouped.select("day", "locale_day")
                .unique()
                .sort("day")
                .select("locale_day")
                .to_series()
                .to_list()
            )
            .add_yaxis(
                "Husets medeltemperatur",
                data_grouped.filter(pl.col("floor") == "Huset")["mean"].to_list(),
                areastyle_opts=opts.AreaStyleOpts(color="lightgray", opacity=0.5),
                linestyle_opts=opts.LineStyleOpts(color="lightgray", width=2),
                symbol="none",
                label_opts=opts.LabelOpts(is_show=False),
                itemstyle_opts=opts.ItemStyleOpts(color="lightgray"),
            )
            .add_yaxis(
                "Våning 1",
                data_grouped.filter(pl.col("floor") == "Våning 1")["mean"].to_list(),
                symbol_size=12,
                symbol="circle",
                linestyle_opts=opts.LineStyleOpts(width=2),
            )
            .add_yaxis(
                "Våning 2",
                data_grouped.filter(pl.col("floor") == "Våning 2")["mean"].to_list(),
                symbol_size=12,
                symbol="circle",
                linestyle_opts=opts.LineStyleOpts(width=2),
            )
            .add_yaxis(
                "Våning 3",
                data_grouped.filter(pl.col("floor") == "Våning 3")["mean"].to_list(),
                symbol_size=12,
                symbol="circle",
                linestyle_opts=opts.LineStyleOpts(width=2),
            )
            .set_series_opts(
                label_opts=opts.LabelOpts(is_show=False),
                markline_opts=opts.MarkLineOpts(
                    data=[
                        {"yAxis": 21, "lineStyle": {"color": "#0000FF"}},
                        {"yAxis": 24, "lineStyle": {"color": "#FF0000"}},
                    ],
                    label_opts=opts.LabelOpts(is_show=False),
                ),
            )
            .set_global_opts(
                tooltip_opts=opts.TooltipOpts(
                    is_show=True,
                    trigger="axis",
                    axis_pointer_type="shadow",
                ),
                legend_opts=opts.LegendOpts(
                    orient="horizontal",
                    pos_bottom="0",
                    textstyle_opts=opts.TextStyleOpts(
                        font_size=14,
                        color="#313131",
                        font_family="Arial",
                    ),
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(
                        font_size=14,
                        font_family="Arial",
                        color="#313131",
                    )
                ),
                yaxis_opts=opts.AxisOpts(
                    min_=18
                    if min(data_grouped["mean"]) > 18
                    else min(data_grouped["mean"]),
                    max_=25
                    if max(data_grouped["mean"]) < 24
                    else max(data_grouped["mean"] + 1),
                    axislabel_opts=opts.LabelOpts(
                        formatter="{value} °C",
                        font_size=14,
                        font_family="Arial",
                        color="#313131",
                    ),
                    axisline_opts=opts.AxisLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(
                            color="#313131",
                        ),
                    ),
                ),
            )
        )
        return ui.HTML(chart.render_embed())


app = App(app_ui, server)
