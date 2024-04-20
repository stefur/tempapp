import locale
from datetime import datetime, timedelta

import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
import polars as pl
import polars_xdt as xdt
import shinyswatch
import tempapp.utils as utils  # type: ignore[import-untyped]
from dateutil.relativedelta import relativedelta
from faicons import icon_svg as icon
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

# Set the locale
locale.setlocale(locale.LC_ALL, "sv_SE.utf-8")

app_ui = ui.page_navbar(
    shinyswatch.theme.simplex(),
    ui.nav_panel(
        "Dashboard",
        ui.page_fluid(
            ui.row(ui.h2(icon("clock", style="regular"), " Timme för timme")),
            ui.br(),
            ui.row(
                ui.h4(
                    ui.output_text("status_right_now"),
                ),
                ui.p(
                    ui.output_ui("temp_boxes", fillable=True),
                ),
            ),
            ui.row(ui.output_ui("time_slider")),
            ui.br(),
            ui.row(ui.h2(icon("calendar-day", style="solid"), " Senaste dygnet")),
            ui.br(),
            ui.row(
                ui.card(
                    output_widget("day_plt"),
                ),
            ),
            ui.br(),
            ui.row(ui.h2(icon("calendar-week", style="solid"), " Senaste 7 dygnen")),
            ui.br(),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.input_select(
                            "select_floor",
                            "Välj:",
                            {
                                "Huset": "Huset",
                                "Våning 1": "Våning 1",
                                "Våning 2": "Våning 2",
                                "Våning 3": "Våning 3",
                            },
                        ),
                        output_widget("seven_day_heatmap"),
                    ),
                ),
            ),
        ),
    ),
    ui.nav_panel(
        "Långtidsdata",
        ui.page_fluid(
            ui.row(ui.h2(icon("calendar-days", style="solid"), " Tidsserie")),
            ui.br(),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.input_date_range(
                            id="daterange",
                            label="Datum:",
                            language="sv",
                            weekstart=1,
                            separator=" till ",
                            start=utils.get_max_timestamp() - relativedelta(months=1),
                            end=utils.get_max_timestamp(),
                        ),
                        ui.input_action_button(
                            id="reset", label="Återställ", width="200px"
                        ),
                        output_widget("long_plt"),
                    ),
                )
            ),
        ),
    ),
    title="TempApp",
)


