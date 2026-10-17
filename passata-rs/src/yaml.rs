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

use std::sync::OnceLock;

use regex::Regex;
use yaml_rust::{Yaml, YamlEmitter};

fn implicit_scalar(value: &str) -> bool {
    static IMPLICIT: OnceLock<Regex> = OnceLock::new();
    let implicit = IMPLICIT.get_or_init(|| {
        Regex::new(
            r"(?x)\A(?:
                yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|
                on|On|ON|off|Off|OFF|null|Null|NULL|~|<<|=|
                [-+]?0b[01_]+|[-+]?0[0-7_]+|[-+]?(?:0|[1-9][0-9_]*)|
                [-+]?0x[0-9a-fA-F_]+|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+|
                [-+]?[0-9][0-9_]*\.[0-9_]*(?:[eE][-+][0-9]+)?|
                \.[0-9][0-9_]*(?:[eE][-+][0-9]+)?|
                [-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*|
                [-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)|
                [0-9]{4}-[0-9]{2}-[0-9]{2}|
                [0-9]{4}-[0-9]{1,2}-[0-9]{1,2}
                (?:[Tt]|[\x20\t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}
                (?:\.[0-9]*)?(?:[\x20\t]*(?:Z|[-+][0-9]{1,2}(?::[0-9]{2})?))?
            )\z",
        )
        .expect("valid YAML implicit scalar pattern")
    });
    // Also protect types recognized by the Rust loader but not by PyYAML's YAML 1.1 resolver.
    implicit.is_match(value) || !matches!(Yaml::from_str(value), Yaml::String(_))
}

fn printable(ch: char) -> bool {
    matches!(ch, '\x20'..='\x7e' | '\u{a0}'..='\u{d7ff}' | '\u{e000}'..='\u{fffd}' | '\u{10000}'..='\u{10fffe}')
        && ch != '\u{feff}'
}

fn scalar(node: &Yaml) -> Result<String, String> {
    if let Yaml::String(value) = node {
        let chars: Vec<_> = value.chars().collect();
        let plain = !value.is_empty()
            && !value.starts_with([' ', '\n', '\r'])
            && !value.ends_with([' ', '\n', '\r'])
            && !value.starts_with("---")
            && !value.starts_with("...")
            && !chars
                .first()
                .is_some_and(|ch| "#,[]{}&*!|>'\"%@`".contains(*ch))
            && !chars.iter().enumerate().any(|(index, ch)| {
                !printable(*ch)
                    || matches!(ch, '\u{2028}' | '\u{2029}')
                    || ((*ch == ':' || (index == 0 && matches!(ch, '?' | '-')))
                        && chars.get(index + 1).is_none_or(|next| next.is_whitespace()))
                    || (*ch == '#' && (index == 0 || chars[index - 1].is_whitespace()))
            })
            && !implicit_scalar(value);
        if plain {
            return Ok(value.clone());
        }
        if chars
            .iter()
            .all(|ch| printable(*ch) && !matches!(ch, '\u{2028}' | '\u{2029}'))
        {
            return Ok(format!("'{}'", value.replace('\'', "''")));
        }
        // Keep multiline and control characters escaped rather than folding their contents.
        let mut escaped = String::from("\"");
        for ch in chars {
            match ch {
                '"' => escaped.push_str("\\\""),
                '\\' => escaped.push_str("\\\\"),
                '\n' => escaped.push_str("\\n"),
                '\r' => escaped.push_str("\\r"),
                '\t' => escaped.push_str("\\t"),
                '\u{2028}' | '\u{2029}' => escaped.push_str(&format!("\\u{:04X}", ch as u32)),
                ch if printable(ch) => escaped.push(ch),
                ch if (ch as u32) <= 0xff => escaped.push_str(&format!("\\x{:02X}", ch as u32)),
                ch if (ch as u32) <= 0xffff => escaped.push_str(&format!("\\u{:04X}", ch as u32)),
                ch => escaped.push_str(&format!("\\U{:08X}", ch as u32)),
            }
        }
        escaped.push('"');
        return Ok(escaped);
    }
    match node {
        Yaml::Null => Ok(String::from("null")),
        Yaml::BadValue | Yaml::Alias(_) => {
            Err(String::from("Couldn't serialize unresolved YAML value"))
        }
        _ => {
            let mut output = String::new();
            YamlEmitter::new(&mut output)
                .dump(node)
                .map_err(|e| format!("Couldn't serialize database: {}", e))?;
            Ok(output.trim_start_matches("---\n").to_owned())
        }
    }
}

fn nonempty_collection(node: &Yaml) -> bool {
    match node {
        Yaml::Hash(map) => !map.is_empty(),
        Yaml::Array(items) => !items.is_empty(),
        _ => false,
    }
}

fn emit(node: &Yaml, indent: usize, output: &mut String) -> Result<(), String> {
    let padding = " ".repeat(indent);
    match node {
        Yaml::Hash(map) if !map.is_empty() => {
            for (key, value) in map {
                output.push_str(&padding);
                if nonempty_collection(key) {
                    output.push_str("?\n");
                    emit(key, indent + 2, output)?;
                    output.push_str(&padding);
                } else {
                    let key = scalar(key)?;
                    // YAML limits implicit mapping keys to 1024 characters.
                    if key.chars().count() > 1024 {
                        output.push_str("? ");
                        output.push_str(&key);
                        output.push('\n');
                        output.push_str(&padding);
                    } else {
                        output.push_str(&key);
                    }
                }
                output.push(':');
                emit_value(value, indent, output)?;
            }
        }
        Yaml::Array(items) if !items.is_empty() => {
            for item in items {
                output.push_str(&padding);
                output.push('-');
                if nonempty_collection(item) {
                    output.push('\n');
                    emit(item, indent + 2, output)?;
                } else {
                    output.push(' ');
                    output.push_str(&scalar(item)?);
                    output.push('\n');
                }
            }
        }
        _ => {
            output.push_str(&padding);
            output.push_str(&scalar(node)?);
            output.push('\n');
        }
    }
    Ok(())
}

fn emit_value(node: &Yaml, indent: usize, output: &mut String) -> Result<(), String> {
    if nonempty_collection(node) {
        output.push('\n');
        // PyYAML uses indentless sequences for mapping values.
        emit(
            node,
            indent + if matches!(node, Yaml::Array(_)) { 0 } else { 2 },
            output,
        )?;
    } else {
        output.push(' ');
        output.push_str(&scalar(node)?);
        output.push('\n');
    }
    Ok(())
}

/// Emit block YAML with PyYAML-like plain/single-quoted strings and safe type preservation.
pub fn dump(data: &Yaml) -> Result<String, String> {
    let mut output = String::new();
    emit(data, 0, &mut output)?;
    Ok(output)
}

#[cfg(test)]
#[path = "../tests/unit/yaml.rs"]
mod tests;
