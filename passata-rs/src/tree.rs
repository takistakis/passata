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

use crate::database::Database;
use crate::output::{pager_color, render_tree};

/// Display a selected group's descendants as a paged tree with optional colors.
pub fn tree(
    db: &Database,
    args: &clap::ArgMatches,
    configured_color: Option<bool>,
) -> Result<(), String> {
    let group = args.get_one::<String>("group").map(String::as_str);
    let node = db.get(group)?;
    let items = db.group_items(group)?;
    if items.is_empty() {
        return Ok(());
    }

    let mut pager = Pager::new();
    pager.setup();
    let color = pager_color(args, configured_color, pager.is_on());
    let label = group.map(|name| name.trim_end_matches('/')).unwrap_or(".");
    println!("{}", render_tree(node, label, color));
    Ok(())
}