def server(input, output, session):
    @output
    @render.text
    def status_right_now():
        return f"""Kl {datetime.strftime(utils.fix_timezone(input.time()), "%H:%M (%-d/%-m)")}"""

    @output
    @render.ui
    def time_slider():
        return (
            ui.input_slider(
                id="time",
                label="",
                min=utils.get_max_timestamp() - timedelta(hours=24),
                max=utils.get_max_timestamp(),
                value=utils.get_max_timestamp(),
                time_format="%H:%M %-d/%-m",
                step=timedelta(hours=1),
                width="100%",
                ticks=True,
            ),
        )

    @reactive.effect
    @reactive.event(input.reset)
    def reset_date_filter():
        """Reset the date range upon a button click"""
        ui.update_date_range(
            id="daterange",
            start=utils.get_max_timestamp() - relativedelta(months=1),
            end=utils.get_max_timestamp(),
        )

    @reactive.Effect
    def _():
        """Make sure that the date filter in long term data is properly up to date"""
        ui.update_date_range(
            id="daterange",
            start=utils.get_max_timestamp() - relativedelta(months=1),
            end=utils.get_max_timestamp(),
        )

    @output
    @render.ui
    def temp_boxes():
        data = utils.query_db(
            f"SELECT floor, temp FROM temps WHERE time_trunc = '{utils.fix_timezone(input.time()).strftime("%Y-%m-%d %H:%M:%S")}'"
        )  # Fix the timezone in the query, and also format the input so that DuckDB correctly interprets the datetime

        # Split data for each floor
        floors = utils.split_floor_data(data)

        # Unpack the temps and round them
        floor_temps = {
            floor: df.with_columns(pl.col("temp").round(1).alias("temp"))
            .select("temp")
            .to_series()
            .to_list()[0]
            for floor, df in floors.items()
        }

        return ui.layout_column_wrap(
            *[
                # For each floor, return a value_box with the temp, colored based on
                # how high the temp is.
                ui.card(
                    floor,
                    ui.h2(utils.dot_to_comma(temp)),
                    # theme="yellow" if temp > 18 else "red" if temp > 25 else "blue",
                ).add_style(f"background-color:{utils.determine_bg_color(temp)};")
                for floor, temp in floor_temps.items()
            ],
            fixed_width=True,
        )

    @output
    @render_widget
    def seven_day_heatmap() -> go.FigureWidget:
        # Get the latest available from the last 7 days by truncating the timestamp
        # to make sure we get full days of data.

        floor_filter: str = (
            ""
            if input.select_floor() == "Huset"
            else f" AND floor = '{input.select_floor()}'"
        )

        data = utils.query_db(
            f"""SELECT day, hour, temp FROM temps
            WHERE time_trunc >= date_trunc('day', (SELECT MAX(time_trunc) FROM temps)) - INTERVAL '6' DAY
            AND time_trunc <= date_trunc('day', (SELECT MAX(time_trunc) FROM temps)) + INTERVAL '1' DAY{floor_filter}"""
        )

        avg_temp = (
            data.group_by("day", "hour")
            .agg(pl.col("temp").mean().round(1))
            .sort("day", "hour")
            .with_columns(
                locale_day=xdt.format_localized(pl.col("day"), "%-d %B", "sv_SE"),
                date_iso=pl.col("day").dt.strftime("%Y-%m-%d"),
            )
        )

        heatmap = go.FigureWidget()

        heatmap.add_trace(
            go.Heatmap(
                z=avg_temp["temp"],
                x=avg_temp["locale_day"],
                y=avg_temp["hour"],
                hoverinfo="text",
                hovertext=[
                    f"""Datum: {row["date_iso"]}<br>Tid: {row["hour"]}<br>Temp: {row["temp"]}°C"""
                    for row in avg_temp.rows(named=True)
                ],  # Manually create the text for hover labels to avoid showing labels for missing (e.g. future) timestamps
                colorscale="rdylbu_r",  # Set the color scale (in reverse)
                zmin=18
                if min(avg_temp["temp"]) > 18
                else min(avg_temp["temp"]),  # Set the minimum value for the color scale
                zmax=25
                if max(avg_temp["temp"]) < 25
                else max(avg_temp["temp"]),  # Set the maximum value for the color scale
            )
        )
        # Customize the layout
        heatmap.update_layout(
            template="plotly_white",
            title="Medeltemperatur timme för timme",
            yaxis=dict(
                categoryorder="category descending",
                fixedrange=True,
                dtick=2,
            ),  # Sort the hours correctly
            xaxis=dict(fixedrange=True),
        )

        result = utils.set_plotly_config(heatmap)

        return result

    @output
    @render_widget
    def day_plt() -> go.FigureWidget:
        # Get the latest available from 24 hours back.
        data = utils.query_db(
            """SELECT floor, temp, time_trunc, date_iso, hour FROM temps
            WHERE time_trunc >= (SELECT MAX(time_trunc) FROM temps)
            - INTERVAL '24' HOUR AND time_trunc <= (SELECT MAX(time_trunc) FROM temps)"""
        ).with_columns(
            locale_hour_day=pl.when(
                pl.col("hour") == pl.col("time_trunc").min().dt.strftime("%H:%M")
            )
            .then(pl.col("time_trunc").dt.strftime("%H:%M - %-d/%-m"))
            .otherwise(pl.col("hour"))
        )

        house_avg_hour = (
            data.select("locale_hour_day", "time_trunc", "temp")
            .group_by("locale_hour_day", "time_trunc")
            .agg(pl.col("temp").mean().round(1).alias("mean"))
            .sort("time_trunc", "locale_hour_day")
        )

        plt = go.FigureWidget()

        plt.add_trace(
            go.Scatter(
                x=house_avg_hour["locale_hour_day"],
                y=house_avg_hour["mean"],
                name="Husets medeltemperatur",
                mode="lines",
                fill="tozeroy",
                line=dict(color="rgba(211, 211, 211, 0.8)"),  # Light grey
                fillcolor="rgba(211, 211, 211, 0.4)",
                hoverinfo="none",  # Hide the hover label since it is mostly blocked any way
            )
        )
        plt.update_layout(
            template="plotly_white",
            legend=dict(
                orientation="h",
                y=-0.14,
                xanchor="center",
                x=0.5,
            ),
            # Don't allow zooming any axes
            xaxis=dict(fixedrange=True),
            yaxis=dict(
                fixedrange=True,
                range=[
                    18
                    if min(data["temp"]) > 18
                    else min(data["temp"]),  # Set the minimum value for the color scale
                    25 if max(data["temp"]) < 24 else max(data["temp"] + 1),
                ],  # Set the maximum value for the color scale, max(by_hour["temp"] + 1)],
            ),
        )

        # Preparing the dumbbell lines by calculating min
        # and max temps for each timestamp, concating them to a list
        # and pushing them to dicts
        connectors = (
            data.group_by("locale_hour_day", "time_trunc")
            .agg(
                pl.col("temp").max().alias("y_end"),
                pl.col("temp").min().alias("y_start"),
            )
            .select(
                pl.col("time_trunc"),
                pl.col("locale_hour_day"),
                pl.concat_list(pl.col("y_start"), pl.col("y_end")).alias("values"),
            )
            .drop("y_end", "y_start")
            .sort("time_trunc", "locale_hour_day")
            .unique()
            .to_dicts()
        )

        # For each connector (timestamp) we add the values
        # which is a list of length 2, e.g. y_start and y_end
        # We repeat the the x value twice too so plotly knows
        # where each point is supposed to go.
        for c in connectors:
            plt.add_trace(
                go.Scatter(
                    y=c["values"],
                    x=[c["locale_hour_day"], c["locale_hour_day"]],
                    showlegend=False,
                    mode="lines",
                    line=dict(color="darkgray", dash="dot"),
                    hoverinfo="none",  # Connectors should not any hover
                )
            )

        # Now split each floor
        floors = utils.split_floor_data(data)

        for floor, df in floors.items():
            # Get the color based on the key index
            color = px.colors.qualitative.Safe[list(floors.keys()).index(floor)]
            plt.add_trace(
                go.Scatter(
                    y=df["temp"],
                    x=df["locale_hour_day"],
                    mode="markers",
                    name=floor,
                    marker=dict(color=color, size=12),
                    hoverinfo="text",
                    hovertext=[
                        f"""Datum: {row["date_iso"]}<br>Tid: {row["hour"]}<br>Temp: {row["temp"]}°C"""
                        for row in df.rows(named=True)
                    ],
                )
            )

        # Disable all clicking on traces for this plot as it doesn't make much sense here
        plt.update_layout(legend_itemclick=False, legend_itemdoubleclick=False)

        result = utils.set_plotly_config(plt)

        return result

    @output
    @render_widget
    def long_plt() -> go.FigureWidget:
        # Query the db for data
        data = utils.query_db(
            f"SELECT * FROM temps WHERE time BETWEEN '{input.daterange()[0]}' AND '{input.daterange()[1]}'"
        )
        # Create a day variable and then group on it to get a mean temp per day
        per_day = (
            data.select("day", "temp", "floor")
            .group_by(["day", "floor"])
            .agg(
                pl.col("temp").mean().round(1).alias("mean"),
                pl.col("temp").std().alias("std"),
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

        # The names of each floor in a list
        floors = data.select(pl.col("floor")).unique().to_series().sort().to_list()

        # Produce 3 different dataframes, 1 for each floor, so we can plot it easily
        floors_avg = {
            floor: per_day.filter(pl.col("floor") == floor) for floor in floors
        }

        time_series = go.FigureWidget()

        # Add the line trace
        for floor, df in floors_avg.items():
            df_in_date = df.filter(
                (pl.col("day") >= input.daterange()[0])
                & (pl.col("day") <= input.daterange()[1])
            )

            # Illustrate variance of standard deviation with a gray surface
            # Must be applied first to allow hovering on the mean line
            time_series.add_trace(
                go.Scatter(
                    x=df_in_date["locale_day"].to_list()
                    + df_in_date["locale_day"].to_list()[::-1],
                    y=df_in_date["std_minus"].to_list()
                    + df_in_date["std_plus"].to_list()[::-1],
                    fill="toself",
                    fillcolor="rgba(136,139,141,0.2)",
                    line_color="rgba(255,255,255,0)",
                    showlegend=False,
                    legendgroup=floor,
                    name=floor,
                    hoverinfo="none",
                )
            )

            # Get the color based on the key index
            color = px.colors.qualitative.Safe[list(floors_avg.keys()).index(floor)]
            # Add the mean as a line
            time_series.add_trace(
                go.Scatter(
                    x=df_in_date["locale_day"],
                    y=df_in_date["mean"],
                    name=floor,
                    legendgroup=floor,
                    line=dict(color=color),
                    hovertemplate="%{x}<br>%{y}°C",
                )
            )

        # Title, template, legend etc.
        time_series.update_layout(
            template="plotly_white",
            title="Temperatur över tid",
            legend=dict(
                orientation="h",
                y=1.14,
                xanchor="center",
                x=0.5,
            ),
            # Don't allow zooming any axes
            xaxis=dict(fixedrange=True),
            yaxis=dict(fixedrange=True),
        )

        # Fix the axes
        time_series.update_yaxes(title_text="Temperatur °C")
        time_series.update_xaxes(nticks=10)

        result = utils.set_plotly_config(time_series)

        # Show the plot
        return result


app = App(app_ui, server)
