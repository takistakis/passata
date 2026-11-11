// Copyright 2026 Panagiotis Ktistakis <panktist@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later

use yaml_rust::{Yaml, YamlEmitter, YamlLoader};

pub fn load(text: &str) -> Result<Vec<Yaml>, String> {
    YamlLoader::load_from_str(text).map_err(|error| error.to_string())
}

/// Serialize with the native emitter, omitting its document marker.
pub fn dump(data: &Yaml) -> Result<String, String> {
    if matches!(data, Yaml::Hash(map) if map.is_empty()) {
        return Ok(String::new());
    }
    let mut output = String::new();
    YamlEmitter::new(&mut output)
        .dump(data)
        .map_err(|error| format!("Couldn't serialize database: {}", error))?;
    Ok(format!("{}\n", output.trim_start_matches("---\n")))
}

#[cfg(test)]
#[path = "../tests/unit/yaml.rs"]
mod tests;
