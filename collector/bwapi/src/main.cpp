#include <BWAPI.h>
#include <BWAPI/Client.h>

#include "transition_json.hpp"

#include <algorithm>
#include <chrono>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Options {
  std::string output = "transitions.jsonl";
  std::string mode = "live";
  std::string observability = "player";
  int player_id = -1;
  int horizon_frames = 8;
};

struct PendingTransition {
  int step = 0;
  int due_frame = 0;
  scai::ObservationRecord observation;
  scai::ActionRecord action;
};

Options parse_options(int argc, char** argv) {
  Options options;
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    auto require_value = [&]() -> std::string {
      if (index + 1 >= argc) throw std::runtime_error("missing value for " + arg);
      return argv[++index];
    };

    if (arg == "--output") {
      options.output = require_value();
    } else if (arg == "--mode") {
      options.mode = require_value();
    } else if (arg == "--observability") {
      options.observability = require_value();
    } else if (arg == "--player-id") {
      options.player_id = std::stoi(require_value());
    } else if (arg == "--horizon-frames") {
      options.horizon_frames = std::stoi(require_value());
    } else if (arg == "--help") {
      std::cout
          << "BWAPICollector options:\n"
          << "  --output FILE\n"
          << "  --mode live|replay\n"
          << "  --observability player|privileged\n"
          << "  --player-id ID          required for replay mode\n"
          << "  --horizon-frames N      default: 8\n";
      std::exit(0);
    } else {
      throw std::runtime_error("unknown argument: " + arg);
    }
  }

  if (options.mode != "live" && options.mode != "replay") {
    throw std::runtime_error("--mode must be live or replay");
  }
  if (options.observability != "player" && options.observability != "privileged") {
    throw std::runtime_error("--observability must be player or privileged");
  }
  if (options.mode == "replay" && options.player_id < 0) {
    throw std::runtime_error("--player-id is required for replay mode");
  }
  if (options.horizon_frames < 1) {
    throw std::runtime_error("--horizon-frames must be >= 1");
  }
  return options;
}

void connect() {
  while (!BWAPI::BWAPIClient.connect()) {
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
  }
}

BWAPI::Player perspective_player(const Options& options) {
  if (options.mode == "live") return BWAPI::Broodwar->self();
  return BWAPI::Broodwar->getPlayer(options.player_id);
}

std::string owner_relation(BWAPI::Player owner, BWAPI::Player perspective) {
  if (!owner) return "neutral";
  if (owner == perspective) return "self";
  if (owner->isNeutral()) return "neutral";
  return "enemy";
}

double explored_fraction_live() {
  const int width = BWAPI::Broodwar->mapWidth();
  const int height = BWAPI::Broodwar->mapHeight();
  if (width <= 0 || height <= 0) return 0.0;

  int explored = 0;
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      if (BWAPI::Broodwar->isExplored(x, y)) ++explored;
    }
  }
  return static_cast<double>(explored) / static_cast<double>(width * height);
}

