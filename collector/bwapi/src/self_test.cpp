#include "transition_json.hpp"

#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
  std::string output_path = "collector-selftest.jsonl";
  for (int index = 1; index + 1 < argc; ++index) {
    if (std::string(argv[index]) == "--output") output_path = argv[index + 1];
  }

  scai::ObservationRecord current;
  current.frame = 0;
  current.player_id = 0;
  current.minerals = 50;
  current.gas = 0;
  current.supply_used = 8;
  current.supply_total = 18;
  current.map_width = 128;
  current.map_height = 128;
  current.explored_fraction = 0.05;
  current.units.push_back(
      {1, 7, "self", 320, 320, 40, 40, 0, 0, 3, true, "current", -1});

  scai::ActionRecord action;
  action.frame = 0;
  action.player_id = 0;
  action.action_type = "MOVE";
  action.actor_unit_ids = {1};
  action.target_x = 352;
  action.target_y = 336;

  scai::ObservationRecord next = current;
  next.frame = 8;
  next.units[0].x = 352;
  next.units[0].y = 336;

  const std::vector<std::string> lines = {
      scai::transition_json(
          "bwapi-collector-selftest", 0, current, action, next, 0.0, false)};

  try {
    scai::atomic_write_lines(output_path, lines);
  } catch (const std::exception& error) {
    std::cerr << error.what() << "\n";
    return 1;
  }

  std::cout << "wrote " << lines.size() << " transition -> " << output_path << "\n";
  return 0;
}
