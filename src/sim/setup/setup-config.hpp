#pragma once
#include <cstdint>
#include <sim/setup/enums.hpp>

namespace sim::setup {

struct SetupConfig {
    // Physical NAND parameters
    std::uint32_t bits_per_cell;
    std::uint32_t bytes_per_page;
    std::uint32_t pages_per_block;

    // Higher-level array geometry
    std::uint32_t blocks_per_plane;
    std::uint32_t planes_per_die;
    std::uint32_t dies_per_package;
    std::uint32_t packages;

    // ECC
    EccType ecc_type;
    std::uint32_t ecc_bits_per_1k;

    // DRAM model
    std::uint64_t dram_bytes;
    std::uint64_t fast_ftl_bytes;

    // FTL mapping
    MappingGranularity base_mapping;
    MappingGranularity fast_mapping;
    std::uint32_t subpages_per_page;
};

} // namespace sim::setup
