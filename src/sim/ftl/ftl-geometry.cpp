// sim/ftl/ftl-geometry.cpp
#include <sim/ftl/ftl-geometry.hpp>
#include <sim/setup/enums.hpp>
#include <stdexcept>

namespace sim::ftl {

// Helper: compute ECC bytes per page from ecc_bits_per_1k
static std::uint64_t compute_ecc_bytes_per_page(
    const sim::setup::SetupConfig& cfg,
    std::uint64_t user_bytes_per_page
) {
    using sim::setup::EccType;

    if (cfg.ecc_type == EccType::None || cfg.ecc_bits_per_1k == 0) {
        return 0;
    }

    // ecc_bits_per_1k bits per 1024 bytes of user data (approx).
    std::uint64_t units_1k = (user_bytes_per_page + 1023) / 1024;
    std::uint64_t ecc_bits = static_cast<std::uint64_t>(cfg.ecc_bits_per_1k) * units_1k;
    std::uint64_t ecc_bytes = (ecc_bits + 7) / 8;
    return ecc_bytes;
}

double SsdGeometry::user_capacity_gib() const {
    return static_cast<double>(user_capacity_bytes) / (1024.0 * 1024.0 * 1024.0);
}

SsdGeometry derive_geometry(const sim::setup::SetupConfig& cfg) {
    if (cfg.bits_per_cell == 0 ||
        cfg.bytes_per_page == 0 ||
        cfg.pages_per_block == 0 ||
        cfg.blocks_per_plane == 0 ||
        cfg.planes_per_die == 0 ||
        cfg.dies_per_package == 0 ||
        cfg.packages == 0) {
        throw std::invalid_argument("derive_geometry: invalid physical parameters");
    }

    SsdGeometry g{};

    g.bits_per_cell   = cfg.bits_per_cell;
    g.bytes_per_page  = cfg.bytes_per_page;
    g.user_bytes_per_page = cfg.bytes_per_page; // ignoring spare area for now

    g.ecc_bytes_per_page = compute_ecc_bytes_per_page(cfg, g.user_bytes_per_page);

    g.pages_per_block = cfg.pages_per_block;

    g.blocks_total =
        static_cast<std::uint64_t>(cfg.blocks_per_plane) *
        cfg.planes_per_die *
        cfg.dies_per_package *
        cfg.packages;

    g.pages_total = g.blocks_total * g.pages_per_block;

    g.user_capacity_bytes = g.pages_total * g.user_bytes_per_page;
    g.raw_capacity_bytes  = g.pages_total *
                            (g.user_bytes_per_page + g.ecc_bytes_per_page);

    return g;
}

} // namespace sim::ftl
