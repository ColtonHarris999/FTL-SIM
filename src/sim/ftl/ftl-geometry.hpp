// sim/ftl/ftl-geometry.hpp
#pragma once

#include <cstdint>
#include <sim/setup/setup-config.hpp>

namespace sim::ftl {

struct SsdGeometry {
    std::uint64_t bits_per_cell;
    std::uint64_t bytes_per_page;

    std::uint64_t user_bytes_per_page;   // ignoring spare / OOB area for now
    std::uint64_t ecc_bytes_per_page;    // ECC overhead per page (approx.)

    std::uint64_t pages_per_block;
    std::uint64_t blocks_total;
    std::uint64_t pages_total;

    std::uint64_t raw_capacity_bytes;    // user + ECC
    std::uint64_t user_capacity_bytes;   // user data only

    double user_capacity_gib() const;
};

// Compute full SSD geometry from configuration
SsdGeometry derive_geometry(const sim::setup::SetupConfig& cfg);

} // namespace sim::ftl
