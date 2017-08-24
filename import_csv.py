#!/usr/bin/env python3

# Copyright 2017 Panagiotis Ktistakis <panktist@gmail.com>
#
# This file is part of passata.
#
# passata is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# passata is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with passata.  If not, see <http://www.gnu.org/licenses/>.

"""Migrate a keepassx2 csv database to passata yaml format."""

import collections
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

    db = collections.OrderedDict()
    next(file)  # Skip headers
    for line in csv.reader(file):
        group, title, username, password, url, notes = line
        if not group.startswith('Root/'):
            passata.die("Every entry should be in a group")
        group = group[5:]  # Skip 'Root/'
        name = '/'.join([group, title])
        entry = collections.OrderedDict()
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
