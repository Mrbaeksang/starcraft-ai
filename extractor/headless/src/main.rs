use anyhow::{Context, Result, bail};
use bw_engine::chk;
use bw_engine::chk_units;
use bw_engine::dat::{DamageType, FlingyType, GameData, UnitSize, UnitType, WeaponType};
use bw_engine::tile::MiniTile;
use bw_engine::tileset::{CV5_ENTRY_SIZE, VF4_ENTRY_SIZE, Tileset};
use bw_engine::{EngineCommand, Game, Map};
use replay_core::command::{Command, HotkeyAction};
use replay_core::header::Race;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

const ENGINE_REV: &str = "befa5432c8749cdea196703c5b82c0f0fcfad2c5";
const INVALID_TAG: u16 = 0xFFFF;

#[derive(Debug)]
struct Options {
    replay: PathBuf,
    output: PathBuf,
    manifest: PathBuf,
    player_id: Option<u8>,
    horizon_frames: u32,
    max_frames: Option<u32>,
    game_data_root: Option<PathBuf>,
    synthetic: bool,
}

impl Options {
    fn parse() -> Result<Self> {
        let mut replay = None;
        let mut output = None;
        let mut manifest = None;
        let mut player_id = None;
        let mut horizon_frames = 8u32;
        let mut max_frames = None;
        let mut game_data_root = None;
        let mut synthetic = false;

        let args: Vec<String> = env::args().skip(1).collect();
        let mut index = 0usize;
        while index < args.len() {
            let arg = &args[index];
            let mut value = || -> Result<String> {
                index += 1;
                args.get(index)
                    .cloned()
                    .with_context(|| format!("missing value for {arg}"))
            };
            match arg.as_str() {
                "--replay" => replay = Some(PathBuf::from(value()?)),
                "--output" => output = Some(PathBuf::from(value()?)),
                "--manifest" => manifest = Some(PathBuf::from(value()?)),
                "--player-id" => player_id = Some(value()?.parse()?),
                "--horizon-frames" => horizon_frames = value()?.parse()?,
                "--max-frames" => max_frames = Some(value()?.parse()?),
                "--game-data-root" => game_data_root = Some(PathBuf::from(value()?)),
                "--synthetic" => synthetic = true,
                "--help" | "-h" => {
                    println!(
                        "Usage: scai-headless-extractor \
                         --replay game.rep --output transitions.jsonl \
                         [--manifest extraction.json] [--player-id N] \
                         [--horizon-frames 8] [--max-frames N] \
                         (--game-data-root STARCRAFT_DIR | --synthetic)"
                    );
                    std::process::exit(0);
                }
                _ => bail!("unknown argument: {arg}"),
            }
            index += 1;
        }

        let replay = replay.context("--replay is required")?;
        let output = output.context("--output is required")?;
        let manifest = manifest.unwrap_or_else(|| {
            let mut value = output.clone().into_os_string();
            value.push(".manifest.json");
            PathBuf::from(value)
        });
        if horizon_frames == 0 {
            bail!("--horizon-frames must be >= 1");
        }
        if synthetic == game_data_root.is_some() {
            bail!("choose exactly one of --synthetic or --game-data-root");
        }

        Ok(Self {
            replay,
            output,
            manifest,
            player_id,
            horizon_frames,
            max_frames,
            game_data_root,
            synthetic,
        })
    }
}

#[derive(Clone, Debug, Serialize)]
struct UnitRecord {
    unit_id: u16,
    type_id: u16,
    owner: &'static str,
    x: i32,
    y: i32,
    hp: i32,
    hp_max: i32,
    shields: i32,
    energy: i32,
    order_id: u8,
    visible: bool,
    position_source: &'static str,
    last_seen_frame: Option<u32>,
}

