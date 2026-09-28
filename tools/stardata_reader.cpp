#include <replayer.h>

#include <algorithm>
#include <cstdint>
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
    if (argc != 2) {
      std::cerr << "usage: stardata-reader FILE.tcr\n";
      return 2;
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
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "stardata-reader error: " << error.what() << "\n";
    return 1;
  }
}
