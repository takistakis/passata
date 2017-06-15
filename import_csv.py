#!/usr/bin/env python3

"""Migrate a keepassx2 csv database to passata yaml format."""

import csv
import os.path

import click

import passata


@click.command()
@click.option('--config', type=click.Path(dir_okay=False),
              default=os.path.join(click.get_app_dir('passata'), 'config.yml'),
              envvar='PASSATA_CONFIG_PATH',
              help="Path of the configuration file.")
@click.argument('file', type=click.File())
@click.pass_context
def import_csv(ctx, config, file):
    """Migrate a keepassx2 csv database to passata yaml format.

    Unlike keepassx2, in passata each entry must be in a group and groups
    cannot be nested. So, if an entry in the csv file has any of these
    properties, this script will fail.
    """
    ctx.obj = passata.read_config(config)

    db = {}
    next(file)  # Skip headers
    for line in csv.reader(file):
        group, title, username, password, url, notes = line
        if not group.startswith('Root/'):
            passata.die("Every entry should be in a group")
        group = group[5:]  # Skip 'Root/'
        name = '/'.join([group, title])
        entry = {}
        if username:
            entry['username'] = username
        if password:
            entry['password'] = password
        if url:
            entry['url'] = url
        if notes:
            entry['notes'] = notes
        passata.put(db, name, entry)

    passata.write_db(db, force=False)


if __name__ == '__main__':
    import_csv()  # pylint: disable=no-value-for-parameter