#[derive(Clone, Debug, Serialize)]
struct Observation {
    schema_version: u8,
    frame: u32,
    player_id: u8,
    minerals: i32,
    gas: i32,
    supply_used: i32,
    supply_total: i32,
    map_width: u16,
    map_height: u16,
    explored_fraction: f64,
    upgrades: Vec<u8>,
    techs: Vec<u8>,
    units: Vec<UnitRecord>,
}

#[derive(Clone, Debug, Serialize)]
struct Action {
    schema_version: u8,
    frame: u32,
    player_id: u8,
    action_type: &'static str,
    actor_unit_ids: Vec<u16>,
    target_unit_id: Option<u16>,
    target_x: Option<u32>,
    target_y: Option<u32>,
    argument_type_id: Option<u16>,
}

#[derive(Debug, Serialize)]
struct Transition {
    schema_version: u8,
    episode_id: String,
    step: u32,
    observation: Observation,
    action: Action,
    next_observation: Observation,
    reward: f32,
    terminal: bool,
}

#[derive(Clone, Debug)]
struct LastSeen {
    record: UnitRecord,
    frame: u32,
}

#[derive(Default)]
struct SelectionTracker {
    selected: BTreeMap<u8, Vec<u16>>,
    hotkeys: BTreeMap<(u8, u8), Vec<u16>>,
}

impl SelectionTracker {
    fn selected(&self, player: u8) -> Vec<u16> {
        self.selected.get(&player).cloned().unwrap_or_default()
    }

    fn observe(&mut self, player: u8, command: &Command) {
        match command {
            Command::Select { unit_tags } => {
                self.selected.insert(player, unit_tags.clone());
            }
            Command::SelectAdd { unit_tags } => {
                let selected = self.selected.entry(player).or_default();
                for tag in unit_tags {
                    if !selected.contains(tag) {
                        selected.push(*tag);
                    }
                }
            }
            Command::SelectRemove { unit_tags } => {
                let remove: BTreeSet<u16> = unit_tags.iter().copied().collect();
                self.selected
                    .entry(player)
                    .or_default()
                    .retain(|tag| !remove.contains(tag));
            }
            Command::Hotkey {
                action: HotkeyAction::Assign,
                group,
            } => {
                self.hotkeys.insert((player, *group), self.selected(player));
            }
            Command::Hotkey {
                action: HotkeyAction::Select,
                group,
            } => {
                let selected = self.hotkeys.get(&(player, *group)).cloned().unwrap_or_default();
                self.selected.insert(player, selected);
            }
            _ => {}
        }
    }
}

#[derive(Clone)]
struct Pending {
    step: u32,
    due_frame: u32,
    observation: Observation,
    action: Action,
}

