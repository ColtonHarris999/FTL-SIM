#pragma once
#include <string>
#include <sim/setup/setup-config.hpp>

namespace sim::setup {
    SetupConfig load_ssd_config(const std::string& path);
}
