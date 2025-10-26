import pandas as pd
import matplotlib.pyplot as plt
import math
import calendar
from scipy.integrate import trapz
from collections import OrderedDict

class StackedLinePlot:
    def __init__(self, csv_path, date_column_name, q_column_name):
        self.csv_path = csv_path
        self._df = None
        self._pivot_table = None
        self._name_of_Q_column = q_column_name
        self._forced_x_positions = None
        self._forced_x_labels = None
        self._mean = None
        self._median = None
        self._st_dev = None
        self._lower_bound = None
        self._upper_bound = None
        self._lower_bound_percentile25 = None
        self._upper_bound_percentile75 = None
        self._colors = ['crimson', 'springgreen', 'dodgerblue', 'purple', 'green', 'deeppink', 'lawngreen', 'coral', 'lime', 'navy', 'goldenrod']

    @property
    def df(self):
        return self._df

    @df.setter
    def df(self, csv_path):
        try:
            self._df = pd.read_csv(csv_path)
            self._create_pivot_table()
        except Exception as e:
            print(e)

    def _create_pivot_table(self):
        if self._df is not None:
            self._pivot_table = self._df.pivot(index="month-day", columns='Year', values=self._name_of_Q_column)

    @property
    def mean_value(self):
        if self._mean is None:
            self.calculate_statistics()
        return self._mean

    @property
    def monthly_stats(self):
        monthly_stats = self._monthly_stats
        monthly_stats.index = monthly_stats.index.map(lambda x: calendar.month_name[x])
        monthly_stats = monthly_stats.round(1)
        return monthly_stats

    @property
    def stats(self):
        return self._df.describe().round(2)

    def calculate_statistics(self):
        self._stats = self._df.groupby("month-day")[self._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
        self._monthly_stats = self._df.groupby("month")[self._name_of_Q_column].agg(['mean', 'median', 'std', ("q25", lambda x: x.quantile(0.25)), ("q75", lambda y: y.quantile(0.75))])
        self._mean = self._stats.iloc[:, 0]
        self._median = self._stats.iloc[:, 1]
        self._st_dev = self._stats.iloc[:, 2]
        self._percentile25 = self._stats.iloc[:, 3]
        self._percentile75 = self._stats.iloc[:, 4]
        self._lower_bound = self._mean - self._st_dev
        self._upper_bound = self._mean + self._st_dev
        self._lower_bound_percentile25 = self._mean - self._percentile25
        self._upper_bound_percentile75 = self._mean + self._percentile75
   

    def calculate_yearly_volumes(self):
        years = []
        area = []
        for year in self._pivot_table.columns:
            dates = (list(range(0,len(self._pivot_table[year].dropna()))))
            area.append(trapz(self._pivot_table[year].dropna(), dates))
            years.append(year)
 
        Area_dict = OrderedDict()
        for key, value in zip(years, area):
            Area_dict[key] = value

 

#        Area_df = pd.DataFrame(dict(zip(years,area)))
#       
#        Area_df = pd.DataFrame(Area_dict)
#        area = {str(year): trapz(self._pivot_table[year].dropna(), list(range(0,len(self._pivot_table[year].dropna())))) for year in self._pivot_table.columns}
#        self._area_df = pd.DataFrame(area)
        return Area_dict

     

    def plot_stacked_line_plot(
        self,
        forced_x_positions=[1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 336],
        forced_x_labels=['01-01', '02-01', '03-01', '04-01', '05-01', '06-01', '07-01', '08-01', '09-01', '10-01', '11-01', '12-01'],
        title=None,
        highlight_years=[2001, 2015, 2023],
        plot_central_tendency_stats=True,
        quartile_shading=True,
        quartile_shading_alpha=0.4,
        quartile_shading_zorder=1,
        series_labels=True,
        series_alpha=1,
        group_by_decade=False,
        decade_stats_to_plot="All",
        y_lower_lim=0,
        y_upper_lim="Auto",
        legend='upper right',
        legend_ncol=1,
        input_start_year=2010,
        input_end_year=2020
    ):

        # if y_upper_lim == "Auto":
        #     y_upper_lim = self._ylim_max

        self._filter_dataframe(input_start_year, input_end_year)

        fig, ax = plt.subplots(figsize=(9, 7))

        if plot_central_tendency_stats:
            self._plot_central_tendency_stats(ax)

        if highlight_years:
            self._plot_highlight_years(ax, highlight_years)

        if quartile_shading:
            self._plot_quartile_shading(ax, quartile_shading_alpha, quartile_shading_zorder)

        if group_by_decade:
            self._plot_group_by_decade(ax, decade_stats_to_plot)
        else:
            self._plot_individual_series(ax, series_labels, series_alpha)

        self._set_plot_properties(ax, title, legend, legend_ncol, y_lower_lim, y_upper_lim)
        plt.show()

    def _filter_dataframe(self, start_year, end_year):
        self._df = self._df[(self._df['Year'] >= start_year) & (self._df['Year'] <= end_year)]
        self._unique_years = list(self._df['Year'].unique())
        self._start_year, self._end_year = self._unique_years[0], self._unique_years[-1]

    def _plot_central_tendency_stats(self, ax):
        self._mean.plot(ax=ax, label="Mean", linestyle=':', color='black', linewidth=1.5, zorder=3)
        self._median.plot(ax=ax, label="Median", linestyle=':', color='red', linewidth=1.5, zorder=3)

    def _plot_highlight_years(self, ax, highlight_years):
        for i, year in enumerate(highlight_years):
            self._pivot_table.loc[:, year].plot(ax=ax, linewidth=1.6, zorder=3, color=self._colors[i])

    def _plot_quartile_shading(self, ax, quartile_shading_alpha, quartile_shading_zorder):
        ax.fill_between(
            list(range(0, len(pd.DataFrame(self._mean).iloc[:, 0]))),
            pd.DataFrame(self._mean).iloc[:, 0].astype(float),
            pd.DataFrame(self._lower_bound_percentile25).iloc[:, 0].astype(float),
            where=(pd.DataFrame(self._mean).iloc[:, 0].astype(float) > pd.DataFrame(self._lower_bound_percentile25).iloc[:, 0].astype(float)),
            interpolate=True, color='yellow', alpha=quartile_shading_alpha, zorder=quartile_shading_zorder, label="q25-q75")

        ax.fill_between(
            list(range(0, len(pd.DataFrame(self._mean).iloc[:, 0]))),
            pd.DataFrame(self._mean).iloc[:, 0].astype(float),
            pd.DataFrame(self._upper_bound_percentile75).iloc[:, 0].astype(float),
            where=(pd.DataFrame(self._mean).iloc[:, 0].astype(float) < pd.DataFrame(self._upper_bound_percentile75).iloc[:, 0].astype(float)),
            interpolate=True, color='yellow', alpha=quartile_shading_alpha, zorder=1)

    def _plot_group_by_decade(self, ax, decade_stats_to_plot):
        colors = ['blue', 'orange', 'purple', 'red']
        decade_groups = [list(range(i, i + 10)) for i in self._unique_decades]

        for i, decade in enumerate(decade_groups):
            means = self._pivot_table.loc[:, decade].mean(axis=1)
            medians = self._pivot_table.loc[:, decade].median(axis=1)
            self._plot_decade_stats_line(ax, means, medians, decade, i, colors, decade_stats_to_plot)

    def _plot_individual_series(self, ax, series_labels, series_alpha):
        filtered_pivot_table = self._get_filtered_pivot_table()
        if series_labels is False:
            for i in filtered_pivot_table.columns:
                filtered_pivot_table[i].plot(ax=ax, alpha=series_alpha, zorder=2, linewidth=1.0, label='')
        else:
            filtered_pivot_table.plot(ax=ax, alpha=series_alpha, zorder=2, linewidth=1.0, label='')

    def _plot_decade_stats_line(self, ax, means, medians, decade, index, colors, decade_stats_to_plot):
        if decade_stats_to_plot == 'mean':
            means.plot(ax=ax, linestyle="--", label=f"mean {decade[0]} - {decade[-1]}", linewidth=1, color=colors[index])
        elif decade_stats_to_plot == 'median':
            medians.plot(ax=ax, linestyle="-.", label=f"median {decade[0]} - {decade[-1]}", linewidth=1, color=colors[index])
        else:
            means.plot(ax=ax, linestyle="--", label=f"mean {decade[0]} - {decade[-1]}", linewidth=1, color=colors[index])
            medians.plot(ax=ax, linestyle="-.", label=f"median {decade[0]} - {decade[-1]}", linewidth=1, color=colors[index])

    def _set_plot_properties(self, ax, title, legend, legend_ncol, y_lower_lim, y_upper_lim):
        if self._forced_x_positions is not None and self._forced_x_labels is not None:
            ax.set_xticks(self._forced_x_positions)
            xlim_min, xlim_max = self._forced_x_positions[0], self._forced_x_positions[-1]
            ax.set_xticklabels(self._forced_x_labels, rotation=45)
            ax.set_xlim([xlim_min, xlim_max])
            ax.set_ylim([y_lower_lim, y_upper_lim])

        plt.grid(color='green', linestyle=":", linewidth=0.5)
        plt.xlabel('Month-Day')
        plt.ylabel('Lake Elevation (ft)')
        plt.legend(loc=legend, ncol=legend_ncol)
 
    
 

 

if __name__ == "__main__":

#    parser = argparse.ArgumentParser(description="Plot stacked line plots for any csv file with a date column and data column")

#    parser.add_argument('csv_file', type=str, help='Path to csv file')

#    parser.add_argument('Name of date column in csv', type=str, help='Name of date column in csv')

#    parser.add_argument('Name of the Q column in csv', type=str)

#    parser.add_argument('--run)

   

    

    

#    print(os.getcwd())

#    BUDW1 = StackedLinePlot("BUDW1_daily_USBR_inflow_data_new.csv", 'DATE', "QU")

#    print("-------")   

#    print(BUDW1._df)

#    print("-------")

#    print(BUDW1._pivot_table)

#   

##    print(BUDW1._df_stat_summary)

##    print(pd.DataFrame(BUDW1._pivot_table_monthly_stats))

##    print(BUDW1._pivot_table)

##    priestLake.plot_entireTS(title="Priest River Near Priest River, ID - USGS 12395000")

#    BUDW1.plotStackedLinePlot(title="BUDW1_daily_USBR_inflow",

#                                  forced_x_positions=None,

#                                  forced_x_labels=None,

#                                  quartile_shading=True,

#                                  group_by_decade=True,

#                                  decade_stats_to_plot="All",

#                                  y_upper_lim=3500,

##                                  legend="partial",

#                                  input_start_year=1980,

#                                  input_end_year=2023

#                                  )

    print("-------This module creates customized StackedLinePlots.")

#    print(BUDW1._monthly_stats)