#[derive(Serialize)]
struct Manifest {
    schema_version: u8,
    extractor: &'static str,
    extractor_version: &'static str,
    backend: &'static str,
    backend_commit: &'static str,
    fidelity: String,
    scientific_use: &'static str,
    replay_path: String,
    replay_sha256: String,
    output_sha256: String,
    map_name: String,
    player_id: u8,
    horizon_frames: u32,
    simulated_frames: u32,
    replay_frames: u32,
    truncated: bool,
    replay_commands: usize,
    translated_engine_commands: usize,
    emitted_actions: usize,
    emitted_transitions: usize,
    skipped_schema_actions: usize,
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn read_required(path: &Path, label: &str) -> Result<Vec<u8>> {
    fs::read(path).with_context(|| format!("failed to read {label}: {}", path.display()))
}

fn actual_game_data(root: &Path, replay: &replay_core::Replay) -> Result<(Map, GameData)> {
    let sections = chk::parse_sections(&replay.map_data)?;
    let terrain = chk::extract_terrain(&sections)?;
    let tileset = Tileset::from_index(terrain.tileset_index)?;
    let stem = tileset.file_stem();

    let arr = root.join("arr");
    let tileset_dir = root.join("tileset");
    let units = read_required(&arr.join("units.dat"), "units.dat")?;
    let flingy = read_required(&arr.join("flingy.dat"), "flingy.dat")?;
    let weapons = read_required(&arr.join("weapons.dat"), "weapons.dat")?;
    let tech = read_required(&arr.join("techdata.dat"), "techdata.dat")?;
    let upgrades = read_required(&arr.join("upgrades.dat"), "upgrades.dat")?;
    let orders = read_required(&arr.join("orders.dat"), "orders.dat")?;
    let cv5 = read_required(&tileset_dir.join(format!("{stem}.cv5")), "tileset cv5")?;
    let vf4 = read_required(&tileset_dir.join(format!("{stem}.vf4")), "tileset vf4")?;

    let map = Map::from_chk(&replay.map_data, &cv5, &vf4)?;
    let data = GameData::from_dat_all(&units, &flingy, &weapons, &tech, &upgrades, &orders)?;
    Ok((map, data))
}

fn synthetic_map(chk_data: &[u8]) -> Result<Map> {
    let sections = chk::parse_sections(chk_data)?;
    let terrain = chk::extract_terrain(&sections)?;
    let width = terrain.width;
    let height = terrain.height;

    let mut vf4 = vec![0u8; VF4_ENTRY_SIZE];
    for index in 0..16 {
        vf4[index * 2..index * 2 + 2].copy_from_slice(&MiniTile::WALKABLE.to_le_bytes());
    }
    let mut cv5 = vec![0u8; CV5_ENTRY_SIZE];
    cv5[20..22].copy_from_slice(&0u16.to_le_bytes());

    let mut synthetic_chk = Vec::new();
    synthetic_chk.extend_from_slice(b"DIM ");
    synthetic_chk.extend_from_slice(&4u32.to_le_bytes());
    synthetic_chk.extend_from_slice(&width.to_le_bytes());
    synthetic_chk.extend_from_slice(&height.to_le_bytes());
    synthetic_chk.extend_from_slice(b"ERA ");
    synthetic_chk.extend_from_slice(&2u32.to_le_bytes());
    synthetic_chk.extend_from_slice(&terrain.tileset_index.to_le_bytes());
    let tiles = vec![0u8; width as usize * height as usize * 2];
    synthetic_chk.extend_from_slice(b"MTXM");
    synthetic_chk.extend_from_slice(&(tiles.len() as u32).to_le_bytes());
    synthetic_chk.extend_from_slice(&tiles);

    Ok(Map::from_chk(&synthetic_chk, &cv5, &vf4)?)
}

fn synthetic_game_data() -> GameData {
    let flingy = FlingyType {
        top_speed: 4 * 256,
        acceleration: 256,
        halt_distance: 0,
        turn_rate: 40,
        movement_type: 0,
    };
    let default_unit = UnitType {
        flingy_id: 0,
        turret_unit_type: 228,
        hitpoints: 40 * 256,
        shield_points: 0,
        has_shield: false,
        ground_weapon: 0,
        max_ground_hits: 1,
        air_weapon: 130,
        max_air_hits: 0,
        armor: 0,
        armor_upgrade: 0,
        unit_size: UnitSize::Small,
        elevation: 0,
        sight_range: 7,
        build_time: 100,
        mineral_cost: 50,
        gas_cost: 0,
        supply_cost: 2,
        supply_provided: 0,
        is_building: false,
    };
    let building = UnitType {
        is_building: true,
        hitpoints: 1000 * 256,
        ground_weapon: 130,
        unit_size: UnitSize::Large,
        ..default_unit
    };
    let mut unit_types = vec![default_unit; 228];
    for unit in &mut unit_types[106..=202] {
        *unit = building;
    }
    let weapon = WeaponType {
        damage_amount: 6,
        damage_bonus: 0,
        cooldown: 15,
        damage_factor: 1,
        damage_type: DamageType::Normal,
        damage_upgrade: 7,
        max_range: 128,
        inner_splash: 0,
        medium_splash: 0,
        outer_splash: 0,
    };
    GameData {
        flingy_types: vec![flingy; 209],
        unit_types,
        weapon_types: vec![weapon; 130],
        tech_types: Vec::new(),
        upgrade_types: Vec::new(),
        order_types: Vec::new(),
        fallback_flingy: Vec::new(),
    }
}

fn race_code(race: Race) -> u8 {
    match race {
        Race::Zerg => 0,
        Race::Terran => 1,
        Race::Protoss => 2,
        Race::Unknown(_) => 1,
    }
}

fn engine_command(command: &Command) -> Option<EngineCommand> {
    match command {
        Command::Select { unit_tags } => Some(EngineCommand::Select(unit_tags.clone())),
        Command::SelectAdd { unit_tags } => Some(EngineCommand::SelectAdd(unit_tags.clone())),
        Command::SelectRemove { unit_tags } => Some(EngineCommand::SelectRemove(unit_tags.clone())),
        Command::Hotkey {
            action: HotkeyAction::Assign,
            group,
        } => Some(EngineCommand::HotkeyAssign { group: *group }),
        Command::Hotkey {
            action: HotkeyAction::Select,
            group,
        } => Some(EngineCommand::HotkeyRecall { group: *group }),
        Command::Build {
            x, y, unit_type, ..
        } => Some(EngineCommand::Build {
            x: *x,
            y: *y,
            unit_type: *unit_type,
        }),
        Command::RightClick {
            x, y, target_tag, ..
        } if *target_tag == 0 || *target_tag == INVALID_TAG => {
            Some(EngineCommand::Move { x: *x, y: *y })
        }
        Command::RightClick { target_tag, .. } => Some(EngineCommand::Attack {
            target_tag: *target_tag,
        }),
        Command::TargetedOrder {
            x,
            y,
            target_tag: _,
            order,
            ..
        } if *order == 0x06 => Some(EngineCommand::Move { x: *x, y: *y }),
        Command::TargetedOrder { target_tag, .. }
            if *target_tag != 0 && *target_tag != INVALID_TAG =>
        {
            Some(EngineCommand::Attack {
                target_tag: *target_tag,
            })
        }
        Command::Train { unit_type } => Some(EngineCommand::Train {
            unit_type: *unit_type,
        }),
        Command::UnitMorph { unit_type } => Some(EngineCommand::UnitMorph {
            unit_type: *unit_type,
        }),
        Command::BuildingMorph { unit_type } => Some(EngineCommand::BuildingMorph {
            unit_type: *unit_type,
        }),
        Command::Research { tech_type } => Some(EngineCommand::Research {
            tech_type: *tech_type,
        }),
        Command::Upgrade { upgrade_type } => Some(EngineCommand::Upgrade {
            upgrade_type: *upgrade_type,
        }),
        Command::Stop { .. } => Some(EngineCommand::Stop),
        Command::Stim => Some(EngineCommand::Stim),
        Command::Burrow { .. } => Some(EngineCommand::Burrow),
        Command::Unburrow { .. } => Some(EngineCommand::Unburrow),
        Command::Cloak { .. } => Some(EngineCommand::Cloak),
        Command::Decloak { .. } => Some(EngineCommand::Decloak),
        Command::UnloadAll { .. } => Some(EngineCommand::UnloadAll),
        _ => None,
    }
}

fn schema_action(
    command: &Command,
    frame: u32,
    player_id: u8,
    actors: Vec<u16>,
) -> Option<Action> {
    if actors.is_empty() {
        return None;
    }
    let mut action = Action {
        schema_version: 1,
        frame,
        player_id,
        action_type: "NOOP",
        actor_unit_ids: actors,
        target_unit_id: None,
        target_x: None,
        target_y: None,
        argument_type_id: None,
    };

    match command {
        Command::Build {
            x, y, unit_type, ..
        } => {
            action.action_type = "BUILD";
            action.target_x = Some(*x as u32 * 32);
            action.target_y = Some(*y as u32 * 32);
            action.argument_type_id = Some(*unit_type);
        }
        Command::RightClick {
            x, y, target_tag, ..
        } => {
            action.action_type = "RIGHT_CLICK";
            if *target_tag != 0 && *target_tag != INVALID_TAG {
                action.target_unit_id = Some(*target_tag);
            } else {
                action.target_x = Some(*x as u32);
                action.target_y = Some(*y as u32);
            }
        }
        Command::TargetedOrder {
            x,
            y,
            target_tag: _,
            order,
            ..
        } if *order == 0x06 => {
            action.action_type = "MOVE";
            action.target_x = Some(*x as u32);
            action.target_y = Some(*y as u32);
        }
        Command::TargetedOrder { target_tag, .. }
            if *target_tag != 0 && *target_tag != INVALID_TAG =>
        {
            action.action_type = "ATTACK_UNIT";
            action.target_unit_id = Some(*target_tag);
        }
        Command::Train { unit_type } => {
            action.action_type = "TRAIN";
            action.argument_type_id = Some(*unit_type);
        }
        Command::UnitMorph { unit_type } | Command::BuildingMorph { unit_type } => {
            action.action_type = "MORPH";
            action.argument_type_id = Some(*unit_type);
        }
        Command::Research { tech_type } => {
            action.action_type = "RESEARCH";
            action.argument_type_id = Some(*tech_type as u16);
        }
        Command::Upgrade { upgrade_type } => {
            action.action_type = "UPGRADE";
            action.argument_type_id = Some(*upgrade_type as u16);
        }
        Command::Stop { .. } => action.action_type = "STOP",
        Command::HoldPosition { .. } => action.action_type = "HOLD",
        _ => return None,
    }
    Some(action)
}

fn relation(owner: u8, perspective: u8) -> &'static str {
    if owner == perspective {
        "self"
    } else if owner >= 8 {
        "neutral"
    } else {
        "enemy"
    }
}

