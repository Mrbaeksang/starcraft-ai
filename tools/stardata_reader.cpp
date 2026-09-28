#include <replayer.h>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct FrameSummary {
  std::size_t index = 0;
  std::size_t units = 0;
  std::size_t actions = 0;
  std::size_t resource_players = 0;
};

FrameSummary summarize_frame(
    std::size_t index,
    const torchcraft::replayer::Frame* frame,
    std::set<int32_t>& player_ids) {
  if (!frame) {
    throw std::runtime_error("missing frame");
  }

  FrameSummary summary;
  summary.index = index;

  for (const auto& [player_id, units] : frame->units) {
    player_ids.insert(player_id);
    summary.units += units.size();
  }
  for (const auto& [player_id, actions] : frame->actions) {
    player_ids.insert(player_id);
    summary.actions += actions.size();
  }
  for (const auto& [player_id, resources] : frame->resources) {
    (void)resources;
    player_ids.insert(player_id);
    ++summary.resource_players;
  }
  return summary;
}


void write_state_jsonl(
    const torchcraft::replayer::Replayer& replay,
    const std::string& output_path) {
  std::ofstream out(output_path);
  if (!out.good()) {
    throw std::runtime_error("cannot open state JSONL output");
  }

  for (std::size_t index = 0; index < replay.size(); ++index) {
    const auto* frame = replay.getFrame(index);
    if (!frame) {
      continue;
    }

    std::vector<int32_t> resource_players;
    resource_players.reserve(frame->resources.size());
    for (const auto& [player_id, resources] : frame->resources) {
      (void)resources;
      resource_players.push_back(player_id);
    }
    std::sort(resource_players.begin(), resource_players.end());

    std::vector<int32_t> unit_players;
    unit_players.reserve(frame->units.size());
    for (const auto& [player_id, units] : frame->units) {
      (void)units;
      unit_players.push_back(player_id);
    }
    std::sort(unit_players.begin(), unit_players.end());

    out << "{";
    out << "\"schema_version\":1,";
    out << "\"sample_index\":" << index << ",";
    out << "\"approx_game_frame\":" << (index * 3) << ",";
    out << "\"map_width\":" << replay.mapWidth() << ",";
    out << "\"map_height\":" << replay.mapHeight() << ",";
    out << "\"is_terminal\":" << (frame->is_terminal ? "true" : "false") << ",";

    out << "\"resources\":[";
    bool first_resource = true;
    for (const auto player_id : resource_players) {
      const auto& resources = frame->resources.at(player_id);
      if (!first_resource) {
        out << ",";
      }
      first_resource = false;
      out
          << "{\"player_id\":" << player_id
          << ",\"minerals\":" << resources.ore
          << ",\"gas\":" << resources.gas
          << ",\"supply_used\":" << resources.used_psi
          << ",\"supply_total\":" << resources.total_psi
          << ",\"upgrades\":" << resources.upgrades
          << ",\"upgrade_levels\":" << resources.upgrades_level
          << ",\"techs\":" << resources.techs
          << "}";
    }
    out << "],";

    out << "\"units\":[";
    bool first_unit = true;
    for (const auto player_id : unit_players) {
      auto units = frame->units.at(player_id);
      std::sort(
          units.begin(),
          units.end(),
          [](const torchcraft::replayer::Unit& left,
             const torchcraft::replayer::Unit& right) {
            return left.id < right.id;
          });

      for (const auto& unit : units) {
        if (!first_unit) {
          out << ",";
        }
        first_unit = false;

        int order_type = -1;
        int order_target_id = -1;
        int order_target_x = -1;
        int order_target_y = -1;
        if (!unit.orders.empty()) {
          const auto& order = unit.orders.back();
          order_type = order.type;
          order_target_id = order.targetId;
          order_target_x = order.targetX;
          order_target_y = order.targetY;
        }

        out
            << "{\"player_id\":" << player_id
            << ",\"unit_id\":" << unit.id
            << ",\"type_id\":" << unit.type
            << ",\"x\":" << unit.x
            << ",\"y\":" << unit.y
            << ",\"pixel_x\":" << unit.pixel_x
            << ",\"pixel_y\":" << unit.pixel_y
            << ",\"hp\":" << unit.health
            << ",\"hp_max\":" << unit.max_health
            << ",\"shield\":" << unit.shield
            << ",\"energy\":" << unit.energy
            << ",\"visible\":" << unit.visible
            << ",\"order_type\":" << order_type
            << ",\"order_target_id\":" << order_target_id
            << ",\"order_target_x\":" << order_target_x
            << ",\"order_target_y\":" << order_target_y
            << "}";
      }
    }
    out << "]}\n";
  }
}

void print_frame_summary(const char* label, const FrameSummary& summary) {
  std::cout
      << "\"" << label << "\":{"
      << "\"index\":" << summary.index
      << ",\"units\":" << summary.units
      << ",\"actions\":" << summary.actions
      << ",\"resource_players\":" << summary.resource_players
      << "}";
}

