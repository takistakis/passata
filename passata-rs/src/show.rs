// Copyright 2026 Panagiotis Ktistakis <panktist@gmail.com>
//
// This file is part of passata-rs.
//
// passata-rs is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// passata-rs is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with passata-rs.  If not, see <http://www.gnu.org/licenses/>.

use pager::Pager;

use crate::database::{Database, entry_password, is_entry};
use crate::output::{clipboard, clipboard_timeout, colorize, pager_color};

/// Display a selected node as YAML or copy an entry's non-null password to the clipboard.
pub fn show(
    db: &Database,
    args: &clap::ArgMatches,
    configured_color: Option<bool>,
    configured_timeout: Option<u64>,
) -> Result<(), String> {
    let name = args.get_one::<String>("name").map(String::as_str);
    let entry = db.get(name)?;

    if args.get_flag("clip") && !args.get_flag("no_clip") {
        let Some(name) = name else {
            return Err(String::from("Can't put the entire database to clipboard"));
        };
        if !is_entry(entry) {
            return Err(String::from("Can't put a group to clipboard"));
        }
        let password = entry_password(entry, name)?;
        clipboard(&password, clipboard_timeout(args, configured_timeout))?;
        return Ok(());
    }

    let output = db.yaml_for(entry)?;
    let output = output.trim();
    let mut pager = Pager::new();
    pager.setup();
    let output = if pager_color(args, configured_color, pager.is_on()) {
        colorize(output)
    } else {
        output.to_owned()
    };
    println!("{}", output);
    Ok(())
}