fn unit_record(
    unit: &bw_engine::UnitState,
    owner: &'static str,
    visible: bool,
    frame: u32,
) -> UnitRecord {
    UnitRecord {
        unit_id: unit.id.to_tag(),
        type_id: unit.unit_type,
        owner,
        x: unit.pixel_x.max(0),
        y: unit.pixel_y.max(0),
        hp: (unit.hp.max(0) / 256).max(0),
        hp_max: (unit.max_hp.max(0) / 256).max(0),
        shields: (unit.shields.max(0) / 256).max(0),
        energy: (unit.energy.max(0) / 256).max(0),
        order_id: 0,
        visible,
        position_source: if visible { "current" } else { "last_seen" },
        last_seen_frame: if visible { None } else { Some(frame) },
    }
}

fn capture_observation(
    game: &Game,
    static_units: &[UnitType],
    perspective: u8,
    memory: &mut BTreeMap<u16, LastSeen>,
) -> Observation {
    let frame = game.current_frame();
    let mut records = Vec::new();
    let mut live_tags = BTreeSet::new();
    let mut visible_enemy_tags = BTreeSet::new();

    for unit in game.units() {
        let tag = unit.id.to_tag();
        live_tags.insert(tag);
        let owner = relation(unit.owner, perspective);
        let tile_x = (unit.pixel_x.max(0) / 32) as u16;
        let tile_y = (unit.pixel_y.max(0) / 32) as u16;
        let visible = owner == "self"
            || ((owner == "enemy" || owner == "neutral")
                && game.vision.is_visible(perspective, tile_x, tile_y));

        if visible {
            let record = unit_record(unit, owner, true, frame);
            if owner == "enemy" {
                visible_enemy_tags.insert(tag);
                memory.insert(
                    tag,
                    LastSeen {
                        record: record.clone(),
                        frame,
                    },
                );
            }
            records.push(record);
        }
    }

    let memory_tags: Vec<u16> = memory.keys().copied().collect();
    for tag in memory_tags {
        if visible_enemy_tags.contains(&tag) {
            continue;
        }
        let Some(last) = memory.get(&tag).cloned() else {
            continue;
        };
        let tile_x = (last.record.x.max(0) / 32) as u16;
        let tile_y = (last.record.y.max(0) / 32) as u16;
        if !live_tags.contains(&tag) && game.vision.is_visible(perspective, tile_x, tile_y) {
            memory.remove(&tag);
            continue;
        }
        let mut record = last.record;
        record.visible = false;
        record.position_source = "last_seen";
        record.last_seen_frame = Some(last.frame);
        records.push(record);
    }

    records.sort_by_key(|unit| unit.unit_id);

    let player = game.player_state(perspective).cloned().unwrap_or_default();
    let mut supply_used = 0i32;
    let mut supply_total = 0i32;
    for unit in game.units().filter(|unit| unit.owner == perspective) {
        if let Some(kind) = static_units.get(unit.unit_type as usize) {
            supply_used += kind.supply_cost as i32;
            supply_total += kind.supply_provided as i32;
        }
    }
    supply_total = supply_total.max(supply_used);

    let upgrades = player
        .upgrade_levels
        .iter()
        .enumerate()
        .filter_map(|(index, level)| (*level > 0).then_some(index as u8))
        .collect();
    let techs = (0u8..64).filter(|tech| player.has_tech(*tech)).collect();

    let vision = game.vision.visibility_grid(perspective);
    let explored = vision.iter().filter(|cell| **cell > 0).count();
    let explored_fraction = if vision.is_empty() {
        0.0
    } else {
        explored as f64 / vision.len() as f64
    };

    Observation {
        schema_version: 1,
        frame,
        player_id: perspective,
        minerals: player.minerals.max(0),
        gas: player.gas.max(0),
        supply_used,
        supply_total,
        map_width: game.map().width(),
        map_height: game.map().height(),
        explored_fraction,
        upgrades,
        techs,
        units: records,
    }
}

