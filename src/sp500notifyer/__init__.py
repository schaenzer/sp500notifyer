import argparse
import configparser
import datetime
import tempfile

import requests
import yfinance as yf
from matplotlib import pyplot as plt
import logging
import pathlib


TODAY = datetime.date.today()
LASTYEAR = datetime.date.today() - datetime.timedelta(days=900)

def map_value_to_emoji(value):
    if value > 0.025:
        return "🟩"
    elif value > 0:
        return "🟨"
    else:
        return "🟥"

def map_value_to_color(value):
    if value > 0.025:
        return "#4CAE2F"
    elif value > 0:
        return "#FFCC00"
    else:
        return "#FF0000"

def map_value_to_action(value):
    if value > 0:
        return "Buy"
    else:
        return "Sell"


def distance(row, base, value):
    return (row[base] - row[value]) / row[base]

def get_dataframe_for_symbol(symbol: str):
    ticker = yf.Ticker(symbol)
    stock_data = ticker.history(start=LASTYEAR, end=TODAY)

    stock_data["SMA200"] = stock_data["Close"].rolling(window=200).mean()
    stock_data["SMA100"] = stock_data["Close"].rolling(window=100).mean()
    stock_data["Distance SMA200"] = stock_data.apply(distance, axis=1, args=("Close", "SMA200"))
    stock_data["Distance SMA100"] = stock_data.apply(distance, axis=1, args=("Close", "SMA100"))
    stock_data["Distance SMA200 Status"] = stock_data["Distance SMA200"].apply(map_value_to_emoji)
    stock_data["Distance SMA100 Status"] = stock_data["Distance SMA100"].apply(map_value_to_emoji)

    return stock_data

def generate_message(last_gspc, last_ndx, last_gdaxi):
    message = f""" <b>{map_value_to_emoji(last_gspc["Distance SMA200"])} <font color="{map_value_to_color(last_gspc["Distance SMA200"])}">{map_value_to_action(last_gspc["Distance SMA200"])}</font></b>

        <b>S&P 500</b>
        Close: {last_gspc["Close"]:9.2f}
        SMA200: {last_gspc["SMA200"]:8.2f} <b><font color="{map_value_to_color(last_gspc["Distance SMA200"])}">{last_gspc["Distance SMA200"]:.2%}</font></b>
        SMA100: {last_gspc["SMA100"]:8.2f} <b><font color="{map_value_to_color(last_gspc["Distance SMA100"])}">{last_gspc["Distance SMA100"]:.2%}</font></b>

        <b>Nasdaq 100</b>
        Close: {last_ndx["Close"]:9.2f}
        SMA200: {last_ndx["SMA200"]:8.2f} <b><font color="{map_value_to_color(last_ndx["Distance SMA200"])}">{last_ndx["Distance SMA200"]:.2%}</font></b>
        SMA100: {last_ndx["SMA100"]:8.2f} <b><font color="{map_value_to_color(last_ndx["Distance SMA100"])}">{last_ndx["Distance SMA100"]:.2%}</font></b>

        <b>DAX</b>
        Close: {last_gdaxi["Close"]:9.2f}
        SMA200: {last_gdaxi["SMA200"]:8.2f} <b><font color="{map_value_to_color(last_gdaxi["Distance SMA200"])}">{last_gdaxi["Distance SMA200"]:.2%}</font></b>
        SMA100: {last_gdaxi["SMA100"]:8.2f} <b><font color="{map_value_to_color(last_gdaxi["Distance SMA100"])}">{last_gdaxi["Distance SMA100"]:.2%}</font></b>
    """

    # stripe whitespace in every line
    message = "\n".join(map(str.strip, message.split("\n")))

    return message

def send_message(message, temp_image_file, pushover_user, pushover_token):
    data = {
        "user": pushover_user,
        "token": pushover_token,
        "html": 1,
        "message": message,
        "attachment_type": " attachment",
    }
    print(data)

    files = {'attachment': temp_image_file}

    response = requests.post("https://api.pushover.net:443/1/messages.json", data=data, files=files)
    response.raise_for_status()

def generate_image(dataframe, temp_image_file):

    dataframe[["Close", "SMA200", "SMA100"]].plot()

    plt.title("S&P 500")
    # remove borders
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    plt.gca().spines['left'].set_visible(False)
    plt.grid()
    plt.savefig(temp_image_file, format="png")
    temp_image_file.seek(0)


def main():
    args = _parse_args()
    config = _load_config(args.config.resolve())

    gspc = get_dataframe_for_symbol("^GSPC")
    ndx = get_dataframe_for_symbol("^NDX")
    gdaxi = get_dataframe_for_symbol("^GDAXI")

    with tempfile.TemporaryFile() as temp_image_file:

        generate_image(gspc.tail(65), temp_image_file)

        last_gspc = gspc.iloc[-1]
        last_ndx = ndx.iloc[-1]
        last_gdaxi = gdaxi.iloc[-1]

        message = generate_message(last_gspc=last_gspc, last_ndx=last_ndx, last_gdaxi=last_gdaxi)

        send_message(
            message,
            temp_image_file,
            pushover_user=config.get("pushover", "user"),
            pushover_token=config.get("pushover", "token")
        )


def _parse_args():
    parser = argparse.ArgumentParser(description='Send stock market analysis to pushover')
    parser.add_argument('-c', '--config', type=pathlib.Path, default='config.ini', help='path to config file')
    return parser.parse_args()

def _load_config(config_file):
    config = configparser.ConfigParser()
    if not config_file.is_file():
        logging.error(f'Config file {config_file} not found')
        raise SystemExit(f'Config file {config_file} not found')

    logging.info(f'Loading config from {config_file}')
    config.read(config_file)
    return config


if __name__ == "__main__":
    main()
