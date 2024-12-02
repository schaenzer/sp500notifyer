import click

from .main import Notifyer


@click.command()
@click.option('-c', '--config', type=click.File('r'), default='config.ini', help='path to config file')
@click.option('--verbose', is_flag=True, help='enable verbose mode')
@click.option('--dry-run', is_flag=True, help='do not send message')
@click.option('--show-graph', is_flag=True, help='show graph')
@click.option('--show-data', is_flag=True, help='show dataframes')
def cli(config, verbose: bool, dry_run: bool, show_graph: bool, show_data: bool):
    """S&P 500 Notifyer: Send stock market analysis to pushover"""
    notifyer = Notifyer(config_file=config, verbose=verbose, dry_run=dry_run)
    notifyer.run()

    if show_graph:
        notifyer.debug_show_graph()

    if show_data:
        notifyer.debug_show_dataframes()

if __name__ == "__main__":
    cli()