scai::ObservationRecord capture_observation(
    const Options& options,
    BWAPI::Player perspective) {
  scai::ObservationRecord observation;
  observation.frame = BWAPI::Broodwar->getFrameCount();
  observation.player_id = perspective->getID();
  observation.minerals = perspective->minerals();
  observation.gas = perspective->gas();
  observation.supply_used = perspective->supplyUsed();
  observation.supply_total = std::max(perspective->supplyTotal(), observation.supply_used);
  observation.map_width = BWAPI::Broodwar->mapWidth();
  observation.map_height = BWAPI::Broodwar->mapHeight();
  // BWAPI's public replay tile API is replay-wide rather than arbitrary
  // perspective-player-specific, so do not pretend it is a player view.
  observation.explored_fraction =
      options.mode == "live" ? explored_fraction_live() : 0.0;

  for (const auto upgrade : BWAPI::UpgradeTypes::allUpgradeTypes()) {
    if (perspective->getUpgradeLevel(upgrade) > 0) {
      observation.upgrades.push_back(upgrade.getID());
    }
  }
  for (const auto tech : BWAPI::TechTypes::allTechTypes()) {
    if (perspective->hasResearched(tech)) {
      observation.techs.push_back(tech.getID());
    }
  }

  for (const auto unit : BWAPI::Broodwar->getAllUnits()) {
    if (!unit || !unit->exists()) continue;

    const std::string relation = owner_relation(unit->getPlayer(), perspective);
    const bool player_visible =
        relation == "self" || unit->isVisible(perspective);
    if (options.observability == "player" && !player_visible) continue;

    const auto position = unit->getPosition();
    if (!position.isValid()) continue;

    scai::UnitRecord record;
    record.unit_id = unit->getID();
    record.type_id = unit->getType().getID();
    record.owner = relation;
    record.x = std::max(position.x, 0);
    record.y = std::max(position.y, 0);
    record.hp = std::max(unit->getHitPoints(), 0);
    record.hp_max = std::max(unit->getType().maxHitPoints(), record.hp);
    record.shields = std::max(unit->getShields(), 0);
    record.energy = std::max(unit->getEnergy(), 0);
    record.order_id = std::max(unit->getOrder().getID(), 0);
    record.visible =
        options.observability == "privileged" ? true : player_visible;
    record.position_source = "current";
    record.last_seen_frame = -1;
    observation.units.push_back(record);
  }

  std::sort(
      observation.units.begin(),
      observation.units.end(),
      [](const scai::UnitRecord& left, const scai::UnitRecord& right) {
        return left.unit_id < right.unit_id;
      });
  return observation;
}

bool map_command(
    const BWAPI::UnitCommand& command,
    int frame,
    int player_id,
    scai::ActionRecord& output) {
  const auto type = command.getType();
  output.frame = frame;
  output.player_id = player_id;
  if (command.getUnit()) output.actor_unit_ids = {command.getUnit()->getID()};

  if (type == BWAPI::UnitCommandTypes::Move) {
    output.action_type = "MOVE";
  } else if (type == BWAPI::UnitCommandTypes::Attack_Move) {
    output.action_type = "ATTACK_MOVE";
  } else if (type == BWAPI::UnitCommandTypes::Attack_Unit) {
    output.action_type = "ATTACK_UNIT";
  } else if (
      type == BWAPI::UnitCommandTypes::Right_Click_Position ||
      type == BWAPI::UnitCommandTypes::Right_Click_Unit) {
    output.action_type = "RIGHT_CLICK";
  } else if (type == BWAPI::UnitCommandTypes::Stop) {
    output.action_type = "STOP";
  } else if (type == BWAPI::UnitCommandTypes::Hold_Position) {
    output.action_type = "HOLD";
  } else if (type == BWAPI::UnitCommandTypes::Train) {
    output.action_type = "TRAIN";
    output.argument_type_id = command.getUnitType().getID();
  } else if (type == BWAPI::UnitCommandTypes::Build) {
    output.action_type = "BUILD";
    output.argument_type_id = command.getUnitType().getID();
  } else if (type == BWAPI::UnitCommandTypes::Morph) {
    output.action_type = "MORPH";
    output.argument_type_id = command.getUnitType().getID();
  } else if (type == BWAPI::UnitCommandTypes::Research) {
    output.action_type = "RESEARCH";
    output.argument_type_id = command.getTechType().getID();
  } else if (type == BWAPI::UnitCommandTypes::Upgrade) {
    output.action_type = "UPGRADE";
    output.argument_type_id = command.getUpgradeType().getID();
  } else {
    return false;
  }

  if (command.getTarget()) output.target_unit_id = command.getTarget()->getID();

  const auto target = command.getTargetPosition();
  if (target.isValid()) {
    output.target_x = std::max(target.x, 0);
    output.target_y = std::max(target.y, 0);
  }
  return true;
}