fn write_atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut temp = path.as_os_str().to_os_string();
    temp.push(".tmp");
    let temp = PathBuf::from(temp);
    fs::write(&temp, bytes)?;
    if path.exists() {
        fs::remove_file(path)?;
    }
    fs::rename(temp, path)?;
    Ok(())
}

fn main() -> Result<()> {
    let options = Options::parse()?;
    let replay_bytes = fs::read(&options.replay)
        .with_context(|| format!("failed to read replay: {}", options.replay.display()))?;
    let replay = replay_core::parse(&replay_bytes).context("failed to parse replay")?;

    let perspective = options.player_id.unwrap_or_else(|| {
        replay
            .header
            .players
            .first()
            .map(|player| player.player_id)
            .unwrap_or(0)
    });
    if !replay
        .header
        .players
        .iter()
        .any(|player| player.player_id == perspective)
    {
        bail!("player id {perspective} does not exist in this replay");
    }

    let (map, game_data, fidelity) = if options.synthetic {
        (
            synthetic_map(&replay.map_data)?,
            synthetic_game_data(),
            "synthetic-ci".to_string(),
        )
    } else {
        let root = options
            .game_data_root
            .as_deref()
            .context("--game-data-root is required")?;
        let (map, data) = actual_game_data(root, &replay)?;
        (map, data, "headless-real-gamedata".to_string())
    };
    let static_units = game_data.unit_types.clone();
    let mut game = Game::new(map, game_data);

    let sections = chk::parse_sections(&replay.map_data)?;
    let initial_units = chk_units::parse_chk_units(&sections)?;
    game.load_initial_units(&initial_units)?;

    let start_locations = chk_units::parse_start_locations(&sections)
        .into_iter()
        .map(|(owner, x, y)| (owner, x as i32, y as i32))
        .collect::<Vec<_>>();
    let races = replay
        .header
        .players
        .iter()
        .map(|player| (player.player_id, race_code(player.race)))
        .collect::<Vec<_>>();
    game.create_melee_starting_units(&start_locations, &races);
    for player in &replay.header.players {
        game.set_player_resources(player.player_id, 50, 0);
    }

    let replay_limit = options
        .max_frames
        .unwrap_or(replay.header.frame_count)
        .min(replay.header.frame_count);
    let truncated = replay_limit < replay.header.frame_count;

    let mut tracker = SelectionTracker::default();
    let mut memory = BTreeMap::new();
    let mut pending: Vec<Pending> = Vec::new();
    let mut transitions = Vec::new();
    let mut command_index = 0usize;
    let mut step = 0u32;
    let mut translated_engine_commands = 0usize;
    let mut emitted_actions = 0usize;
    let mut skipped_schema_actions = 0usize;
    let replay_hash = sha256_bytes(&replay_bytes);
    let episode_id = format!("headless-{}-p{perspective}", &replay_hash[..16]);

    for frame in 0..=replay_limit {
        let current = capture_observation(&game, &static_units, perspective, &mut memory);

        let mut remaining = Vec::new();
        for item in pending.drain(..) {
            if item.due_frame <= frame {
                transitions.push(Transition {
                    schema_version: 1,
                    episode_id: episode_id.clone(),
                    step: item.step,
                    observation: item.observation,
                    action: item.action,
                    next_observation: current.clone(),
                    reward: 0.0,
                    terminal: !truncated && frame >= replay.header.frame_count,
                });
            } else {
                remaining.push(item);
            }
        }
        pending = remaining;

        while command_index < replay.commands.len()
            && replay.commands[command_index].frame == frame
        {
            let entry = &replay.commands[command_index];
            let actors = tracker.selected(entry.player_id);
            if entry.player_id == perspective && entry.command.is_meaningful_action() {
                if let Some(action) =
                    schema_action(&entry.command, frame, perspective, actors.clone())
                {
                    pending.push(Pending {
                        step,
                        due_frame: frame.saturating_add(options.horizon_frames),
                        observation: current.clone(),
                        action,
                    });
                    step += 1;
                    emitted_actions += 1;
                } else {
                    skipped_schema_actions += 1;
                }
            }

            if let Some(command) = engine_command(&entry.command) {
                game.apply_command(entry.player_id, &command);
                translated_engine_commands += 1;
            }
            tracker.observe(entry.player_id, &entry.command);
            command_index += 1;
        }

        if frame < replay_limit {
            game.step();
        }
    }

    let mut output = Vec::new();
    for transition in &transitions {
        serde_json::to_writer(&mut output, transition)?;
        output.push(b'\n');
    }
    write_atomic(&options.output, &output)?;

    let manifest = Manifest {
        schema_version: 1,
        extractor: "scai-headless-extractor",
        extractor_version: env!("CARGO_PKG_VERSION"),
        backend: "broodwar-live/bw-engine",
        backend_commit: ENGINE_REV,
        fidelity,
        scientific_use: "pipeline-validation-only-until-cross-validated-against-BWAPI",
        replay_path: options.replay.display().to_string(),
        replay_sha256: replay_hash,
        output_sha256: sha256_bytes(&output),
        map_name: replay.header.map_name.clone(),
        player_id: perspective,
        horizon_frames: options.horizon_frames,
        simulated_frames: replay_limit,
        replay_frames: replay.header.frame_count,
        truncated,
        replay_commands: replay.commands.len(),
        translated_engine_commands,
        emitted_actions,
        emitted_transitions: transitions.len(),
        skipped_schema_actions,
    };
    let manifest_bytes = serde_json::to_vec_pretty(&manifest)?;
    write_atomic(&options.manifest, &manifest_bytes)?;

    eprintln!(
        "map={} player={} frames={} transitions={} fidelity={}",
        replay.header.map_name,
        perspective,
        replay_limit,
        transitions.len(),
        manifest.fidelity
    );
    if transitions.is_empty() {
        bail!("extraction produced zero TransitionV1 records");
    }
    Ok(())
}