void print_resources(
    const char* label,
    const torchcraft::replayer::Frame* frame) {
  std::vector<int32_t> players;
  for (const auto& [player_id, resources] : frame->resources) {
    (void)resources;
    players.push_back(player_id);
  }
  std::sort(players.begin(), players.end());

  std::cout << "\"" << label << "_resources\":[";
  bool first = true;
  for (const auto player_id : players) {
    const auto& resources = frame->resources.at(player_id);
    if (!first) {
      std::cout << ",";
    }
    first = false;
    std::cout
        << "{\"player_id\":" << player_id
        << ",\"minerals\":" << resources.ore
        << ",\"gas\":" << resources.gas
        << ",\"supply_used\":" << resources.used_psi
        << ",\"supply_total\":" << resources.total_psi
        << "}";
  }
  std::cout << "]";
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 2 && argc != 4) {
      std::cerr << "usage: stardata-reader FILE.tcr [--frames-jsonl OUTPUT]\n";
      return 2;
    }

    std::string frames_jsonl;
    if (argc == 4) {
      if (std::string(argv[2]) != "--frames-jsonl") {
        throw std::runtime_error("expected --frames-jsonl");
      }
      frames_jsonl = argv[3];
    }

    torchcraft::replayer::Replayer replay;
    replay.load(argv[1]);
    if (replay.size() == 0) {
      throw std::runtime_error("replay contains zero frames");
    }

    const std::size_t first_index = 0;
    const std::size_t middle_index = replay.size() / 2;
    const std::size_t last_index = replay.size() - 1;

    std::set<int32_t> player_ids;
    const auto first =
        summarize_frame(first_index, replay.getFrame(first_index), player_ids);
    const auto middle =
        summarize_frame(middle_index, replay.getFrame(middle_index), player_ids);
    const auto last =
        summarize_frame(last_index, replay.getFrame(last_index), player_ids);

    std::size_t total_actions = 0;
    std::size_t frames_with_actions = 0;
    std::set<std::string> unit_command_events;
    std::set<int32_t> unit_command_frames;
    std::set<std::string> order_events;
    std::size_t max_units = 0;
    std::size_t first_nonempty_frame = replay.size();

    for (std::size_t index = 0; index < replay.size(); ++index) {
      const auto* frame = replay.getFrame(index);
      if (!frame) {
        continue;
      }
      std::size_t frame_units = 0;
      for (const auto& [player_id, units] : frame->units) {
        player_ids.insert(player_id);
        frame_units += units.size();

        for (const auto& unit : units) {
          if (unit.command.type >= 0 && unit.command.type < 44) {
            std::ostringstream key;
            key << player_id << "|"
                << unit.command.frame << "|"
                << unit.command.type << "|"
                << unit.command.targetId << "|"
                << unit.command.targetX << "|"
                << unit.command.targetY << "|"
                << unit.command.extra;
            unit_command_events.insert(key.str());
            unit_command_frames.insert(unit.command.frame);
          }

          for (const auto& order : unit.orders) {
            std::ostringstream key;
            key << player_id << "|"
                << unit.id << "|"
                << order.first_frame << "|"
                << order.type << "|"
                << order.targetId << "|"
                << order.targetX << "|"
                << order.targetY;
            order_events.insert(key.str());
          }
        }
      }
      max_units = std::max(max_units, frame_units);
      if (frame_units > 0 && first_nonempty_frame == replay.size()) {
        first_nonempty_frame = index;
      }
      for (const auto& [player_id, resources] : frame->resources) {
        (void)resources;
        player_ids.insert(player_id);
      }
      std::size_t frame_actions = 0;
      for (const auto& [player_id, actions] : frame->actions) {
        player_ids.insert(player_id);
        frame_actions += actions.size();
      }
      total_actions += frame_actions;
      if (frame_actions > 0) {
        ++frames_with_actions;
      }
    }

    std::cout << "{";
    std::cout << "\"frames\":" << replay.size() << ",";
    std::cout << "\"map_width\":" << replay.mapWidth() << ",";
    std::cout << "\"map_height\":" << replay.mapHeight() << ",";
    std::cout << "\"total_actions\":" << total_actions << ",";
    std::cout << "\"frames_with_actions\":" << frames_with_actions << ",";
    std::cout << "\"unit_command_events\":" << unit_command_events.size() << ",";
    std::cout << "\"unit_command_frames\":" << unit_command_frames.size() << ",";
    std::cout << "\"order_events\":" << order_events.size() << ",";
    std::cout << "\"max_units\":" << max_units << ",";
    std::cout << "\"first_nonempty_frame\":"
              << (first_nonempty_frame == replay.size() ? -1 : static_cast<long long>(first_nonempty_frame))
              << ",";

    std::cout << "\"player_ids\":[";
    bool first_player = true;
    for (const auto player_id : player_ids) {
      if (!first_player) {
        std::cout << ",";
      }
      first_player = false;
      std::cout << player_id;
    }
    std::cout << "],";

    print_frame_summary("first", first);
    std::cout << ",";
    print_frame_summary("middle", middle);
    std::cout << ",";
    print_frame_summary("last", last);
    std::cout << ",";

    print_resources("first", replay.getFrame(first_index));
    std::cout << ",";
    print_resources("last", replay.getFrame(last_index));
    std::cout << "}\n";

    if (!frames_jsonl.empty()) {
      write_state_jsonl(replay, frames_jsonl);
      std::cerr << "wrote " << replay.size()
                << " sampled states to " << frames_jsonl << "\n";
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "stardata-reader error: " << error.what() << "\n";
    return 1;
  }
}