std::string action_signature(const scai::ActionRecord& action) {
  std::ostringstream key;
  key << action.action_type << "|"
      << action.target_unit_id << "|"
      << action.target_x << "|"
      << action.target_y << "|"
      << action.argument_type_id;
  return key.str();
}

std::vector<scai::ActionRecord> capture_actions(BWAPI::Player perspective) {
  const int frame = BWAPI::Broodwar->getFrameCount();
  std::map<std::string, scai::ActionRecord> grouped;

  for (const auto unit : perspective->getUnits()) {
    if (!unit || !unit->exists() || unit->getLastCommandFrame() != frame) continue;

    scai::ActionRecord action;
    if (!map_command(unit->getLastCommand(), frame, perspective->getID(), action)) {
      continue;
    }

    const std::string key = action_signature(action);
    auto [iterator, inserted] = grouped.emplace(key, action);
    if (inserted) {
      iterator->second.actor_unit_ids.clear();
    }
    iterator->second.actor_unit_ids.push_back(unit->getID());
  }

  std::vector<scai::ActionRecord> actions;
  actions.reserve(grouped.size());
  for (auto& [key, action] : grouped) {
    (void)key;
    std::sort(action.actor_unit_ids.begin(), action.actor_unit_ids.end());
    actions.push_back(action);
  }
  return actions;
}

std::string episode_id(BWAPI::Player perspective) {
  std::ostringstream output;
  output << "bwapi-" << BWAPI::Broodwar->mapHash() << "-p" << perspective->getID();
  return output.str();
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Options options = parse_options(argc, argv);
    std::cout << "Connecting to BWAPI...\n";
    connect();

    while (!BWAPI::Broodwar->isInGame()) {
      BWAPI::BWAPIClient.update();
      if (!BWAPI::BWAPIClient.isConnected()) connect();
    }

    if (BWAPI::Broodwar->isReplay() != (options.mode == "replay")) {
      throw std::runtime_error("connected match does not match requested --mode");
    }
    if (options.observability == "privileged") {
      BWAPI::Broodwar->enableFlag(BWAPI::Flag::CompleteMapInformation);
    }

    BWAPI::Player perspective = perspective_player(options);
    if (!perspective) throw std::runtime_error("could not resolve perspective player");

    const std::string episode = episode_id(perspective);
    std::vector<PendingTransition> pending;
    std::vector<std::string> output_lines;
    int next_step = 0;

    while (BWAPI::Broodwar->isInGame()) {
      const int frame = BWAPI::Broodwar->getFrameCount();
      const auto current = capture_observation(options, perspective);

      for (const auto& action : capture_actions(perspective)) {
        pending.push_back({next_step++, frame + options.horizon_frames, current, action});
      }

      std::vector<PendingTransition> remaining;
      for (const auto& item : pending) {
        if (frame >= item.due_frame) {
          output_lines.push_back(
              scai::transition_json(
                  episode, item.step, item.observation, item.action, current, 0.0, false));
        } else {
          remaining.push_back(item);
        }
      }
      pending.swap(remaining);

      BWAPI::BWAPIClient.update();
      if (!BWAPI::BWAPIClient.isConnected()) {
        throw std::runtime_error("BWAPI disconnected during match");
      }
    }

    if (!pending.empty()) {
      auto final_observation = pending.back().observation;
      final_observation.frame =
          std::max(final_observation.frame + 1, BWAPI::Broodwar->getFrameCount());
      for (const auto& item : pending) {
        output_lines.push_back(
            scai::transition_json(
                episode,
                item.step,
                item.observation,
                item.action,
                final_observation,
                0.0,
                true));
      }
    }

    scai::atomic_write_lines(options.output, output_lines);
    std::cout << "wrote " << output_lines.size() << " transitions to "
              << options.output << "\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "collector error: " << error.what() << "\n";
    return 1;
  }
}
