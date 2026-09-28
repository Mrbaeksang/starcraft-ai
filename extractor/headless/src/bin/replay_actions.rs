use anyhow::{Context, Result, bail};
use replay_core::command::{Command, HotkeyAction};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::PathBuf;

#[derive(Default)]
struct SelectionTracker {
    selected: BTreeMap<u8, Vec<u16>>,
    hotkeys: BTreeMap<(u8, u8), Vec<u16>>,
}

impl SelectionTracker {
    fn selected(&self, player_id: u8) -> Vec<u16> {
        self.selected.get(&player_id).cloned().unwrap_or_default()
    }

    fn observe(&mut self, player_id: u8, command: &Command) {
        match command {
            Command::Select { unit_tags } => {
                self.selected.insert(player_id, unit_tags.clone());
            }
            Command::SelectAdd { unit_tags } => {
                let selected = self.selected.entry(player_id).or_default();
                for tag in unit_tags {
                    if !selected.contains(tag) {
                        selected.push(*tag);
                    }
                }
            }
            Command::SelectRemove { unit_tags } => {
                let remove: BTreeSet<u16> = unit_tags.iter().copied().collect();
                self.selected
                    .entry(player_id)
                    .or_default()
                    .retain(|tag| !remove.contains(tag));
            }
            Command::Hotkey {
                action: HotkeyAction::Assign,
                group,
            } => {
                self.hotkeys
                    .insert((player_id, *group), self.selected(player_id));
            }
            Command::Hotkey {
                action: HotkeyAction::Select,
                group,
            } => {
                let selected = self
                    .hotkeys
                    .get(&(player_id, *group))
                    .cloned()
                    .unwrap_or_default();
                self.selected.insert(player_id, selected);
            }
            _ => {}
        }
    }
}

#[derive(Serialize)]
struct ActionEvent<'a> {
    schema_version: u8,
    ordinal: usize,
    frame: u32,
    player_id: u8,
    selected_unit_tags: Vec<u16>,
    command: &'a Command,
}

fn is_action(command: &Command) -> bool {
    !matches!(
        command,
        Command::Select { .. }
            | Command::SelectAdd { .. }
            | Command::SelectRemove { .. }
            | Command::Hotkey { .. }
            | Command::KeepAlive
            | Command::Other { .. }
            | Command::Chat { .. }
            | Command::LeaveGame { .. }
            | Command::MinimapPing { .. }
    )
}

fn parse_args() -> Result<(PathBuf, PathBuf)> {
    let mut replay = None;
    let mut output = None;
    let args: Vec<String> = env::args().skip(1).collect();
    let mut index = 0usize;

    while index < args.len() {
        match args[index].as_str() {
            "--replay" => {
                index += 1;
                replay = Some(PathBuf::from(
                    args.get(index).context("missing value for --replay")?,
                ));
            }
            "--output" => {
                index += 1;
                output = Some(PathBuf::from(
                    args.get(index).context("missing value for --output")?,
                ));
            }
            "--help" | "-h" => {
                println!("usage: replay-actions --replay GAME.rep --output actions.jsonl");
                std::process::exit(0);
            }
            value => bail!("unknown argument: {value}"),
        }
        index += 1;
    }

    Ok((
        replay.context("--replay is required")?,
        output.context("--output is required")?,
    ))
}

fn main() -> Result<()> {
    let (replay_path, output_path) = parse_args()?;
    let bytes = fs::read(&replay_path)
        .with_context(|| format!("failed to read replay: {}", replay_path.display()))?;
    let replay = replay_core::parse(&bytes).context("failed to parse replay")?;

    let mut tracker = SelectionTracker::default();
    let mut output = Vec::new();
    let mut ordinal = 0usize;

    for entry in &replay.commands {
        let selected = tracker.selected(entry.player_id);

        if is_action(&entry.command) {
            let event = ActionEvent {
                schema_version: 1,
                ordinal,
                frame: entry.frame,
                player_id: entry.player_id,
                selected_unit_tags: selected,
                command: &entry.command,
            };
            serde_json::to_writer(&mut output, &event)?;
            output.push(b'\n');
            ordinal += 1;
        }

        tracker.observe(entry.player_id, &entry.command);
    }

    if ordinal == 0 {
        bail!("replay contains zero gameplay action events");
    }

    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&output_path, output)?;

    println!(
        "actions={} replay_frames={} map={}",
        ordinal, replay.header.frame_count, replay.header.map_name
    );
    Ok(())
}
