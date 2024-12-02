import configparser
import io
import logging

import click
import requests
import yfinance as yf
from jinja2 import Environment, PackageLoader
from matplotlib import pyplot as plt


def distance(row, base, value):
    return (row[base] - row[value]) / row[base]


class Notifyer:
    def __init__(self, config_file, verbose: bool, dry_run: bool):
        self.dry_run = dry_run
        self.stoke_data = list()

        self.__setup_logging(verbose)
        self.__load_config(config_file)
        self.__setup_template_engine()
        self.__set_main_symbol()
        self.__set_aux_symbols()

    def __setup_logging(self, verbose: bool=False):
        self.logger = logging.getLogger(__name__)

        if verbose:
            logging.basicConfig(level=logging.INFO)
            self.logger.info("Verbose mode enabled")

    def __load_config(self, config_file):
        self.config = configparser.ConfigParser()
        logging.info(f'Loading config from {config_file.name}')
        self.config.read_file(config_file)

    def __set_main_symbol(self):
        symbol = dict(
            name = self.config.get("main_symbol", "name"),
            symbol = self.config.get("main_symbol", "symbol"),
        )
        self.logger.debug(f"Add {symbol['name']} ({symbol['symbol']}) as main symbol")
        self.stoke_data.append(symbol)

    def __set_aux_symbols(self):
        for section in filter(lambda section: section.startswith("aux_symbol:"), self.config.sections()):
            symbol = dict(
                name = self.config.get(section, "name"),
                symbol = self.config.get(section, "symbol"),
            )
            self.logger.info(f"Add {symbol['name']} ({symbol['symbol']}) as aux symbol")
            self.stoke_data.append(symbol)

    def __get_sma_windows(self):
        windows_string = self.config.get("reporting", "sma_windows")
        windows_raw_list = windows_string.split(',')
        windows = list(map(lambda window: int(window.strip()), windows_raw_list))
        windows.sort(reverse=True)
        return windows

    def __setup_template_engine(self):
        self.jinja_env = Environment(
            loader=PackageLoader("sp500notifyer", "templates"),
            trim_blocks=True,
        )

    def load_historical_stock_data(self):
        for symbol in self.stoke_data:
            self.logger.info(f"Loading historical data for {symbol['name']} ({symbol['symbol']})")
            ticker = yf.Ticker(symbol['symbol'])
            symbol['data'] = ticker.history(period=self.config.get("reporting", "history_period"))

    def calculate_sma_values(self):
        for window in self.__get_sma_windows():
            window = int(window)
            for symbol in self.stoke_data:
                self.logger.info(f"Calculating SMA{window} and Distance for {symbol['name']} ({symbol['symbol']})")
                symbol['data'][f"SMA{window}"] = symbol['data']["Close"].rolling(window=window).mean()
                symbol['data'][f"Distance SMA{window}"] = symbol['data'].apply(distance, axis=1, args=("Close", f"SMA{window}"))

    def generate_graph_for_main_symbol(self):
        datapoints_for_graph = self.config.getint("reporting", "datapoints_for_graph")
        main_symbol_dataframe = self.stoke_data[0]['data'].tail(datapoints_for_graph)
        dataframe_parts_for_graph = ["Close"] + [f"SMA{window}" for window in self.__get_sma_windows()]
        main_symbol_dataframe[dataframe_parts_for_graph].plot()

        plt.title(self.stoke_data[0]['name'])
        # remove borders
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)
        plt.gca().spines['left'].set_visible(False)

        plt.grid()

        graph_file = io.BytesIO()
        plt.savefig(graph_file, format="png")
        graph_file.seek(0)

        return graph_file

    def send_report(self):

        message_body = self.jinja_env.get_template("message_body.j2").render(
            symbols=self.stoke_data,
            sma_windows=self.__get_sma_windows(),
        )

        data = {
            "user": self.config.get("pushover", "user"),
            "token": self.config.get("pushover", "token"),
            "html": 1,
            "message": message_body,
            "attachment_type": " attachment",
        }

        files = {'attachment': self.generate_graph_for_main_symbol()}

        if self.dry_run:
            self.logger.warning("Dry run enabled. Skipping message sending")
        else:
            response = requests.post("https://api.pushover.net:443/1/messages.json", data=data, files=files)
            response.raise_for_status()

    def debug_show_graph(self):
        plt.show()

    def debug_show_dataframes(self):
        for symbol in self.stoke_data:
            click.secho(f"Data for {symbol['name']} ({symbol['symbol']})", bold=True, bg='yellow')
            click.echo(symbol['data'])
            click.echo()

    def run(self):
        self.load_historical_stock_data()
        self.calculate_sma_values()
        self.send_report()
