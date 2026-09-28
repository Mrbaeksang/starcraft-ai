#pragma once

#include <cstdio>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace scai {

struct UnitRecord {
  int unit_id = 0;
  int type_id = 0;
  std::string owner = "neutral";
  int x = 0;
  int y = 0;
  int hp = 0;
  int hp_max = 0;
  int shields = 0;
  int energy = 0;
  int order_id = 0;
  bool visible = true;
  std::string position_source = "current";
  int last_seen_frame = -1;
};

struct ObservationRecord {
  int frame = 0;
  int player_id = 0;
  int minerals = 0;
  int gas = 0;
  int supply_used = 0;
  int supply_total = 0;
  int map_width = 1;
  int map_height = 1;
  double explored_fraction = 0.0;
  std::vector<int> upgrades;
  std::vector<int> techs;
  std::vector<UnitRecord> units;
};

struct ActionRecord {
  int frame = 0;
  int player_id = 0;
  std::string action_type;
  std::vector<int> actor_unit_ids;
  int target_unit_id = -1;
  int target_x = -1;
  int target_y = -1;
  int argument_type_id = -1;
};

inline std::string escape_json(const std::string& value) {
  std::ostringstream output;
  for (const unsigned char ch : value) {
    switch (ch) {
      case '"': output << "\\\""; break;
      case '\\': output << "\\\\"; break;
      case '\b': output << "\\b"; break;
      case '\f': output << "\\f"; break;
      case '\n': output << "\\n"; break;
      case '\r': output << "\\r"; break;
      case '\t': output << "\\t"; break;
      default:
        if (ch < 0x20) {
          output << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                 << static_cast<int>(ch) << std::dec;
        } else {
          output << ch;
        }
    }
  }
  return output.str();
}

inline void write_nullable_int(std::ostream& output, int value) {
  if (value < 0) {
    output << "null";
  } else {
    output << value;
  }
}

inline void write_unit(std::ostream& output, const UnitRecord& unit) {
  output << "{"
         << "\"unit_id\":" << unit.unit_id
         << ",\"type_id\":" << unit.type_id
         << ",\"owner\":\"" << escape_json(unit.owner) << "\""
         << ",\"x\":" << unit.x
         << ",\"y\":" << unit.y
         << ",\"hp\":" << unit.hp
         << ",\"hp_max\":" << unit.hp_max
         << ",\"shields\":" << unit.shields
         << ",\"energy\":" << unit.energy
         << ",\"order_id\":" << unit.order_id
         << ",\"visible\":" << (unit.visible ? "true" : "false")
         << ",\"position_source\":\"" << escape_json(unit.position_source) << "\""
         << ",\"last_seen_frame\":";
  write_nullable_int(output, unit.last_seen_frame);
  output << "}";
}

inline void write_int_array(std::ostream& output, const std::vector<int>& values) {
  output << "[";
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index) output << ",";
    output << values[index];
  }
  output << "]";
}

inline void write_observation(std::ostream& output, const ObservationRecord& observation) {
  output << "{"
         << "\"schema_version\":1"
         << ",\"frame\":" << observation.frame
         << ",\"player_id\":" << observation.player_id
         << ",\"minerals\":" << observation.minerals
         << ",\"gas\":" << observation.gas
         << ",\"supply_used\":" << observation.supply_used
         << ",\"supply_total\":" << observation.supply_total
         << ",\"map_width\":" << observation.map_width
         << ",\"map_height\":" << observation.map_height
         << ",\"explored_fraction\":" << std::setprecision(8)
         << observation.explored_fraction
         << ",\"upgrades\":";
  write_int_array(output, observation.upgrades);
  output << ",\"techs\":";
  write_int_array(output, observation.techs);
  output << ",\"units\":[";
  for (std::size_t index = 0; index < observation.units.size(); ++index) {
    if (index) output << ",";
    write_unit(output, observation.units[index]);
  }
  output << "]}";
}

inline void write_action(std::ostream& output, const ActionRecord& action) {
  output << "{"
         << "\"schema_version\":1"
         << ",\"frame\":" << action.frame
         << ",\"player_id\":" << action.player_id
         << ",\"action_type\":\"" << escape_json(action.action_type) << "\""
         << ",\"actor_unit_ids\":";
  write_int_array(output, action.actor_unit_ids);
  output << ",\"target_unit_id\":";
  write_nullable_int(output, action.target_unit_id);
  output << ",\"target_x\":";
  write_nullable_int(output, action.target_x);
  output << ",\"target_y\":";
  write_nullable_int(output, action.target_y);
  output << ",\"argument_type_id\":";
  write_nullable_int(output, action.argument_type_id);
  output << "}";
}

inline std::string transition_json(
    const std::string& episode_id,
    int step,
    const ObservationRecord& observation,
    const ActionRecord& action,
    const ObservationRecord& next_observation,
    double reward,
    bool terminal) {
  std::ostringstream output;
  output << "{"
         << "\"schema_version\":1"
         << ",\"episode_id\":\"" << escape_json(episode_id) << "\""
         << ",\"step\":" << step
         << ",\"observation\":";
  write_observation(output, observation);
  output << ",\"action\":";
  write_action(output, action);
  output << ",\"next_observation\":";
  write_observation(output, next_observation);
  output << ",\"reward\":" << std::setprecision(8) << reward
         << ",\"terminal\":" << (terminal ? "true" : "false")
         << "}";
  return output.str();
}

inline void atomic_write_lines(
    const std::string& output_path,
    const std::vector<std::string>& lines) {
  const std::string temporary_path = output_path + ".tmp";
  {
    std::ofstream output(temporary_path, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("failed to open temporary output file");
    for (const auto& line : lines) output << line << "\n";
    if (!output.good()) throw std::runtime_error("failed while writing output shard");
  }

  std::remove(output_path.c_str());
  if (std::rename(temporary_path.c_str(), output_path.c_str()) != 0) {
    throw std::runtime_error("failed to atomically rename output shard");
  }
}

}  // namespace scai
